"""ضدکلاهبرداری: سقف قیمت تدریجی، لیست سیاه، حذف خودکار با گزارش، دستورهای مدیر، کاربر مسدود."""
from sqlalchemy import select

from app.db import Blacklist, Content, SessionLocal, User
from app.trust import price_cap
from tests.conftest import BUYER, MAIN_ID, OWNER, SHOP_ID, STRANGER, callback, message
from tests.test_flows import make_product, pay
from tests.test_web import as_user, client  # noqa: F401  (fixture)


def same_file_photo(uid: int, unique: str) -> dict:
    return message(uid, photo=[{"file_id": f"f-{unique}-{uid}", "file_unique_id": unique,
                                "width": 100, "height": 100, "file_size": 1000}])


async def test_new_seller_price_cap_in_chat(env):
    await env.feed(env.shop, same_file_photo(OWNER, "cap-1"))
    prices = [b["text"] for b in env.tg.buttons(SHOP_ID)]
    async with SessionLocal() as s:
        c = await s.scalar(select(Content).order_by(Content.id.desc()))
        assert await price_cap(s, SHOP_ID) == 100
    await env.feed(env.shop, callback(OWNER, f"chatprice:{c.id}"))
    prices = [b["text"] for b in env.tg.buttons(SHOP_ID)]
    assert "100 ⭐" in prices and "250 ⭐" not in prices
    await env.feed(env.shop, callback(OWNER, f"price:{c.id}:250"))      # دکمه‌ی دست‌کاری‌شده
    async with SessionLocal() as s:
        assert (await s.get(Content, c.id)).is_draft


async def test_price_cap_rises_with_sales_and_blocks_api(env, client):  # noqa: F811
    c = await make_product(env, price=10)
    h = as_user(OWNER, via_shop=False)
    r = await client.patch(f"/api/products/{c.id}", headers=h, json={"price": 500})
    assert r.status == 400 and (await r.json())["error"] == "price_cap"
    for i in range(5):
        await pay(env, c, buyer=600 + i, charge=f"cap-{i}")
    async with SessionLocal() as s:
        assert await price_cap(s, SHOP_ID) == 300
    assert (await client.patch(f"/api/products/{c.id}", headers=h, json={"price": 300})).status == 200
    me = await (await client.get("/api/me", headers=h)).json()
    assert me["shop"]["price_cap"] == 300


async def report(env, buyer, purchase_id, reason):
    await env.feed(env.shop, callback(buyer, f"report:{purchase_id}"))
    await env.feed(env.shop, callback(buyer, f"reportr:{purchase_id}:{reason}"))


async def test_reports_ask_reason_and_never_act_automatically(env):
    """گزارش‌ها دلیل دارند و هیچ کار خودکاری نمی‌کنند: نه حذف، نه تعلیق، نه پایین آمدن سقف قیمت."""
    from app.db import Purchase, Seller
    c = await make_product(env, price=1)
    purchases = []
    for i in range(6):
        p = await pay(env, c, buyer=800 + i, charge=f"td-{i}")
        await env.feed(env.shop, callback(800 + i, f"open:{p.id}"))
        purchases.append(p)
    env.tg.clear()
    await env.feed(env.shop, callback(800, f"report:{purchases[0].id}"))
    assert [b["text"] for b in env.tg.buttons(SHOP_ID)] == [
        "با توضیحات فرق داشت", "فایل خراب یا ناقص بود", "محتوای ممنوع", "مشکل دیگه"]
    await env.feed(env.shop, callback(800, f"reportr:{purchases[0].id}:hacked"))   # دلیل دست‌کاری‌شده
    async with SessionLocal() as s:
        assert (await s.get(Purchase, purchases[0].id)).reported_at is None
    for i, p in enumerate(purchases):
        await report(env, 800 + i, p.id, "mismatch")
    await report(env, 900, purchases[1].id, "broken")   # خریدار دیگری نمی‌تواند خرید کس دیگر را گزارش کند
    async with SessionLocal() as s:
        assert (await s.get(Content, c.id)).is_active
        assert not await s.get(Blacklist, c.file_unique_id)
        assert not (await s.scalar(select(Seller).where(Seller.bot_id == SHOP_ID))).is_suspended
        assert await price_cap(s, SHOP_ID) == 300   # ۶ فروش؛ ۱۰۰٪ گزارش اثری ندارد
        p = await s.get(Purchase, purchases[1].id)
        assert p.report_reason == "mismatch"
    assert "گزارش‌ها توسط UploadFly بررسی می‌شن" in env.tg.texts(SHOP_ID)
    assert not env.tg.sent(MAIN_ID, "SendMessage")   # برای «فرق با توضیحات» به مدیر پیام فوری نمی‌رود


