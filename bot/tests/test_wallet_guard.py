"""فروشگاهی که کیف پولش ثبت نشده (یا توکنش دیگر کار نمی‌کند) نباید مشتری را با سکوت روبه‌رو کند:
قیمت‌گذاری از Mini App بسته است، خریدار پیام روشن می‌گیرد و صاحب فروشگاه خبردار می‌شود."""
import pytest
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import select

from app import payments
from app.bale import BaleMiddleware, set_wallet
from app.db import Content, Seller, SessionLocal
from app.web import make_app
from tests.conftest import BUYER, MAIN_ID, OWNER, SHOP_ID, callback, message, photo_message
from tests.test_flows import make_product
from tests.test_web import as_user


@pytest.fixture
async def client(env):
    c = TestClient(TestServer(make_app(env.manager, "Uploadfly_Bot")))
    await c.start_server()
    yield c
    await c.close()


async def drop_wallet():
    async with SessionLocal() as s:
        seller = await s.scalar(select(Seller).where(Seller.bot_id == SHOP_ID))
        seller.wallet_enc = None
        await s.commit()
    set_wallet(SHOP_ID, None)


async def test_buyer_gets_a_clear_message_and_owner_is_told_once(env):
    c = await make_product(env, price=10)
    await drop_wallet()                                  # مثل وقتی که توکن کیف پول باطل شده
    env.shop.session.middleware(BaleMiddleware())        # همان لایه‌ی واقعی بله که فاکتور بدون کیف پول را رد می‌کند
    payments._owner_alerted.clear()
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))
    to_buyer = [p["text"] for p in env.tg.sent(SHOP_ID, "SendMessage") if p["chat_id"] == BUYER]
    assert any("پرداخت در این فروشگاه الان ممکن نیست" in x for x in to_buyer)
    to_owner = [p["text"] for p in env.tg.sent(SHOP_ID, "SendMessage") if p["chat_id"] == OWNER]
    assert len(to_owner) == 1 and "/wallet" in to_owner[0]
    assert not env.tg.sent(SHOP_ID, "SendInvoice")
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))   # بار دوم: صاحب فروشگاه دوباره پیام نمی‌گیرد
    assert not [p for p in env.tg.sent(SHOP_ID, "SendMessage") if p["chat_id"] == OWNER]
    env.shop.session.middleware._middlewares.clear()


async def test_donation_is_refused_without_a_wallet(env):
    await drop_wallet()
    await env.feed(env.shop, message(BUYER, "/donate"))
    assert "پرداخت در این فروشگاه الان ممکن نیست" in env.tg.texts(SHOP_ID)
    assert not [b for b in env.tg.buttons(SHOP_ID) if str(b.get("callback_data", "")).startswith("tip:")]


async def test_mini_app_cannot_price_without_a_wallet(env, client):
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        cid = (await s.scalar(select(Content).order_by(Content.id.desc()))).id
    await drop_wallet()
    me = await (await client.get("/api/me", headers=as_user(OWNER, via_shop=False))).json()
    assert me["shop"]["wallet"] is False and me["shop"]["wallet_link"] == "https://ble.ir/Uploadfly_Bot?start=wallet"
    r = await client.patch(f"/api/products/{cid}", headers=as_user(OWNER, via_shop=False),
                           json={"price": 10, "publish": True})
    assert r.status == 409 and (await r.json())["error"] == "no_wallet"
    r = await client.patch(f"/api/products/{cid}", headers=as_user(OWNER, via_shop=False),
                           json={"price": 0, "publish": True})          # رایگان همچنان ممکن است
    assert r.status == 200 and (await r.json())["status"] == "active"
    r = await client.post("/api/showcases", headers=as_user(OWNER, via_shop=False),
                          json={"title": "ویژه", "access": "once", "price": 10})
    assert r.status == 400 and (await r.json())["error"] == "no_wallet"


async def test_store_invoice_answers_a_clear_error(env, client):
    c = await make_product(env, price=10)
    await drop_wallet()
    env.shop.session.middleware(BaleMiddleware())
    try:
        r = await client.post(f"/api/store/{SHOP_ID}/invoice/{c.id}", headers=as_user(BUYER))
        assert r.status == 409 and (await r.json())["error"] == "pay_unavailable"
        store = await (await client.get(f"/api/store/{SHOP_ID}", headers=as_user(BUYER))).json()
        assert store["shop"]["pay"] is False
    finally:
        env.shop.session.middleware._middlewares.clear()


async def test_wallet_deep_link_starts_the_wallet_step(env):
    await env.feed(env.main, message(OWNER, "/start wallet"))
    assert "توکن کیف پول" in env.tg.texts(MAIN_ID)
    await env.feed(env.main, message(OWNER, "WALLET-TEST-1111111111111111"))
    assert "کیف پول" in env.tg.texts(MAIN_ID) and env.tg.sent(MAIN_ID, "DeleteMessage")
    await env.feed(env.main, callback(OWNER, "shop:home"))   # حالت گفت‌وگو تمام شده و فروشگاه سر جایش است
    assert "فروشگاه من" in env.tg.texts(MAIN_ID)
