"""ویترین‌های چندگانه: ساخت و مدیریت، صفحه‌ی خریدار، ورود یک‌باره و ماهانه، باز کردن محتوای اعضا، بازپرداخت."""
import time

from sqlalchemy import select

from app.db import Membership, Purchase, SessionLocal, Showcase
from tests.conftest import BUYER, MAIN_ID, OWNER, SHOP_ID, STRANGER, message, user
from tests.test_flows import make_product
from tests.test_web import as_user, client  # noqa: F401  (fixture)


def owner():
    return as_user(OWNER, via_shop=False)


async def create(client, **body):  # noqa: F811
    r = await client.post("/api/showcases", headers=owner(), json=body)
    return r.status, await r.json()


async def join_payment(env, sc, buyer=BUYER, charge="sc-1", amount=None, expires=None):
    """پرداخت ورودی از طریق ربات فروشنده (همان چیزی که تلگرام بعد از پرداخت می‌فرستد)."""
    sp = {"currency": "XTR", "total_amount": amount if amount is not None else sc["price"],
          "invoice_payload": f"s:{sc['id']}", "telegram_payment_charge_id": charge, "provider_payment_charge_id": "p"}
    if expires:
        sp.update({"subscription_expiration_date": expires, "is_recurring": True, "is_first_recurring": True})
    await env.feed(env.shop, message(buyer, successful_payment=sp))


async def pre_checkout(env, sc, buyer=BUYER, amount=None):
    env.tg.clear()
    await env.feed(env.shop, {"pre_checkout_query": {
        "id": "pcq", "from": user(buyer), "currency": "XTR",
        "total_amount": amount if amount is not None else sc["price"], "invoice_payload": f"s:{sc['id']}"}})
    return env.tg.sent(SHOP_ID, "AnswerPreCheckoutQuery")[-1]["ok"]


async def test_seller_creates_and_validates_showcases(env, client):  # noqa: F811
    assert (await create(client, title="", access="free"))[1]["error"] == "sc_need_title"
    assert (await create(client, title="x", access="weird"))[1]["error"] == "bad_access"
    assert (await create(client, title="x", access="once", price=0))[1]["error"] == "bad_price"
    assert (await create(client, title="x", access="once", price=500))[1]["error"] == "price_cap"  # فروشنده‌ی تازه: سقف ۱۰۰
    status, sc = await create(client, title="پریست‌ها", description="ده پریست", access="once", price=50)
    assert status == 200 and sc["access"] == "once" and sc["price"] == 50 and sc["link"].endswith(f"?start=sc_{sc['code']}")
    status, free = await create(client, title="رایگان", access="free", price=99)
    assert free["price"] == 0                                              # ویترین رایگان قیمت ندارد
    data = await (await client.get("/api/showcases", headers=owner())).json()
    assert [x["title"] for x in data["items"]] == ["پریست‌ها", "رایگان"] and data["main"]["link"].endswith("start=store")
    # خریدار فروشگاه ندارد
    assert (await client.get("/api/showcases", headers=as_user(BUYER, via_shop=False))).status == 403


async def test_items_from_showcase_and_from_product_editor(env, client):  # noqa: F811
    a = await make_product(env, price=10, title="A")
    b = await make_product(env, price=20, title="B")
    _, sc = await create(client, title="ویژه", access="once", price=30,
                         items=[{"id": a.id, "member_free": True}, {"id": b.id, "member_free": False}, {"id": 99999}])
    assert {p["id"]: (p["included"], p["member_free"]) for p in sc["products"]} == {a.id: (True, True), b.id: (True, False)}
    p = await (await client.get(f"/api/products/{a.id}", headers=owner())).json()
    assert p["showcases"] == [sc["id"]]
    # از ویرایشگر محصول: B از ویترین خارج می‌شود، A می‌ماند و «رایگان برای اعضا»یش حفظ می‌شود
    r = await client.patch(f"/api/products/{b.id}", headers=owner(), json={"showcases": []})
    assert (await r.json())["showcases"] == []
    detail = await (await client.get(f"/api/showcases/{sc['id']}", headers=owner())).json()
    assert [(p["id"], p["included"]) for p in detail["products"] if p["included"]] == [(a.id, True)] and detail["items"] == 1
    # ویترین فروشگاه دیگری را نمی‌شود دید یا عوض کرد
    assert (await client.get(f"/api/showcases/{sc['id']}", headers=as_user(BUYER, via_shop=False))).status == 404