async def test_forbidden_report_alerts_admin_and_reports_list(env):
    c = await make_product(env, price=10)
    p = await pay(env, c, buyer=BUYER, charge="fb-1")
    await env.feed(env.shop, callback(BUYER, f"open:{p.id}"))
    env.tg.clear()
    await report(env, BUYER, p.id, "forbidden")
    alert = [m for m in env.tg.sent(MAIN_ID, "SendMessage") if m["chat_id"] == OWNER]   # OWNER مدیر تست است
    assert alert and "گزارش محتوای ممنوع" in alert[0]["text"] and c.code in alert[0]["text"]
    env.tg.clear()
    await env.feed(env.main, message(OWNER, "/reports"))
    text = env.tg.texts(MAIN_ID)
    assert f"@bot{SHOP_ID}" in text and "ممنوع 1" in text and c.code in text
    await env.feed(env.main, message(STRANGER, "/reports"))   # غیرمدیر
    assert env.tg.texts(MAIN_ID).count("گزارش‌های ۳۰ روز اخیر") == 1


async def test_admin_suspend_and_unsuspend(env):
    from app.db import Seller
    c = await make_product(env, price=10)
    await env.feed(env.main, message(OWNER, f"/suspend @bot{SHOP_ID}"))
    async with SessionLocal() as s:
        assert (await s.scalar(select(Seller).where(Seller.bot_id == SHOP_ID))).is_suspended
    assert "نقض قوانین UploadFly تعلیق شد" in env.tg.texts(MAIN_ID)
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))   # خرید ممکن نیست
    assert not env.tg.sent(SHOP_ID, "SendInvoice")
    await env.feed(env.main, message(OWNER, f"/unsuspend bot{SHOP_ID}"))
    async with SessionLocal() as s:
        assert not (await s.scalar(select(Seller).where(Seller.bot_id == SHOP_ID))).is_suspended
    await env.feed(env.main, message(OWNER, "/suspend @nobody"))
    assert "فروشگاه پیدا نشد" in env.tg.texts(MAIN_ID)


async def test_blacklisted_file_rejected_everywhere(env):
    async with SessionLocal() as s:
        s.add(Blacklist(file_unique_id="bad-file", reason="admin"))
        await s.commit()
    await env.feed(env.shop, same_file_photo(OWNER, "bad-file"))
    await env.feed(env.main, same_file_photo(BUYER, "bad-file"))
    assert env.tg.texts().count("مسدود شده و قابل آپلود نیست") == 2
    async with SessionLocal() as s:
        assert (await s.scalar(select(Content))) is None


async def test_admin_takedown_by_link(env):
    c = await make_product(env, price=10)
    await env.feed(env.main, message(OWNER, f"/takedown https://t.me/bot{SHOP_ID}?start={c.code}"))
    assert "حذف شد" in env.tg.texts(MAIN_ID)
    async with SessionLocal() as s:
        assert not (await s.get(Content, c.id)).is_active
        assert await s.get(Blacklist, c.file_unique_id)


async def test_non_admin_cannot_use_admin_commands(env):
    c = await make_product(env, price=10)
    await env.feed(env.main, message(STRANGER, f"/takedown {c.code}"))
    await env.feed(env.main, message(STRANGER, f"/ban {OWNER}"))
    async with SessionLocal() as s:
        assert (await s.get(Content, c.id)).is_active
        assert not (await s.get(User, OWNER)).is_banned
    assert "این دستور رو نمی‌شناسم" in env.tg.texts(MAIN_ID)


