"""API مینی‌اپ صفحه‌ی سازنده: تنظیمات، فن‌ها، کشف، دونیت، لایک، آزمایشی، بسته، خبر پست تازه، زمان‌بندی، ۱۸+."""
from datetime import timedelta

from sqlalchemy import select

from app import creator, showcases
from app.db import Content, SessionLocal, Seller
from tests.conftest import BUYER, OWNER, SHOP_ID, STRANGER, message, photo_message
from tests.test_flows import make_product, pay
from tests.test_web import as_user, client  # noqa: F401  (fixture)


def owner():
    return as_user(OWNER, via_shop=False)


async def test_creator_settings(env, client):  # noqa: F811
    r = await client.get("/api/creator", headers=owner())
    data = await r.json()
    assert r.status == 200 and data["dm_mode"] == "fans" and data["listed"] is True
    assert data["referral"]["link"].endswith(f"?start=ref_{OWNER}") and data["broadcast_link"].endswith("start=broadcast")
    r = await client.patch("/api/creator", headers=owner(), json={
        "bio": "مربی بدنسازی", "category": "fitness", "dm_mode": "all", "welcome": "خوش اومدی", "watermark": True,
        "listed": False})
    data = await r.json()
    assert (data["bio"], data["category"], data["dm_mode"], data["watermark"], data["listed"]) == \
        ("مربی بدنسازی", "fitness", "all", True, False)
    for bad in ({"category": "weird"}, {"dm_mode": "x"}, {"bio": "x" * 301}):
        assert (await client.patch("/api/creator", headers=owner(), json=bad)).status == 400
    # خریدار فروشگاه ندارد؛ امضای ربات فروشنده برای غیرصاحب اصلاً اجازه ندارد
    assert (await client.get("/api/creator", headers=as_user(BUYER, via_shop=False))).status == 403
    assert (await client.get("/api/creator", headers=as_user(BUYER))).status == 403
    assert (await client.get("/api/fans", headers=as_user(BUYER))).status == 403


async def test_fans_and_wallet_earnings(env, client):  # noqa: F811
    c = await make_product(env, price=10)
    await pay(env, c)
    data = await (await client.get("/api/fans", headers=owner())).json()
    assert [(f["number"], f["spent"]) for f in data["fans"]] == [(1, 10)]
    assert "id" not in data["fans"][0] and "name" not in data["fans"][0]   # ناشناس
    w = await (await client.get("/api/wallet", headers=owner())).json()
    assert w["earnings"]["sales"] == 10 and w["earnings"]["tips"] == 0


async def test_explore_hides_unlisted_and_sensitive(env, client):  # noqa: F811
    hb = as_user(BUYER, via_shop=False)
    assert (await (await client.get("/api/explore", headers=hb)).json())["items"] == []   # هنوز پستی ندارد
    await make_product(env, price=10)
    await client.patch("/api/creator", headers=owner(), json={"category": "art", "bio": "نقاشی دیجیتال"})
    items = (await (await client.get("/api/explore", headers=hb)).json())["items"]
    assert [(i["bot_id"], i["posts"], i["category"]) for i in items] == [(SHOP_ID, 1, "art")]
    assert (await (await client.get("/api/explore?q=نقاشی", headers=hb)).json())["items"]
    assert not (await (await client.get("/api/explore?q=zzz", headers=hb)).json())["items"]
    assert not (await (await client.get("/api/explore?cat=music", headers=hb)).json())["items"]
    assert (await client.get("/api/explore", headers=as_user(BUYER))).status == 403        # فقط از ربات اصلی
    await make_product(env, price=10, sensitive=True)                                      # محتوای حساس → هرگز در کشف
    assert (await (await client.get("/api/explore", headers=hb)).json())["items"] == []
    async with SessionLocal() as s:
        for c in (await s.scalars(select(Content).where(Content.is_sensitive.is_(True)))).all():
            c.is_active = False
        await s.commit()
    await client.patch("/api/creator", headers=owner(), json={"listed": False})
    assert (await (await client.get("/api/explore", headers=hb)).json())["items"] == []


