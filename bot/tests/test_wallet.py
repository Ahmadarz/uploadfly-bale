"""کیف پول فروشنده در بله: جمع درآمد ثبت‌شده و تاریخچه‌ی فروش."""
from app.db import Purchase, SessionLocal
from tests.conftest import BUYER, OWNER, SHOP_ID
from tests.test_flows import make_product, pay
from tests.test_web import as_user, client  # noqa: F401  (fixture)


async def test_wallet_shows_recorded_income(env, client):  # noqa: F811
    c = await make_product(env, price=30, title="قدیمی")
    await pay(env, c, buyer=601, charge="w-old")
    await pay(env, c, buyer=602, charge="w-new")
    gone = await pay(env, c, buyer=603, charge="w-ref")
    async with SessionLocal() as s:
        (await s.get(Purchase, gone.id)).refunded = True
        await s.commit()
    w = await (await client.get("/api/wallet", headers=as_user(OWNER, via_shop=False))).json()
    # بله: پول همان لحظه در کیف پول فروشنده است؛ نه دوره‌ی انتظار، نه حداقل برداشت، نه Premium
    assert w["balance"] == 60 and w["pending"] == 0 and w["available"] == 60
    assert w["min"] == 0 and w["hold_days"] == 0 and w["next_unlock"] is None and w["premium"] == []
    assert [(x["amount"], x["refunded"]) for x in w["sales"]] == [(30, True), (30, False), (30, False)]
    assert w["sales"][0]["title"] == "قدیمی" and w["sales"][0]["kind"] == "photo"
    # کسی که فروشگاه ندارد
    assert (await client.get("/api/wallet", headers=as_user(BUYER, via_shop=False))).status == 404
    # خرید Premium مخصوص تلگرام بود
    r = await client.post("/api/wallet/premium", headers=as_user(OWNER, via_shop=False), json={"months": 3})
    assert r.status == 400 and not env.tg.sent(SHOP_ID, "GiftPremiumSubscription")


async def test_first_sale_message_builds_trust(env):
    c = await make_product(env, price=10)
    await pay(env, c, buyer=601, charge="fs-1")
    to_owner = [m["text"] for m in env.tg.sent(SHOP_ID, "SendMessage") if m["chat_id"] == OWNER]
    assert any("اولین فروشت" in x and "کیف پول بله" in x for x in to_owner)
    env.tg.clear()
    await pay(env, c, buyer=602, charge="fs-2")
    to_owner = [m["text"] for m in env.tg.sent(SHOP_ID, "SendMessage") if m["chat_id"] == OWNER]
    assert to_owner and not any("اولین فروشت" in x for x in to_owner) and "کیف پول بله‌ی خودت" in to_owner[0]