async def test_buyer_one_time_entry_flow(env, client):  # noqa: F811
    a = await make_product(env, price=10, title="عضو رایگان")
    b = await make_product(env, price=20, title="قیمت جدا")
    _, sc = await create(client, title="کلاس", access="once", price=30,
                         items=[{"id": a.id, "member_free": True}, {"id": b.id, "member_free": False}])
    hb = as_user(BUYER)
    page = await (await client.get(f"/api/sc/{sc['code']}", headers=hb)).json()
    assert page["showcase"]["is_member"] is False and all(i["locked"] for i in page["items"])
    assert {i["title"]: i["member_free"] for i in page["items"]} == {"عضو رایگان": True, "قیمت جدا": False}
    assert (await client.post(f"/api/sc/{sc['code']}/open/{a.id}", headers=hb)).status == 403   # هنوز عضو نیست
    r = await (await client.post(f"/api/sc/{sc['code']}/join", headers=hb)).json()
    assert r["invoice"] and env.tg.sent(SHOP_ID, "CreateInvoiceLink")[-1]["payload"] == f"s:{sc['id']}"
    assert await pre_checkout(env, sc) is True
    assert await pre_checkout(env, sc, amount=1) is False                  # قیمت عوض شده
    env.tg.clear()
    await join_payment(env, sc)
    assert "خوش اومدی" in env.tg.texts(SHOP_ID)
    to_owner = [m["text"] for m in env.tg.sent(SHOP_ID, "SendMessage") if m["chat_id"] == OWNER]
    assert any("عضو تازه" in x for x in to_owner)
    assert await pre_checkout(env, sc) is False                            # دوباره عضو نمی‌شود
    page = await (await client.get(f"/api/sc/{sc['code']}", headers=hb)).json()
    assert page["showcase"]["is_member"] is True and page["showcase"]["can_refund"] is True
    assert {i["title"]: i["unlocked"] for i in page["items"]} == {"عضو رایگان": True, "قیمت جدا": False}
    # محتوای جدا قیمت دارد؛ با عضویت باز نمی‌شود
    assert (await client.post(f"/api/sc/{sc['code']}/open/{b.id}", headers=hb)).status == 409
    env.tg.clear()
    assert (await client.post(f"/api/sc/{sc['code']}/open/{a.id}", headers=hb)).status == 200
    assert env.tg.sent(SHOP_ID, "SendPhoto")                               # تحویل در چت، محافظت‌شده
    async with SessionLocal() as s:
        p = await s.scalar(select(Purchase).where(Purchase.content_id == a.id, Purchase.buyer_id == BUYER))
        m = await s.scalar(select(Membership))
    assert p.amount == 0 and p.opened_at and m.opened_at
    # بعد از باز کردن، ورودی بازپرداخت نمی‌شود
    r = await client.post(f"/api/sc/{sc['code']}/refund", headers=hb)
    assert (await r.json())["error"] == "sc_refund_opened"
    # و حذف ویترینی که عضو دارد ممنوع است
    assert (await (await client.delete(f"/api/showcases/{sc['id']}", headers=owner())).json())["error"] == "sc_has_members"


async def test_refund_before_opening_removes_access(env, client):  # noqa: F811
    a = await make_product(env, price=10)
    _, sc = await create(client, title="X", access="once", price=30, items=[{"id": a.id}])
    await join_payment(env, sc, charge="sc-r")
    env.tg.clear()
    r = await client.post(f"/api/sc/{sc['code']}/refund", headers=as_user(BUYER))
    assert (await r.json())["refunded"] == 30 and env.tg.sent(SHOP_ID, "RefundStarPayment")
    page = await (await client.get(f"/api/sc/{sc['code']}", headers=as_user(BUYER))).json()
    assert page["showcase"]["is_member"] is False
    assert (await client.delete(f"/api/showcases/{sc['id']}", headers=owner())).status == 200   # دیگر عضو ندارد
    assert (await client.get(f"/api/sc/{sc['code']}", headers=as_user(BUYER))).status == 404