async def test_tip_and_like_from_store(env, client):  # noqa: F811
    c = await make_product(env, price=10)
    hb = as_user(BUYER)   # از داخل ربات فروشنده
    r = await client.post(f"/api/store/{SHOP_ID}/tip", headers=hb, json={"amount": 25, "content_id": c.id})
    assert (await r.json())["invoice"] and env.tg.sent(SHOP_ID, "CreateInvoiceLink")[-1]["payload"] == f"t:25:{c.id}"
    assert (await client.post(f"/api/store/{SHOP_ID}/tip", headers=hb, json={"amount": 0})).status == 400
    assert (await client.post(f"/api/store/{SHOP_ID}/tip", headers=hb, json={"amount": "5"})).status == 400
    assert (await client.post(f"/api/store/{SHOP_ID}/tip", headers=owner(), json={"amount": 5})).status == 400
    r = await (await client.post(f"/api/store/{SHOP_ID}/like/{c.id}", headers=hb)).json()
    assert r == {"liked": True, "likes": 1}
    store = await (await client.get(f"/api/store/{SHOP_ID}", headers=hb)).json()
    assert store["items"][0]["likes"] == 1 and store["items"][0]["liked"] is True
    assert store["shop"]["tips"] == list(creator.TIP_PRESETS) and store["shop"]["dm_mode"] == "fans"
    r = await (await client.post(f"/api/store/{SHOP_ID}/like/{c.id}", headers=hb)).json()
    assert r == {"liked": False, "likes": 0}
    assert (await client.post(f"/api/store/{SHOP_ID}/like/99999", headers=hb)).status == 404


async def test_trial_and_bundles_from_page(env, client):  # noqa: F811
    r = await client.post("/api/showcases", headers=owner(), json={
        "title": "VIP", "access": "monthly", "price": 30, "trial_days": 7, "bundles": {"3": 10}})
    sc = await r.json()
    assert sc["trial_days"] == 7 and sc["bundles"] == {"3": 10}
    assert (await client.post("/api/showcases", headers=owner(), json={"title": "x", "trial_days": 5})).status == 400
    assert (await client.post("/api/showcases", headers=owner(), json={"title": "x", "bundles": {"3": 90}})).status == 400
    hb = as_user(BUYER)
    page = await (await client.get(f"/api/sc/{sc['code']}", headers=hb)).json()
    assert page["showcase"]["trial_available"] is True and page["showcase"]["bundles"][0]["price"] == 81
    r = await (await client.post(f"/api/sc/{sc['code']}/join", headers=hb, json={"months": 3})).json()
    assert env.tg.sent(SHOP_ID, "CreateInvoiceLink")[-1]["payload"] == f"s:{sc['id']}:3"
    assert (await client.post(f"/api/sc/{sc['code']}/join", headers=hb, json={"months": 6})).status == 400
    env.tg.clear()
    r = await client.post(f"/api/sc/{sc['code']}/trial", headers=hb)
    assert r.status == 200 and "آزمایشی" in env.tg.texts(SHOP_ID)
    page = await (await client.get(f"/api/sc/{sc['code']}", headers=hb)).json()
    assert page["showcase"]["is_member"] and page["showcase"]["is_trial"] and not page["showcase"]["trial_available"]
    assert (await (await client.post(f"/api/sc/{sc['code']}/trial", headers=hb)).json())["error"] == "sc_trial_used"
    r = await (await client.post(f"/api/sc/{sc['code']}/join", headers=hb, json={})).json()
    assert r.get("invoice")                                               # وسط آزمایشی می‌تواند مشترک شود


