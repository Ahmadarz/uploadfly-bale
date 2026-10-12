"""کیف پول فروشنده: موجودی آزاد و در انتظار ۲۱ روزه، تاریخچه، خرید Premium از موجودی ربات."""
from datetime import datetime, timedelta, timezone

from app import shop
from app.db import Purchase, SessionLocal
from tests.conftest import BUYER, MockSession, OWNER, SHOP_ID
from tests.test_flows import make_product, pay
from tests.test_web import as_user, client  # noqa: F401  (fixture)


async def test_wallet_splits_available_and_pending(env, client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(MockSession, "star_balance", 100)
    shop._balance_cache.clear()
    c = await make_product(env, price=30, title="قدیمی")
    old = await pay(env, c, buyer=601, charge="w-old")
    new = await pay(env, c, buyer=602, charge="w-new")
    gone = await pay(env, c, buyer=603, charge="w-ref")
    async with SessionLocal() as s:
        (await s.get(Purchase, old.id)).created_at = datetime.now(timezone.utc) - timedelta(days=30)
        (await s.get(Purchase, gone.id)).refunded = True
        await s.commit()
    w = await (await client.get("/api/wallet", headers=as_user(OWNER, via_shop=False))).json()
    assert w["balance"] == 100 and w["pending"] == 30 and w["available"] == 70   # فقط فروش تازه در انتظار است
    assert w["min"] == 1000 and w["hold_days"] == 21 and w["next_unlock"]
    assert [(x["amount"], x["refunded"], x["unlocked"]) for x in w["sales"]] == [
        (30, True, False), (30, False, False), (30, False, True)]
    assert w["sales"][0]["title"] == "قدیمی" and w["sales"][0]["kind"] == "photo"
    # کسی که فروشگاه ندارد
    assert (await client.get("/api/wallet", headers=as_user(BUYER, via_shop=False))).status == 404


async def test_pending_never_exceeds_real_balance(env, client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(MockSession, "star_balance", 5)
    shop._balance_cache.clear()
    c = await make_product(env, price=30)
    await pay(env, c, buyer=601, charge="w-1")
    w = await (await client.get("/api/wallet", headers=as_user(OWNER, via_shop=False))).json()
    assert w["pending"] == 5 and w["available"] == 0


async def test_buy_premium_from_bot_balance(env, client, monkeypatch):  # noqa: F811
    h = as_user(OWNER, via_shop=False)
    shop._balance_cache.clear()
    r = await client.post("/api/wallet/premium", headers=h, json={"months": 3})
    assert r.status == 400 and (await r.json())["error"] == "not_enough"           # موجودی ۱۰
    assert not env.tg.sent(SHOP_ID, "GiftPremiumSubscription")
    assert (await (await client.post("/api/wallet/premium", headers=h, json={"months": 5})).json())["error"] == "bad_months"
    assert (await client.post("/api/wallet/premium", headers=h, json={"months": "x"})).status == 400
    monkeypatch.setattr(MockSession, "star_balance", 2000)
    r = await client.post("/api/wallet/premium", headers=h, json={"months": 6})
    assert r.status == 200
    (gift,) = env.tg.sent(SHOP_ID, "GiftPremiumSubscription")   # از ربات فروشگاه، نه ربات اصلی
    assert gift["user_id"] == OWNER and gift["month_count"] == 6 and gift["star_count"] == 1500
    # فقط صاحب فروشگاه، برای خودش: خریدار فروشگاه ندارد
    assert (await client.post("/api/wallet/premium", headers=as_user(BUYER, via_shop=False), json={"months": 3})).status == 404


async def test_premium_failure_is_reported_not_crashed(env, client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(MockSession, "star_balance", 2000)
    shop._balance_cache.clear()

    async def refuse(**kw):
        raise RuntimeError("STARS_NOT_AVAILABLE")   # مثلاً استارزها هنوز در دوره‌ی ۲۱ روزه‌اند
    monkeypatch.setattr(env.shop, "gift_premium_subscription", refuse)
    r = await client.post("/api/wallet/premium", headers=as_user(OWNER, via_shop=False), json={"months": 3})
    assert r.status == 400 and (await r.json())["error"] == "premium_failed"


async def test_first_sale_message_builds_trust(env):
    c = await make_product(env, price=10)
    await pay(env, c, buyer=601, charge="fs-1")
    to_owner = [m["text"] for m in env.tg.sent(SHOP_ID, "SendMessage") if m["chat_id"] == OWNER]
    assert any("اولین فروشت" in x and "Balance" in x for x in to_owner)
    env.tg.clear()
    await pay(env, c, buyer=602, charge="fs-2")
    to_owner = [m["text"] for m in env.tg.sent(SHOP_ID, "SendMessage") if m["chat_id"] == OWNER]
    assert to_owner and not any("اولین فروشت" in x for x in to_owner) and "مال خودت" in to_owner[0]