async def test_monthly_subscription_and_expiry(env, client):  # noqa: F811
    a = await make_product(env, price=10)
    _, sc = await create(client, title="ماهانه", access="monthly", price=40, items=[{"id": a.id}])
    await client.post(f"/api/sc/{sc['code']}/join", headers=as_user(BUYER))
    assert env.tg.sent(SHOP_ID, "CreateInvoiceLink")[-1]["subscription_period"] == 2592000
    await join_payment(env, sc, charge="sub-1", expires=int(time.time()) + 30 * 86400)
    page = await (await client.get(f"/api/sc/{sc['code']}", headers=as_user(BUYER))).json()
    assert page["showcase"]["is_member"] and page["showcase"]["expires_at"] and page["showcase"]["can_refund"] is False
    async with SessionLocal() as s:   # یک ماه گذشت و تمدید نشد
        m = await s.scalar(select(Membership))
        m.expires_at = m.expires_at.replace(year=2020)
        await s.commit()
    page = await (await client.get(f"/api/sc/{sc['code']}", headers=as_user(BUYER))).json()
    assert page["showcase"]["is_member"] is False and page["items"][0]["locked"]


async def test_free_showcase_and_chat_link(env, client):  # noqa: F811
    a = await make_product(env, price=0, title="هدیه")
    _, sc = await create(client, title="رایگان‌ها", access="free", items=[{"id": a.id}])
    page = await (await client.get(f"/api/sc/{sc['code']}", headers=as_user(BUYER))).json()
    assert not page["items"][0]["locked"] and page["showcase"]["access"] == "free"
    assert (await (await client.post(f"/api/sc/{sc['code']}/join", headers=as_user(BUYER))).json())["member"] is True
    # لینک بایو: در ربات فروشنده دکمه‌ی باز کردن ویترین می‌آید
    env.tg.clear()
    await env.feed(env.shop, message(STRANGER, f"/start sc_{sc['code']}"))
    btn = env.tg.buttons(SHOP_ID)[0]
    assert "رایگان‌ها" in env.tg.texts(SHOP_ID) and f"sc={sc['code']}" in btn["web_app"]["url"]
    env.tg.clear()
    await env.feed(env.shop, message(STRANGER, "/start sc_nope"))
    assert "وجود نداره" in env.tg.texts(SHOP_ID)
    # کد ویترین در ربات اصلی (یا فروشگاه دیگر) کار نمی‌کند
    env.tg.clear()
    await env.feed(env.main, message(STRANGER, f"/start sc_{sc['code']}"))
    assert "وجود نداره" in env.tg.texts(MAIN_ID)


async def test_showcase_limit(env, client, monkeypatch):  # noqa: F811
    from app import showcases
    monkeypatch.setattr(showcases, "MAX_SHOWCASES", 2)
    await create(client, title="1")
    await create(client, title="2")
    assert (await create(client, title="3"))[1]["error"] == "sc_limit"
    async with SessionLocal() as s:
        assert len((await s.scalars(select(Showcase))).all()) == 2


# --- اشتراک ماهانه: یادآوری، پایان، لغو تمدید ---
async def test_subscription_reminder_end_and_renewal(env, client):  # noqa: F811
    from datetime import datetime, timedelta, timezone
    from app import showcases
    a = await make_product(env, price=10)
    _, sc = await create(client, title="ماهانه <ویژه>", access="monthly", price=40, items=[{"id": a.id}])
    soon = int((datetime.now(timezone.utc) + timedelta(days=2)).timestamp())
    await join_payment(env, sc, charge="first-charge", expires=soon)
    async with SessionLocal() as s:
        m = await s.scalar(select(Membership))
    assert m.sub_charge_id == "first-charge"
    # یک بار یادآوری (۳ روز قبل)، نه دو بار
    env.tg.clear()
    assert await showcases.subscription_tick(env.manager, "https://app.example") == 1
    assert "تمدید می‌شود" in env.tg.texts(SHOP_ID) and env.tg.buttons(SHOP_ID)[0]["web_app"]
    assert "&lt;ویژه&gt;" in env.tg.texts(SHOP_ID)                     # عنوان با < پیام را خراب نمی‌کند
    assert await showcases.subscription_tick(env.manager, "https://app.example") == 0
    # لغو تمدید از Mini App: با شناسه‌ی پرداخت اول؛ یادآوری با متن «تمدید نمی‌شود» دوباره می‌آید
    r = await client.post(f"/api/sc/{sc['code']}/renewal", headers=as_user(BUYER), json={"cancel": True})
    assert (await r.json())["renewal_canceled"] is True
    edit = env.tg.sent(SHOP_ID, "EditUserStarSubscription")[-1]
    assert edit["telegram_payment_charge_id"] == "first-charge" and edit["is_canceled"] is True
    env.tg.clear()
    await showcases.subscription_tick(env.manager, None)
    assert "تمدید نمی‌شود" in env.tg.texts(SHOP_ID)
    page = await (await client.get(f"/api/sc/{sc['code']}", headers=as_user(BUYER))).json()
    assert page["showcase"]["renewal_canceled"] is True and page["showcase"]["is_subscription"] is True
    # سررسید گذشت و تمدید نشد → پیام پایان (یک بار)
    async with SessionLocal() as s:
        m = await s.scalar(select(Membership))
        m.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=3)
        await s.commit()
    env.tg.clear()
    assert await showcases.subscription_tick(env.manager, None) == 1
    assert "تمام شد" in env.tg.texts(SHOP_ID)
    assert await showcases.subscription_tick(env.manager, None) == 0


