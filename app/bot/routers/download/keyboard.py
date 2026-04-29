from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.i18n import gettext as _
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.routers.misc.keyboard import back_button, back_to_main_menu_button
from app.bot.utils.constants import (
    APP_ANDROID_LINK,
    APP_ANDROID_SCHEME,
    APP_HAPP_ANDROID_LINK,
    APP_HAPP_IOS_LINK,
    APP_HAPP_SCHEME,
    APP_HAPP_WINDOWS_LINK,
    APP_IOS_LINK,
    APP_IOS_SCHEME,
    APP_WINDOWS_LINK,
    APP_WINDOWS_SCHEME,
    CONNECTION_WEBHOOK,
)
from app.bot.utils.navigation import NavDownload, NavMain, NavSubscription, NavSupport


_PLATFORM_APPS = {
    NavDownload.PLATFORM_IOS: (
        (NavDownload.APP_IOS_V2, "download:button:app_v2raytun"),
        (NavDownload.APP_IOS_HAPP, "download:button:app_happ"),
    ),
    NavDownload.PLATFORM_ANDROID: (
        (NavDownload.APP_ANDROID_V2, "download:button:app_v2raytun"),
        (NavDownload.APP_ANDROID_HAPP, "download:button:app_happ"),
    ),
    NavDownload.PLATFORM_WINDOWS: (
        (NavDownload.APP_WINDOWS_V2, "download:button:app_v2rayn"),
        (NavDownload.APP_WINDOWS_HAPP, "download:button:app_happ"),
    ),
}


_APP_RESOURCES = {
    NavDownload.APP_IOS_V2: (APP_IOS_SCHEME, APP_IOS_LINK),
    NavDownload.APP_IOS_HAPP: (APP_HAPP_SCHEME, APP_HAPP_IOS_LINK),
    NavDownload.APP_ANDROID_V2: (APP_ANDROID_SCHEME, APP_ANDROID_LINK),
    NavDownload.APP_ANDROID_HAPP: (APP_HAPP_SCHEME, APP_HAPP_ANDROID_LINK),
    NavDownload.APP_WINDOWS_V2: (APP_WINDOWS_SCHEME, APP_WINDOWS_LINK),
    NavDownload.APP_WINDOWS_HAPP: (APP_HAPP_SCHEME, APP_HAPP_WINDOWS_LINK),
}


def get_app_resources(app: str) -> tuple[str, str]:
    return _APP_RESOURCES[app]


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

    if previous_callback == NavMain.MAIN_MENU:
        builder.row(back_to_main_menu_button())
    else:
        back_callback = previous_callback if previous_callback else NavSupport.HOW_TO_CONNECT
        builder.row(back_button(back_callback))

    return builder.as_markup()


def apps_keyboard(platform: NavDownload) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for app_callback, label_key in _PLATFORM_APPS[platform]:
        builder.row(
            InlineKeyboardButton(
                text=_(label_key),
                callback_data=app_callback,
            )
        )

    builder.row(back_button(NavDownload.MAIN))
    return builder.as_markup()


def download_keyboard(app: NavDownload, url: str, key: str, back_to: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    scheme, download = get_app_resources(app)
    connect = f"{url}{CONNECTION_WEBHOOK}?scheme={scheme}&key={key}"

    builder.button(text=_("download:button:download"), url=download)

    builder.button(
        text=_("download:button:connect"),
        url=connect if key else None,
        callback_data=NavSubscription.MAIN if not key else None,
    )

    builder.row(back_button(back_to))
    return builder.as_markup()