async def test_ban_blocks_bot_and_mini_app(env, client):  # noqa: F811
    await env.feed(env.main, message(OWNER, "/ban @stranger"))
    assert "مسدود شد" in env.tg.texts(MAIN_ID)
    env.tg.clear()
    await env.feed(env.main, message(STRANGER, "/start"))
    assert env.tg.sent(MAIN_ID) == []                                        # ربات جوابش را نمی‌دهد
    r = await client.get("/api/me", headers=as_user(STRANGER, via_shop=False))
    assert r.status == 403 and (await r.json())["error"] == "banned"
    await env.feed(env.main, message(OWNER, f"/unban {STRANGER}"))
    async with SessionLocal() as s:
        assert not (await s.get(User, STRANGER)).is_banned


async def test_ban_seller_closes_shop(env):
    await env.feed(env.main, message(OWNER, "/stats"))
    assert "آمار UploadFly" in env.tg.texts(MAIN_ID)
    # مدیر خودش را نمی‌تواند مسدود کند؛ فروشنده‌ی دیگری می‌سازیم
    new_bot = {"id": 3000009, "is_bot": True, "first_name": "S", "username": "buyer_shop_bot"}
    await env.feed(env.main, {"managed_bot": {"user": {"id": BUYER, "is_bot": False, "first_name": "B"},
                                              "bot_user": new_bot}})
    await env.feed(env.main, message(OWNER, f"/ban {BUYER}"))
    from app.db import Seller
    async with SessionLocal() as s:
        seller = await s.scalar(select(Seller).where(Seller.bot_id == 3000009))
    assert not seller.is_active and "فروشگاه @buyer_shop_bot قطع شد" in env.tg.texts(MAIN_ID)


async def test_admin_usage_messages_are_valid_html(env):
    """باگ واقعی: «/takedown» بدون لینک، به‌خاطر «<لینک یا کد>» در HTML خطا می‌داد و جوابی نمی‌آمد."""
    for cmd in ("/takedown", "/ban", "/unban", "/takedown nonexistent"):
        env.tg.clear()
        await env.feed(env.main, message(OWNER, cmd))
        assert env.tg.sent(MAIN_ID, "SendMessage"), cmd


async def test_refund_test_payments_command(env):
    """مدیر (صاحب فروشگاه) همه‌ی پرداخت‌های فروشگاه خودش را با تأیید برمی‌گرداند."""
    from sqlalchemy import select as _select
    from app.db import Purchase as _P, SessionLocal as _S
    from tests.conftest import BUYER, MAIN_ID, OWNER, SHOP_ID, STRANGER, callback, message
    from tests.test_flows import make_product, pay
    c1, c2 = await make_product(env, price=10), await make_product(env, price=5)
    await pay(env, c1, buyer=BUYER, charge="t-1")
    await pay(env, c2, buyer=BUYER, charge="t-2")
    env.tg.clear()
    await env.feed(env.main, message(STRANGER, "/refundtests"))           # غیرمدیر: هیچ
    assert "برگرداندن" not in env.tg.texts(MAIN_ID)
    await env.feed(env.main, message(OWNER, "/refundtests"))
    assert "2 خرید" in env.tg.texts(MAIN_ID) and "15 ⭐" in env.tg.texts(MAIN_ID)
    await env.feed(env.main, callback(OWNER, "rft:no"))
    assert env.tg.sent(SHOP_ID, "RefundStarPayment") == []
    await env.feed(env.main, callback(STRANGER, "rft:yes"))               # دکمه با حساب دیگر: هیچ
    assert env.tg.sent(SHOP_ID, "RefundStarPayment") == []
    await env.feed(env.main, callback(OWNER, "rft:yes"))
    sent = env.tg.sent(SHOP_ID, "RefundStarPayment")
    assert sorted(x["telegram_payment_charge_id"] for x in sent) == ["t-1", "t-2"]
    assert all(x["user_id"] == BUYER for x in sent)
    async with _S() as s:
        assert all(p.refunded for p in (await s.scalars(_select(_P))).all())
    env.tg.clear()
    await env.feed(env.main, message(OWNER, "/refundtests"))               # دوباره: چیزی نمانده
    assert "پرداخت بازپرداخت‌نشده‌ای نیست" in env.tg.texts(MAIN_ID)