async def test_renewal_payment_keeps_subscription_id(env, client):  # noqa: F811
    a = await make_product(env, price=10)
    _, sc = await create(client, title="M", access="monthly", price=40, items=[{"id": a.id}])
    await join_payment(env, sc, charge="c1", expires=int(time.time()) + 86400)
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, successful_payment={
        "currency": "XTR", "total_amount": 40, "invoice_payload": f"s:{sc['id']}", "telegram_payment_charge_id": "c2",
        "provider_payment_charge_id": "p", "subscription_expiration_date": int(time.time()) + 31 * 86400,
        "is_recurring": True}))
    assert "تمدید شد" in env.tg.texts(SHOP_ID)
    async with SessionLocal() as s:
        last = await s.scalar(select(Membership).order_by(Membership.id.desc()))
    assert last.charge_id == "c2" and last.sub_charge_id == "c1"
    # یک‌باره اشتراک نیست
    _, once = await create(client, title="O", access="once", price=20, items=[{"id": a.id}])
    await join_payment(env, once, charge="o1")
    r = await client.post(f"/api/sc/{once['code']}/renewal", headers=as_user(BUYER), json={"cancel": True})
    assert (await r.json())["error"] == "sc_not_subscription"


async def test_member_stats_wallet_and_sales_counting(env, client, monkeypatch):  # noqa: F811
    from app import shop
    from tests.conftest import MockSession
    a = await make_product(env, price=10, title="عضو")
    _, sc = await create(client, title="S", access="once", price=30, items=[{"id": a.id}])
    await join_payment(env, sc, charge="w1")
    await client.post(f"/api/sc/{sc['code']}/open/{a.id}", headers=as_user(BUYER))   # باز کردن ۰ استارزی
    detail = await (await client.get(f"/api/showcases/{sc['id']}", headers=owner())).json()
    assert detail["members"] == 1 and detail["revenue"] == 30 and detail["month_revenue"] == 30
    me = await (await client.get("/api/me", headers=owner())).json()
    assert me["shop"]["total_n"] == 1 and me["shop"]["total_sum"] == 30   # ورودی حساب شد، باز شدن نه
    monkeypatch.setattr(MockSession, "star_balance", 100)
    shop._balance_cache.clear()
    w = await (await client.get("/api/wallet", headers=owner())).json()
    assert w["pending"] == 30 and w["sales"][0]["title"] == "🔑 S" and w["sales"][0]["kind"] == "showcase"
    items = (await (await client.get("/api/products?tab=active", headers=owner())).json())["items"]
    assert items[0]["sales"] == 0                                             # باز شدن با عضویت فروش نیست


