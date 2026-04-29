import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from aiohttp.web import HTTPFound, Request, Response

from app.bot.models import ServicesContainer
from app.bot.utils.constants import (
    APP_ANDROID_SCHEME,
    APP_HAPP_SCHEME,
    APP_IOS_SCHEME,
    APP_WINDOWS_SCHEME,
    MAIN_MESSAGE_ID_KEY,
    PREVIOUS_CALLBACK_KEY,
)
from app.bot.utils.navigation import NavDownload, NavMain
from app.bot.utils.network import parse_redirect_url
from app.config import Config
from app.db.models import User

from .keyboard import apps_keyboard, download_keyboard, platforms_keyboard

logger = logging.getLogger(__name__)
router = Router(name=__name__)


_ALLOWED_SCHEMES = {
    APP_IOS_SCHEME,
    APP_ANDROID_SCHEME,
    APP_WINDOWS_SCHEME,
    APP_HAPP_SCHEME,
}


_APP_TO_PLATFORM = {
    NavDownload.APP_IOS_V2: NavDownload.PLATFORM_IOS,
    NavDownload.APP_IOS_HAPP: NavDownload.PLATFORM_IOS,
    NavDownload.APP_ANDROID_V2: NavDownload.PLATFORM_ANDROID,
    NavDownload.APP_ANDROID_HAPP: NavDownload.PLATFORM_ANDROID,
    NavDownload.APP_WINDOWS_V2: NavDownload.PLATFORM_WINDOWS,
    NavDownload.APP_WINDOWS_HAPP: NavDownload.PLATFORM_WINDOWS,
}


_PLATFORM_LABELS = {
    NavDownload.PLATFORM_IOS: "download:message:platform_ios",
    NavDownload.PLATFORM_ANDROID: "download:message:platform_android",
    NavDownload.PLATFORM_WINDOWS: "download:message:platform_windows",
}


async def redirect_to_connection(request: Request) -> Response:
    query_string = request.query_string

    if not query_string:
        return Response(status=400, reason="Missing query string.")

    params = parse_redirect_url(query_string)
    scheme = params.get("scheme")
    key = params.get("key")

    if not scheme or not key:
        raise Response(status=400, reason="Invalid parameters.")

    redirect_url = f"{scheme}{key}"
    if scheme in _ALLOWED_SCHEMES:
        raise HTTPFound(redirect_url)

    return Response(status=400, reason="Unsupported application.")


@router.callback_query(F.data == NavDownload.MAIN)
async def callback_download(callback: CallbackQuery, user: User, state: FSMContext) -> None:
    logger.info(f"User {user.tg_id} opened download apps page.")

    main_message_id = await state.get_value(MAIN_MESSAGE_ID_KEY)
    previous_callback = await state.get_value(PREVIOUS_CALLBACK_KEY)

    logger.debug("--------------------------------")
    logger.debug(f"callback.message.message_id: {callback.message.message_id}")
    logger.debug(f"main_message_id: {main_message_id}")
    logger.debug(f"previous_callback: {previous_callback}")
    logger.debug("--------------------------------")
    if callback.message.message_id != main_message_id:
        await state.update_data({PREVIOUS_CALLBACK_KEY: NavMain.MAIN_MENU})
        previous_callback = NavMain.MAIN_MENU
        await callback.bot.edit_message_text(
            text=_("download:message:choose_platform"),
            chat_id=user.tg_id,
            message_id=main_message_id,
            reply_markup=platforms_keyboard(previous_callback),
        )
    else:
        await callback.message.edit_text(
            text=_("download:message:choose_platform"),
            reply_markup=platforms_keyboard(previous_callback),
        )


@router.callback_query(F.data.startswith(NavDownload.PLATFORM))
async def callback_platform(callback: CallbackQuery, user: User) -> None:
    logger.info(f"User {user.tg_id} selected platform: {callback.data}")

    platform_key = _PLATFORM_LABELS.get(callback.data)
    if not platform_key:
        return

    await callback.message.edit_text(
        text=_("download:message:choose_app").format(platform=_(platform_key)),
        reply_markup=apps_keyboard(callback.data),
    )


@router.callback_query(F.data.startswith(NavDownload.APP))
async def callback_app(
    callback: CallbackQuery,
    user: User,
    services: ServicesContainer,
    config: Config,
) -> None:
    logger.info(f"User {user.tg_id} selected app: {callback.data}")

    platform = _APP_TO_PLATFORM.get(callback.data)
    if not platform:
        return

    key = await services.vpn.get_key(user)
    platform_label = _(_PLATFORM_LABELS[platform])

    await callback.message.edit_text(
        text=_("download:message:connect_to_vpn").format(platform=platform_label),
        reply_markup=download_keyboard(
            app=callback.data,
            key=key,
            url=config.bot.DOMAIN,
            back_to=platform,
        ),
    )