async def test_notify_new_post_once(env, client):  # noqa: F811
    c = await make_product(env, price=10)
    for uid in (BUYER, STRANGER):
        await env.feed(env.shop, message(uid, "/start"))
    env.tg.clear()
    r = await (await client.post(f"/api/products/{c.id}/notify", headers=owner())).json()
    await creator.drain()
    assert r["sent"] == 2
    sent = [m for m in env.tg.sent(SHOP_ID, "SendMessage") if "پست تازه" in m["text"]]
    assert {m["chat_id"] for m in sent} == {BUYER, STRANGER} and all(m["disable_notification"] for m in sent)
    assert (await (await client.post(f"/api/products/{c.id}/notify", headers=owner())).json())["error"] == "already_notified"
    assert (await client.post(f"/api/products/{c.id}/notify", headers=as_user(BUYER, via_shop=False))).status == 404


async def test_schedule_draft(env, client):  # noqa: F811
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        cid = (await s.scalar(select(Content))).id
    when = (showcases.utcnow() + timedelta(hours=2)).isoformat() + "Z"
    r = await client.patch(f"/api/products/{cid}", headers=owner(), json={"price": 20, "publish_at": when})
    p = await r.json()
    assert r.status == 200 and p["status"] == "draft" and p["publish_at"] and p["price"] == 20
    past = (showcases.utcnow() - timedelta(hours=2)).isoformat() + "Z"
    assert (await client.patch(f"/api/products/{cid}", headers=owner(), json={"publish_at": past})).status == 400
    async with SessionLocal() as s:
        c = await s.get(Content, cid)
        c.publish_at = showcases.utcnow() - timedelta(seconds=1)
        await s.commit()
    assert await creator.publish_due(env.manager) == 1
    p = await (await client.get(f"/api/products/{cid}", headers=owner())).json()
    assert p["status"] == "active" and p["publish_at"] is None
    assert (await client.patch(f"/api/products/{cid}", headers=owner(), json={"publish_at": when})).status == 400


async def test_adult_gate_in_mini_app(env, client):  # noqa: F811
    c = await make_product(env, price=10, sensitive=True)
    hb = as_user(BUYER)
    r = await client.post(f"/api/store/{SHOP_ID}/invoice/{c.id}", headers=hb)
    assert r.status == 409 and (await r.json())["error"] == "adult_confirm"
    assert (await client.post(f"/api/store/{SHOP_ID}/adult", headers=hb)).status == 200
    assert (await (await client.post(f"/api/store/{SHOP_ID}/invoice/{c.id}", headers=hb)).json())["invoice"]
    me = await (await client.get("/api/me", headers=hb)).json()
    assert me["adult_ok"] is True
    async with SessionLocal() as s:
        assert (await s.scalar(select(Seller))).bot_id == SHOP_ID


async def test_creator_script_is_served(client):  # noqa: F811
    html = await (await client.get("/")).text()
    assert "/static/creator.js?v=" in html and 'id="page-explore"' in html and 'id="tip-sheet"' in html
    r = await client.get("/static/creator.js?v=1")
    assert r.status == 200 and "creator.openExplore" in await r.text()


async def test_message_button_prompts_in_chat(env, client):  # noqa: F811
    from tests.test_creator import set_seller
    await set_seller(dm_mode="all")
    r = await client.post(f"/api/store/{SHOP_ID}/dm", headers=as_user(BUYER))
    data = await r.json()
    assert r.status == 200 and data["sent"] is True and data["chat"].endswith(f"bot{SHOP_ID}")
    (prompt,) = [m for m in env.tg.sent(SHOP_ID, "SendMessage") if m["chat_id"] == BUYER]
    assert "همین‌جا بنویس" in prompt["text"]
    assert (await (await client.post(f"/api/store/{SHOP_ID}/dm", headers=owner())).json())["error"] == "dm_self"
    await set_seller(dm_mode="fans")
    r = await client.post(f"/api/store/{SHOP_ID}/dm", headers=as_user(STRANGER))
    assert r.status == 403 and (await r.json())["error"] == "dm_fans_only"
    await set_seller(dm_mode="off")
    assert (await (await client.post(f"/api/store/{SHOP_ID}/dm", headers=as_user(BUYER))).json())["error"] == "dm_off"