# --- امتیاز خریدارها ---
async def test_ratings_only_from_buyers_who_opened(env, client):  # noqa: F811
    from tests.test_flows import pay
    from tests.conftest import callback
    c = await make_product(env, price=10, title="R")
    p = await pay(env, c, buyer=BUYER, charge="r1")
    await env.feed(env.shop, callback(BUYER, f"rate:{p.id}:5"))               # هنوز باز نکرده
    assert "بعد از خرید و دیدن" in str(env.tg.sent(SHOP_ID, "AnswerCallbackQuery")[-1])
    env.tg.clear()
    await env.feed(env.shop, callback(BUYER, f"open:{p.id}"))
    assert any(b.get("callback_data") == f"rate:{p.id}:5" for b in env.tg.buttons(SHOP_ID))
    await env.feed(env.shop, callback(BUYER, f"rate:{p.id}:4"))
    await env.feed(env.shop, callback(STRANGER, f"rate:{p.id}:1"))            # خرید دیگری نیست
    p2 = await pay(env, c, buyer=STRANGER, charge="r2")
    await client.post(f"/api/store/{SHOP_ID}/open/{c.id}", headers=as_user(STRANGER))
    r = await client.post(f"/api/store/{SHOP_ID}/rate/{c.id}", headers=as_user(STRANGER), json={"stars": 2})
    assert (await r.json())["rating"] == {"avg": 3.0, "count": 2}
    assert (await client.post(f"/api/store/{SHOP_ID}/rate/{c.id}", headers=as_user(STRANGER), json={"stars": 9})).status == 403
    store = await (await client.get(f"/api/store/{SHOP_ID}", headers=as_user(BUYER))).json()
    item = store["items"][0]
    assert item["rating"] == {"avg": 3.0, "count": 2} and item["my_rating"] == 4 and store["shop"]["rating"]["count"] == 2
    me = await (await client.get("/api/me", headers=owner())).json()
    assert me["shop"]["top"][0]["title"] == "R" and me["shop"]["top"][0]["sales"] == 2
    prod = (await (await client.get("/api/products?tab=active", headers=owner())).json())["items"][0]
    assert prod["rating"]["count"] == 2
    assert p2


# --- ویترین خصوصی، تاریخ پایان و آرشیو ---
async def test_private_showcase_hidden_from_other_list(env, client):  # noqa: F811
    _, pub = await create(client, title="عمومی")
    _, priv = await create(client, title="خصوصی", private=True)
    store = await (await client.get(f"/api/store/{SHOP_ID}", headers=as_user(BUYER))).json()
    assert [o["title"] for o in store["others"]] == ["عمومی"]
    page = await (await client.get(f"/api/sc/{pub['code']}", headers=as_user(BUYER))).json()
    assert page["others"] == []
    inside = await client.get(f"/api/sc/{priv['code']}", headers=as_user(BUYER))
    assert inside.status == 200                                   # با لینک باز می‌شود
    assert (await inside.json())["others"] == []                  # و ویترین‌های دیگر را لو نمی‌دهد
    assert priv["private"] is True


async def test_expiry_archives_but_buyers_keep_access(env, client):  # noqa: F811
    from datetime import datetime, timedelta, timezone
    from app import showcases
    from app.db import Content
    from tests.test_flows import pay
    c = await make_product(env, price=10, title="موقت")
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    r = await client.patch(f"/api/products/{c.id}", headers=owner(), json={"expires_at": future})
    assert (await r.json())["expires_at"]
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert (await (await client.patch(f"/api/products/{c.id}", headers=owner(), json={"expires_at": past})).json())["error"] == "bad_expiry"
    await pay(env, c, buyer=BUYER, charge="exp-1")
    async with SessionLocal() as s:
        (await s.get(Content, c.id)).expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
        await s.commit()
    assert await showcases.expire_tick(env.manager) == 1
    async with SessionLocal() as s:
        assert not (await s.get(Content, c.id)).is_active                     # رفت به آرشیو
    env.tg.clear()
    await env.feed(env.shop, message(STRANGER, f"/start {c.code}"))
    assert "وجود نداره" in env.tg.texts(SHOP_ID)                           # تازه‌وارد نه
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))
    assert "وجود نداره" not in env.tg.texts(SHOP_ID)                       # خریدار هنوز دسترسی دارد
    # بازگرداندن از آرشیو، تاریخ گذشته را پاک می‌کند
    p = await (await client.patch(f"/api/products/{c.id}", headers=owner(), json={"archived": False})).json()
    assert p["status"] == "active" and p["expires_at"] is None


async def test_takedown_content_never_delivered_even_to_buyers(env, client):  # noqa: F811
    from tests.test_flows import pay
    c = await make_product(env, price=10)
    await pay(env, c, buyer=BUYER, charge="td-x")
    await env.feed(env.main, message(OWNER, f"/takedown https://ble.ir/bot{SHOP_ID}?start={c.code}"))
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))
    assert "وجود نداره" in env.tg.texts(SHOP_ID)


