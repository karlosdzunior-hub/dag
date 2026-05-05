import re

BASE = "/opt/3xui-shop"

# ── 1. constants.py ──────────────────────────────────────────────────────────
with open(f"{BASE}/app/bot/utils/constants.py", "r") as f:
    txt = f.read()

if 'SUB_WEBHOOK' not in txt:
    txt = txt.replace(
        'CONNECTION_WEBHOOK = "/connection"',
        'CONNECTION_WEBHOOK = "/connection"\nSUB_WEBHOOK = "/sub"'
    )
    with open(f"{BASE}/app/bot/utils/constants.py", "w") as f:
        f.write(txt)
    print("✓ constants.py — SUB_WEBHOOK добавлен")
else:
    print("· constants.py — уже есть SUB_WEBHOOK")

# ── 2. vpn.py — добавить get_combined_subscription ───────────────────────────
with open(f"{BASE}/app/bot/services/vpn.py", "r") as f:
    txt = f.read()

METHOD = '''
    async def get_combined_subscription(self, vpn_id: str) -> bytes | None:
        import base64
        import aiohttp as _aiohttp

        connections = self.server_pool_service.get_all_connections()
        all_configs = []

        async with _aiohttp.ClientSession(
            connector=_aiohttp.TCPConnector(ssl=False)
        ) as session:
            for connection in connections:
                sub_url = extract_base_url(
                    url=connection.server.host,
                    port=self.config.xui.SUBSCRIPTION_PORT,
                    path=self.config.xui.SUBSCRIPTION_PATH,
                )
                full_url = f"{sub_url}{vpn_id}"
                try:
                    async with session.get(
                        full_url, timeout=_aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            raw = (await resp.text()).strip()
                            try:
                                decoded = base64.b64decode(raw + "==").decode("utf-8")
                                configs = [c for c in decoded.strip().split("\\n") if c.strip()]
                                all_configs.extend(configs)
                            except Exception:
                                if raw:
                                    all_configs.append(raw)
                except Exception as exc:
                    logger.error(f"[sub] Failed to fetch from {connection.server.name}: {exc}")

        if not all_configs:
            return None

        combined = "\\n".join(all_configs)
        return base64.b64encode(combined.encode("utf-8"))

'''

if 'get_combined_subscription' not in txt:
    txt = txt.replace(
        '\n    async def create_client(',
        METHOD + '\n    async def create_client('
    )
    with open(f"{BASE}/app/bot/services/vpn.py", "w") as f:
        f.write(txt)
    print("✓ vpn.py — get_combined_subscription добавлен")
else:
    print("· vpn.py — уже есть get_combined_subscription")

# ── 3. download/handler.py — добавить subscription_handler и обновить callback_app ──
with open(f"{BASE}/app/bot/routers/download/handler.py", "r") as f:
    txt = f.read()

# 3a. Добавить импорт SUB_WEBHOOK и base64
if 'SUB_WEBHOOK' not in txt:
    txt = txt.replace(
        'from app.bot.utils.constants import (',
        'import base64 as _base64\nfrom app.bot.utils.constants import ('
    )
    txt = txt.replace(
        '    MAIN_MESSAGE_ID_KEY,',
        '    MAIN_MESSAGE_ID_KEY,\n    SUB_WEBHOOK,'
    )
    print("✓ download/handler.py — импорт SUB_WEBHOOK добавлен")
else:
    print("· download/handler.py — SUB_WEBHOOK уже импортирован")

# 3b. Добавить subscription_handler перед @router.callback_query(F.data == NavDownload.MAIN)
HANDLER = '''

async def subscription_handler(request: Request) -> Response:
    vpn_id = request.match_info.get("vpn_id", "")
    if not vpn_id:
        return Response(status=400)

    vpn_service = request.app.get("vpn_service")
    if not vpn_service:
        return Response(status=503)

    content = await vpn_service.get_combined_subscription(vpn_id)
    if not content:
        return Response(status=404)

    title = _base64.b64encode("NovaaVPN".encode()).decode()
    return Response(
        body=content,
        content_type="text/plain; charset=utf-8",
        headers={"profile-title": title},
    )

'''

if 'subscription_handler' not in txt:
    txt = txt.replace(
        '\n@router.callback_query(F.data == NavDownload.MAIN)',
        HANDLER + '\n@router.callback_query(F.data == NavDownload.MAIN)'
    )
    print("✓ download/handler.py — subscription_handler добавлен")
else:
    print("· download/handler.py — subscription_handler уже есть")

# 3c. Обновить callback_app — использовать одну агрегированную ссылку
OLD_KEYS = '    keys = await services.vpn.get_all_keys(user)'
NEW_KEYS = (
    '    sub_url = f"{config.bot.DOMAIN}{SUB_WEBHOOK}/{user.vpn_id}"\n'
    '    keys = [("", sub_url)]'
)
if OLD_KEYS in txt and NEW_KEYS not in txt:
    txt = txt.replace(OLD_KEYS, NEW_KEYS)
    print("✓ download/handler.py — callback_app обновлён на combined URL")
else:
    print("· download/handler.py — callback_app уже обновлён или не найден")

with open(f"{BASE}/app/bot/routers/download/handler.py", "w") as f:
    f.write(txt)

# ── 4. routers/__init__.py — зарегистрировать маршрут ────────────────────────
with open(f"{BASE}/app/bot/routers/__init__.py", "r") as f:
    txt = f.read()

if 'SUB_WEBHOOK' not in txt:
    txt = txt.replace(
        'from app.bot.utils.constants import CONNECTION_WEBHOOK',
        'from app.bot.utils.constants import CONNECTION_WEBHOOK, SUB_WEBHOOK'
    )
    txt = txt.replace(
        '    app.router.add_get(CONNECTION_WEBHOOK, download.handler.redirect_to_connection)',
        '    app.router.add_get(CONNECTION_WEBHOOK, download.handler.redirect_to_connection)\n'
        '    app.router.add_get(SUB_WEBHOOK + "/{vpn_id}", download.handler.subscription_handler)'
    )
    with open(f"{BASE}/app/bot/routers/__init__.py", "w") as f:
        f.write(txt)
    print("✓ routers/__init__.py — маршрут /sub/{vpn_id} зарегистрирован")
else:
    print("· routers/__init__.py — маршрут уже зарегистрирован")

# ── 5. __main__.py — передать vpn_service в aiohttp app ─────────────────────
with open(f"{BASE}/app/__main__.py", "r") as f:
    txt = f.read()

if 'app["vpn_service"]' not in txt:
    txt = txt.replace(
        '    # Sync servers\n    await services_container.server_pool.sync_servers()',
        '    # Sync servers\n    await services_container.server_pool.sync_servers()\n\n'
        '    # Pass VPN service to aiohttp app for subscription handler\n'
        '    app["vpn_service"] = services_container.vpn'
    )
    with open(f"{BASE}/app/__main__.py", "w") as f:
        f.write(txt)
    print("✓ __main__.py — vpn_service передан в app")
else:
    print("· __main__.py — vpn_service уже передан")

print("\n✅ Готово! Перезапусти бота: sudo systemctl restart 3xui-shop")
