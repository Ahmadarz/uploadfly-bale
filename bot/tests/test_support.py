"""پشتیبانی: سؤالات متداول + چت مستقیم با حساب پشتیبانی + ایمیل (از .env)."""
import dataclasses

import app.handlers
import app.web
from app.config import clean_email, clean_username
from tests.conftest import BUYER, MAIN_ID, SHOP_ID, message
from tests.test_web import as_user, client  # noqa: F401


def configure(monkeypatch, username, email):
    for mod in (app.handlers, app.web):
        monkeypatch.setattr(mod, "settings", dataclasses.replace(mod.settings, support_username=username, support_email=email))


async def test_support_command_with_contact(env, monkeypatch):
    configure(monkeypatch, "UploadFlySupport", "help@example.com")
    await env.feed(env.main, message(BUYER, "/support"))
    text, buttons = env.tg.texts(MAIN_ID), env.tg.buttons(MAIN_ID)
    assert "help@example.com" in text and str(BUYER) in text
    assert any(b.get("url") == "https://t.me/UploadFlySupport" for b in buttons)
    assert any(b.get("web_app", {}).get("url", "").endswith("/?page=support") for b in buttons)
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "/start support"))           # از سایت یا ربات فروشگاه
    assert "پشتیبانی UploadFly" in env.tg.texts(MAIN_ID)
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, "/support"))                 # در ربات فروشگاه: لینک به ربات اصلی
    assert any(b.get("url", "").endswith("?start=support") for b in env.tg.buttons(SHOP_ID))


async def test_support_without_contact_hides_buttons(env, monkeypatch):
    configure(monkeypatch, None, None)
    await env.feed(env.main, message(BUYER, "/support"))
    assert "ایمیل" not in env.tg.texts(MAIN_ID)
    assert not any("t.me/" in b.get("url", "") for b in env.tg.buttons(MAIN_ID))


async def test_me_exposes_support_contact(env, client, monkeypatch):  # noqa: F811
    configure(monkeypatch, "UploadFlySupport", "help@example.com")
    me = await (await client.get("/api/me", headers=as_user(BUYER, via_shop=False))).json()
    assert me["support"] == {"username": "UploadFlySupport", "email": "help@example.com"}


def test_contact_values_are_validated():
    assert clean_username("@Upload_Fly_Support") == "Upload_Fly_Support"
    assert clean_username("bad name") is None and clean_username("x") is None and clean_username("") is None
    assert clean_email("support@uploadfly.app") == "support@uploadfly.app"
    assert clean_email("not-an-email") is None and clean_email('a"@b.co') is None and clean_email("") is None
