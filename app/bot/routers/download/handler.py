import base64 as _base64
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.i18n import gettext as _
from aiohttp.web import HTTPFound, Request, Response

from app.bot.utils.constants import (
    APP_HAPP_SCHEME,
    APP_V2_ANDROID_SCHEME,
    APP_V2_IOS_SCHEME,
    APP_V2_WINDOWS_SCHEME,
    APP_V2_IOS_LINK,
    APP_V2_ANDROID_LINK,
    APP_V2_WINDOWS_LINK,
    APP_HAPP_IOS_LINK,
    APP_HAPP_ANDROID_LINK,
    APP_HAPP_WINDOWS_LINK,
    CONNECTION_WEBHOOK,
    MAIN_MESSAGE_ID_KEY,
    PREVIOUS_CALLBACK_KEY,
    SUB_WEBHOOK,
)
from app.bot.utils.navigation import NavDownload, NavMain, NavSubscription
from app.bot.utils.network import parse_redirect_url
from app.config import Config
from app.db.models import User

from .keyboard import apps_keyboard, download_keyboard, platforms_keyboard

logger = logging.getLogger(__name__)
router = Router(name=__name__)

_ALLOWED_SCHEMES = {
    APP_V2_IOS_SCHEME,
    APP_V2_ANDROID_SCHEME,
    APP_V2_WINDOWS_SCHEME,
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

_APP_LINKS = {
    NavDownload.APP_IOS_V2: APP_V2_IOS_LINK,
    NavDownload.APP_IOS_HAPP: APP_HAPP_IOS_LINK,
    NavDownload.APP_ANDROID_V2: APP_V2_ANDROID_LINK,
    NavDownload.APP_ANDROID_HAPP: APP_HAPP_ANDROID_LINK,
    NavDownload.APP_WINDOWS_V2: APP_V2_WINDOWS_LINK,
    NavDownload.APP_WINDOWS_HAPP: APP_HAPP_WINDOWS_LINK,
}

_APP_SCHEMES = {
    NavDownload.APP_IOS_V2: APP_V2_IOS_SCHEME,
    NavDownload.APP_IOS_HAPP: APP_HAPP_SCHEME,
    NavDownload.APP_ANDROID_V2: APP_V2_ANDROID_SCHEME,
    NavDownload.APP_ANDROID_HAPP: APP_HAPP_SCHEME,
    NavDownload.APP_WINDOWS_V2: APP_V2_WINDOWS_SCHEME,
    NavDownload.APP_WINDOWS_HAPP: APP_HAPP_SCHEME,
}

_PLATFORM_LABELS = {
    NavDownload.PLATFORM_IOS: "download:message:platform_ios",
    NavDownload.PLATFORM_ANDROID: "download:message:platform_android",
    NavDownload.PLATFORM_WINDOWS: "download:message:platform_windows",
}

_PLATFORM_APPS = {
    NavDownload.PLATFORM_IOS: (NavDownload.APP_IOS_V2, NavDownload.APP_IOS_HAPP),
    NavDownload.PLATFORM_ANDROID: (NavDownload.APP_ANDROID_V2, NavDownload.APP_ANDROID_HAPP),
    NavDownload.PLATFORM_WINDOWS: (NavDownload.APP_WINDOWS_V2, NavDownload.APP_WINDOWS_HAPP),
}


async def redirect_to_connection(request: Request) -> Response:
    query_string = request.query_string

    if not query_string:
        return Response(status=400, reason="Missing query string.")

    params = parse_redirect_url(query_string)
    scheme = params.get("scheme")
    key = params.get("key")

    if not scheme or not key:
        return Response(status=400, reason="Invalid parameters.")

    if scheme in _ALLOWED_SCHEMES:
        raise HTTPFound(f"{scheme}{key}")

    return Response(status=400, reason="Unsupported application.")


async def subscription_handler(request: Request) -> Response:
    vpn_id = request.match_info.get("vpn_id", "")
    if not vpn_id:
        return Response(status=400, reason="Missing vpn_id.")

    vpn_service = request.app.get("vpn_service")
    if not vpn_service:
        return Response(status=503, reason="VPN service unavailable.")

    content = await vpn_service.get_combined_subscription(vpn_id)
    if not content:
        return Response(status=404, reason="No subscription data found.")

    title = _base64.b64encode("DagVPN".encode()).decode()
    return Response(
        body=content,
        content_type="text/plain",
        charset="utf-8",
        headers={"profile-title": title},
    )


@router.callback_query(F.data == NavDownload.MAIN)
async def callback_download(callback: CallbackQuery, user: User, state: FSMContext) -> None:
    logger.info(f"User {user.tg_id} opened download page.")

    main_message_id = await state.get_value(MAIN_MESSAGE_ID_KEY)
    previous_callback = await state.get_value(PREVIOUS_CALLBACK_KEY)

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

    platform = callback.data
    platform_apps = _PLATFORM_APPS.get(platform)
    if not platform_apps:
        return

    v2_app, happ_app = platform_apps
    platform_label = _(_PLATFORM_LABELS[platform])

    await callback.message.edit_text(
        text=_("download:message:choose_app").format(platform=platform_label),
        reply_markup=apps_keyboard(
            v2_callback=v2_app,
            happ_callback=happ_app,
            back_to=NavDownload.MAIN,
        ),
    )


@router.callback_query(F.data.startswith(NavDownload.APP))
async def callback_app(
    callback: CallbackQuery,
    user: User,
    config: Config,
) -> None:
    logger.info(f"User {user.tg_id} selected app: {callback.data}")

    app = callback.data
    platform = _APP_TO_PLATFORM.get(app)
    download_link = _APP_LINKS.get(app)
    scheme = _APP_SCHEMES.get(app)

    if not platform or not download_link or not scheme:
        return

    platform_label = _(_PLATFORM_LABELS[platform])

    if user.vpn_id:
        key = f"{config.bot.DOMAIN}{SUB_WEBHOOK}/{user.vpn_id}"
    else:
        key = None

    await callback.message.edit_text(
        text=_("download:message:connect_to_vpn").format(platform=platform_label),
        reply_markup=download_keyboard(
            download_link=download_link,
            scheme=scheme,
            key=key,
            url=config.bot.DOMAIN,
            back_to=platform,
        ),
    )
