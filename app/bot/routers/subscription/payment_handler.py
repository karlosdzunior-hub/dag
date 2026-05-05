import logging
import uuid

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from aiogram.utils.i18n import gettext as _
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters.is_dev import IsDev
from app.bot.models import ServicesContainer, SubscriptionData
from app.bot.payment_gateways import GatewayFactory
from app.bot.routers.main_menu.handler import redirect_to_main_menu
from app.bot.utils.constants import Currency, TransactionStatus
from app.bot.utils.formatting import format_subscription_period
from app.bot.utils.navigation import NavSubscription
from app.config import Config
from app.db.models import Transaction, User

from .keyboard import balance_confirm_keyboard, pay_keyboard

logger = logging.getLogger(__name__)
router = Router(name=__name__)


class PaymentState(StatesGroup):
    processing = State()


@router.callback_query(SubscriptionData.filter(F.state.startswith(NavSubscription.PAY)))
async def callback_payment_method_selected(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
    bot: Bot,
    gateway_factory: GatewayFactory,
    state: FSMContext,
) -> None:
    if await state.get_state() == PaymentState.processing:
        logger.debug(f"User {user.tg_id} is already processing payment.")
        return

    await state.set_state(PaymentState.processing)

    try:
        method = callback_data.state
        devices = callback_data.devices
        duration = callback_data.duration
        logger.info(f"User {user.tg_id} selected payment method: {method}")
        logger.info(f"User {user.tg_id} selected {devices} devices and {duration} days.")
        gateway = gateway_factory.get_gateway(method)
        plan = services.plan.get_plan(devices)
        price = plan.get_price(currency=gateway.currency, duration=duration)
        callback_data.price = price

        pay_url = await gateway.create_payment(callback_data)

        if callback_data.is_extend:
            text = _("payment:message:order_extend")
        elif callback_data.is_change:
            text = _("payment:message:order_change")
        else:
            text = _("payment:message:order")

        await callback.message.edit_text(
            text=text.format(
                devices=devices,
                duration=format_subscription_period(duration),
                price=price,
                currency=gateway.currency.symbol,
            ),
            reply_markup=pay_keyboard(pay_url=pay_url, callback_data=callback_data),
        )
    except Exception as exception:
        logger.error(f"Error processing payment: {exception}")
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))
    finally:
        await state.set_state(None)


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, user: User) -> None:
    logger.info(f"Pre-checkout query received from user {user.tg_id}")
    if pre_checkout_query.invoice_payload:
        await pre_checkout_query.answer(ok=True)
    else:
        await pre_checkout_query.answer(ok=False)


@router.message(F.successful_payment)
async def successful_payment(
    message: Message,
    user: User,
    session: AsyncSession,
    bot: Bot,
    gateway_factory: GatewayFactory,
) -> None:
    if await IsDev()(user_id=user.tg_id):
        await bot.refund_star_payment(
            user_id=user.tg_id,
            telegram_payment_charge_id=message.successful_payment.telegram_payment_charge_id,
        )

    data = SubscriptionData.unpack(message.successful_payment.invoice_payload)
    transaction = await Transaction.create(
        session=session,
        tg_id=user.tg_id,
        subscription=data.pack(),
        payment_id=message.successful_payment.telegram_payment_charge_id,
        status=TransactionStatus.COMPLETED,
    )

    gateway = gateway_factory.get_gateway(NavSubscription.PAY_TELEGRAM_STARS)
    await gateway.handle_payment_succeeded(payment_id=transaction.payment_id)


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.PAY_BALANCE))
async def callback_pay_with_balance(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
    config: Config,
) -> None:
    logger.info(f"User {user.tg_id} selected balance payment.")
    plan = services.plan.get_plan(callback_data.devices)
    currency = Currency.from_code(config.shop.CURRENCY)
    price = plan.get_price(currency=currency, duration=callback_data.duration)
    if price is None:
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))
        return

    balance = float(user.balance)
    if balance < float(price):
        await services.notification.show_popup(
            callback=callback,
            text=_("payment:popup:insufficient_balance").format(
                balance=f"{balance:.2f}",
                currency=currency.symbol,
            ),
        )
        return

    callback_data.price = price
    balance_after = balance - float(price)
    await callback.message.edit_text(
        text=_("payment:message:balance_confirm").format(
            price=price,
            currency=currency.symbol,
            balance=f"{balance:.2f}",
            balance_after=f"{balance_after:.2f}",
        ),
        reply_markup=balance_confirm_keyboard(callback_data=callback_data),
    )


@router.callback_query(SubscriptionData.filter(F.state == NavSubscription.PAY_BALANCE_CONFIRM))
async def callback_pay_with_balance_confirm(
    callback: CallbackQuery,
    user: User,
    callback_data: SubscriptionData,
    services: ServicesContainer,
    config: Config,
    session: AsyncSession,
    state: FSMContext,
    bot: Bot,
) -> None:
    logger.info(f"User {user.tg_id} confirmed balance payment.")
    plan = services.plan.get_plan(callback_data.devices)
    currency = Currency.from_code(config.shop.CURRENCY)
    price = plan.get_price(currency=currency, duration=callback_data.duration)
    if price is None:
        await services.notification.show_popup(callback=callback, text=_("payment:popup:error"))
        return

    fresh_user = await User.get(session=session, tg_id=user.tg_id)
    balance = float(fresh_user.balance)
    if balance < float(price):
        await services.notification.show_popup(
            callback=callback,
            text=_("payment:popup:insufficient_balance").format(
                balance=f"{balance:.2f}",
                currency=currency.symbol,
            ),
        )
        return

    await session.execute(
        sa_update(User)
        .where(User.tg_id == user.tg_id)
        .values(balance=User.balance - float(price))
    )
    payment_id = str(uuid.uuid4())
    callback_data.price = price
    await Transaction.create(
        session=session,
        tg_id=user.tg_id,
        subscription=callback_data.pack(),
        payment_id=payment_id,
        status=TransactionStatus.COMPLETED,
    )
    await session.commit()
    logger.info(f"Balance payment {payment_id} completed for user {user.tg_id}, deducted {price} {currency.code}")

    await redirect_to_main_menu(bot=bot, user=user, services=services, config=config, state=state)

    try:
        if callback_data.is_extend:
            await services.vpn.extend_subscription(
                user=user, devices=callback_data.devices, duration=callback_data.duration
            )
            await services.notification.notify_extend_success(user_id=user.tg_id, data=callback_data)
        elif callback_data.is_change:
            await services.vpn.change_subscription(
                user=user, devices=callback_data.devices, duration=callback_data.duration
            )
            await services.notification.notify_change_success(user_id=user.tg_id, data=callback_data)
        else:
            await services.vpn.create_subscription(
                user=user, devices=callback_data.devices, duration=callback_data.duration
            )
            key = await services.vpn.get_key(user)
            await services.notification.notify_purchase_success(user_id=user.tg_id, key=key)
    except Exception as exc:
        logger.error(f"Balance payment VPN activation failed for user {user.tg_id}: {exc}")
