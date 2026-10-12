"""رفتار حلقه‌ی دریافت پیام هنگام قطعی اینترنت."""
import asyncio

from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import GetUpdates

from app import bots
from app.bots import BotManager, retry_delay


def test_retry_delay_grows_and_caps():
    assert [retry_delay(n) for n in range(1, 9)] == [2, 4, 8, 16, 32, 60, 60, 60]


async def test_outage_logs_once_and_reports_recovery(env, monkeypatch, caplog):
    calls = {"n": 0}

    async def flaky_get_updates(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 5:
            raise TelegramNetworkError(method=GetUpdates(), message="down")
        if calls["n"] == 6:
            return []
        raise asyncio.CancelledError

    monkeypatch.setattr(bots, "retry_delay", lambda n: 0)
    monkeypatch.setattr(env.main, "get_updates", flaky_get_updates)
    manager = BotManager(env.dp, env.main)
    caplog.set_level("INFO", logger="app.bots")
    try:
        await manager._poll(env.main)
    except asyncio.CancelledError:
        pass
    msgs = [r.getMessage() for r in caplog.records if r.name == "app.bots"]
    assert sum("Lost connection" in m for m in msgs) == 1          # فقط یک بار، نه به ازای هر تلاش
    assert any("restored" in m and "after 5" in m for m in msgs)


async def test_long_outage_rebuilds_the_connection(env, monkeypatch):
    """بعد از قطع و وصل اینترنت، اتصال‌های خراب قدیمی دور ریخته و از نو ساخته می‌شوند (هر ۳ تلاش ناموفق)."""
    calls, resets = {"n": 0}, []

    async def flaky_get_updates(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 7:
            raise TelegramNetworkError(method=GetUpdates(), message="down")
        raise asyncio.CancelledError

    async def fake_reset(bot):
        resets.append(calls["n"])

    monkeypatch.setattr(bots, "retry_delay", lambda n: 0)
    monkeypatch.setattr(bots, "reset_session", fake_reset)
    monkeypatch.setattr(env.main, "get_updates", flaky_get_updates)
    try:
        await BotManager(env.dp, env.main)._poll(env.main)
    except asyncio.CancelledError:
        pass
    assert resets == [3, 6]


async def test_reset_session_survives_a_broken_session(env, monkeypatch):
    async def boom():
        raise RuntimeError("already broken")
    monkeypatch.setattr(env.main.session, "close", boom)
    await bots.reset_session(env.main)  # نباید خطا بدهد