async def test_archived_showcase_keeps_members_and_stops_renewals(env, client):  # noqa: F811
    from app import showcases
    a = await make_product(env, price=10)
    _, sc = await create(client, title="ماهانه", access="monthly", price=40, items=[{"id": a.id}])
    await join_payment(env, sc, charge="sub-a", expires=int(time.time()) + 20 * 86400)
    env.tg.clear()
    r = await client.patch(f"/api/showcases/{sc['id']}", headers=owner(), json={"archived": True})
    assert (await r.json())["archived"] is True
    assert env.tg.sent(SHOP_ID, "EditUserStarSubscription")[-1]["is_canceled"] is True   # دیگر پول نمی‌گیرد
    assert (await client.get(f"/api/sc/{sc['code']}", headers=as_user(BUYER))).status == 200   # عضو می‌ماند
    assert (await (await client.get(f"/api/sc/{sc['code']}", headers=as_user(STRANGER))).json())["error"] == "sc_ended"
    assert (await client.post(f"/api/sc/{sc['code']}/join", headers=as_user(STRANGER))).status == 410
    lst = await (await client.get("/api/showcases", headers=owner())).json()
    assert lst["items"][-1]["archived"] is True
    # فعال کردن دوباره
    assert (await (await client.patch(f"/api/showcases/{sc['id']}", headers=owner(), json={"archived": False})).json())["archived"] is False
    # تاریخ پایان ویترین با حلقه‌ی خودکار
    from datetime import datetime, timedelta
    async with SessionLocal() as s:
        row = await s.get(Showcase, sc["id"])
        row.expires_at = datetime.utcnow() - timedelta(minutes=1)
        await s.commit()
    assert await showcases.expire_tick(env.manager) == 1
    # خریدهای من: عضویت دیده می‌شود
    mine = await (await client.get("/api/purchases", headers=as_user(BUYER, via_shop=False))).json()
    assert mine["memberships"][0]["title"] == "ماهانه" and mine["memberships"][0]["active"] is True


async def test_unarchive_keeps_future_end_date(env, client):  # noqa: F811
    from datetime import datetime, timedelta, timezone
    future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    _, sc = await create(client, title="X", expires_at=future)
    await client.patch(f"/api/showcases/{sc['id']}", headers=owner(), json={"archived": True})
    back = await (await client.patch(f"/api/showcases/{sc['id']}", headers=owner(), json={"archived": False})).json()
    assert back["archived"] is False and back["expires_at"]


async def test_payment_edge_cases(env, client):  # noqa: F811
    """پرداخت تکراری، خرید دوباره، ویترین آرشیوشده، تمدید ویترین بسته و عنوان با < در یادآوری."""
    from tests.test_flows import pay
    c = await make_product(env, price=10)
    first = await pay(env, c, charge="dup-1")
    await pay(env, c, charge="dup-1")                       # تلگرام همان پرداخت را دوباره فرستاد
    async with SessionLocal() as s:
        assert len((await s.scalars(select(Purchase).where(Purchase.charge_id == "dup-1"))).all()) == 1
    env.tg.clear()
    await env.feed(env.shop, {"pre_checkout_query": {"id": "q2", "from": user(BUYER), "currency": "XTR",
                                                    "total_amount": 10, "invoice_payload": f"c:{c.id}"}})
    assert env.tg.sent(SHOP_ID, "AnswerPreCheckoutQuery")[-1]["ok"] is False   # قبلاً خریده
    assert first is not None

    _, sc = await create(client, title="<b>VIP</b> & co", access="monthly", price=20)
    await client.patch(f"/api/showcases/{sc['id']}", headers=owner(), json={"archived": True})
    assert await pre_checkout(env, sc) is False                                # آرشیو: پرداخت تازه نه
    env.tg.clear()
    await join_payment(env, sc, charge="late-renew", expires=int(time.time()) + 30 * 86400)
    assert env.tg.sent(SHOP_ID, "RefundStarPayment")[-1]["telegram_payment_charge_id"] == "late-renew"
    assert any("&lt;b&gt;VIP" in x for x in env.tg.texts(SHOP_ID).split("\n"))
    async with SessionLocal() as s:
        assert await s.scalar(select(Membership).where(Membership.charge_id == "late-renew")) is None
