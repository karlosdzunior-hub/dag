from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.routers.misc.keyboard import back_button, back_to_main_menu_button
from app.bot.utils.constants import CONNECTION_WEBHOOK
from app.bot.utils.navigation import NavDownload, NavSubscription, NavSupport


def platforms_keyboard(previous_callback: str = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=_("download:button:ios"),
            callback_data=NavDownload.PLATFORM_IOS,
        ),
        InlineKeyboardButton(
            text=_("download:button:android"),
            callback_data=NavDownload.PLATFORM_ANDROID,
        ),
        InlineKeyboardButton(
            text=_("download:button:windows"),
            callback_data=NavDownload.PLATFORM_WINDOWS,
        ),
    )

    if previous_callback == "main_menu":
        builder.row(back_to_main_menu_button())
    else:
        back_callback = previous_callback if previous_callback else NavSupport.HOW_TO_CONNECT
        builder.row(back_button(back_callback))

    return builder.as_markup()


def apps_keyboard(
    v2_callback: str,
    happ_callback: str,
    back_to: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="V2RayTun", callback_data=v2_callback),
        InlineKeyboardButton(text="Happ", callback_data=happ_callback),
    )
    builder.row(back_button(back_to))

    return builder.as_markup()


def download_keyboard(
    download_link: str,
    scheme: str,
    key: str | None,
    url: str,
    back_to: str,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text=_("download:button:download"), url=download_link)

    if key:
        connect_url = f"{url}{CONNECTION_WEBHOOK}?scheme={scheme}&key={key}"
        builder.button(text=_("download:button:connect"), url=connect_url)
    else:
        builder.button(
            text=_("download:button:connect"),
            callback_data=NavSubscription.MAIN,
        )

    builder.adjust(1)
    builder.row(back_button(back_to))
    builder.row(back_to_main_menu_button())

    return builder.as_markup()
