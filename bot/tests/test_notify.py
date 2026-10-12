"""پیام‌های بی‌صدا در برابر مهم، و منوی دستورها به زبان کاربر."""
from aiogram.types import BotCommandScopeChat

from app.bots import set_user_menu, setup_commands
from app.db import SessionLocal, User
from tests.conftest import BUYER, MAIN_ID, OWNER, SHOP_ID, callback, message
from tests.test_flows import make_product, pay


def silent(params: dict) -> bool:
    return params.get("disable_notification") is True


def sends(env, bot_id, chat_id):
    return [(m, p) for b, m, p in env.tg.calls if b == bot_id and m.startswith("Send") and p.get("chat_id") == chat_id]


async def test_publish_messages_are_silent(env):
    """انتشار محصول (پیش‌نمایش، لینک فروش) فقط برای سابقه است؛ نباید صدا بدهد."""
    from app.db import Content
    from sqlalchemy import select
    from tests.conftest import photo_message
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        cid = (await s.scalar(select(Content).order_by(Content.id.desc()))).id
    env.tg.clear()
    await env.feed(env.shop, callback(OWNER, f"price:{cid}:10"))
    out = sends(env, SHOP_ID, OWNER)
    assert out and all(silent(p) for _, p in out), [(m, p.get("disable_notification")) for m, p in out]


async def test_sale_is_loud_and_extras_silent(env):
    c = await make_product(env, price=10)
    await pay(env, c, buyer=BUYER, charge="n1")
    seller_msgs = sends(env, SHOP_ID, OWNER)
    assert seller_msgs and not any(silent(p) for _, p in seller_msgs)  # «فروش جدید» با صدا
    buyer = sends(env, SHOP_ID, BUYER)
    loud = [p["text"] for _, p in buyer if not silent(p)]
    quiet = [p["text"] for _, p in buyer if silent(p)]
    assert len(loud) == 1 and quiet  # فقط «پرداخت شد، محتوا را ببین» صدا دارد؛ «ساخته شده با UploadFly» بی‌صدا
    # تحویل محتوا با صدا، پیشنهاد گزارش بی‌صدا
    from app.db import Purchase
    from sqlalchemy import select
    async with SessionLocal() as s:
        pid = (await s.scalar(select(Purchase))).id
    env.tg.clear()
    await env.feed(env.shop, callback(BUYER, f"open:{pid}"))
    out = sends(env, SHOP_ID, BUYER)
    assert not silent(out[0][1]) and silent(out[-1][1])


async def test_default_menus_per_telegram_language(env):
    await setup_commands(env.main, seller=False)
    calls = env.tg.sent(MAIN_ID, "SetMyCommands")
    by_lang = {p.get("language_code", ""): [c["description"] for c in p["commands"]] for p in calls}
    assert by_lang[""][0] == "لینک‌های من" and set(by_lang) == {""}   # بله: فقط منوی فارسی
    assert {p["language_code"] for p in env.tg.sent(MAIN_ID, "DeleteMyCommands")} == {"fa", "en"}


async def test_menu_failure_does_not_break_start(env, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("telegram down")
    monkeypatch.setattr(env.main, "set_my_commands", boom)
    async with SessionLocal() as s:
        (await s.get(User, BUYER)).language = "en"
        await s.commit()
    await env.feed(env.main, message(BUYER, "/start"))
    assert "Welcome" in env.tg.texts() or env.tg.sent(MAIN_ID, "SendMessage")


async def test_tunnel_watchdog_restarts_only_when_internet_works(monkeypatch):
    """تونل مرده + اینترنت وصل → ری‌استارت بعد از ۳ بار. اینترنت قطع → صبر، بدون ری‌استارت."""
    import asyncio
    from app import tunnel
    killed = []
    monkeypatch.setattr(tunnel.os, "kill", lambda pid, sig: killed.append(sig))

    async def run(tunnel_ok, internet_ok):
        killed.clear()
        async def fake_reachable(session, url):
            return internet_ok if "cdn-cgi/trace" in url else tunnel_ok
        monkeypatch.setattr(tunnel, "reachable", fake_reachable)
        task = asyncio.create_task(tunnel.watch("https://x.trycloudflare.com", interval=0.001, failures_to_restart=3))
        await asyncio.wait([task], timeout=0.3)  # با ری‌استارت تمام می‌شود، وگرنه تا آخر وقت می‌چرخد
        task.cancel()
        return list(killed)

    assert await run(tunnel_ok=False, internet_ok=True)  # ری‌استارت
    assert not await run(tunnel_ok=False, internet_ok=False)  # اینترنت قطع: نه
    assert not await run(tunnel_ok=True, internet_ok=True)  # سالم: نه
