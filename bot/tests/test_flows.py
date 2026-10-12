"""جریان‌های اصلی ربات از دید فروشنده و خریدار."""
from sqlalchemy import select

from app.db import Content, DeleteJob, Purchase, SessionLocal, Seller, User
from tests.conftest import BUYER, MAIN_ID, OWNER, SHOP_ID, STRANGER, callback, message, photo_message


async def make_product(env, price=10, sensitive=False, allow_save=False, title="محصول تست", category="ai"):
    """فروشنده در ربات فروشگاه آپلود می‌کند و از مسیر چت منتشر می‌کند."""
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        c = await s.scalar(select(Content).order_by(Content.id.desc()))
        c.is_sensitive, c.allow_save, c.title, c.category = sensitive, allow_save, title, category
        await s.commit()
        cid = c.id
    await env.feed(env.shop, callback(OWNER, f"price:{cid}:{price}"))
    async with SessionLocal() as s:
        c = await s.get(Content, cid)
    env.tg.clear()
    return c


async def pay(env, content, buyer=BUYER, charge="ch1"):
    await env.feed(env.shop, message(buyer, successful_payment={
        "currency": "XTR", "total_amount": content.price_stars, "invoice_payload": f"c:{content.id}",
        "telegram_payment_charge_id": charge, "provider_payment_charge_id": "p"}))
    async with SessionLocal() as s:
        return await s.scalar(select(Purchase).where(Purchase.charge_id == charge))


# --- آپلود ---

async def test_main_bot_upload_by_shop_owner_points_to_shop(env):
    """باگ تست ۲: فروشنده اشتباهی در ربات اصلی آپلود کرد و چیزی نپرسید."""
    await env.feed(env.main, photo_message(OWNER))
    assert "لینک ساخته شد" in env.tg.texts(MAIN_ID)
    assert "برای <b>فروش</b>" in env.tg.texts(MAIN_ID)
    urls = [b.get("url", "") for b in env.tg.buttons(MAIN_ID)]
    assert f"https://t.me/bot{SHOP_ID}?start=upload" in urls


async def test_main_bot_upload_without_shop_has_no_sell_hint(env):
    await env.feed(env.main, photo_message(BUYER))
    assert "لینک ساخته شد" in env.tg.texts(MAIN_ID)
    assert "فروش" not in env.tg.texts(MAIN_ID).split("لینک ساخته شد")[1].split("http")[0]
    assert not any("start=upload" in b.get("url", "") for b in env.tg.buttons(MAIN_ID))


async def test_shop_upload_creates_draft_with_mini_app_button(env):
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        c = await s.scalar(select(Content).order_by(Content.id.desc()))
    assert c.is_draft and not c.is_active and c.bot_id == SHOP_ID
    web_apps = [b["web_app"]["url"] for b in env.tg.buttons(SHOP_ID) if "web_app" in b]
    assert web_apps == [f"https://app.example/?p={c.id}&bot={SHOP_ID}"]


async def test_start_upload_prompt(env):
    """دکمه‌ی + در Mini App: قبل از آپلود بگوید فایل را بفرست."""
    await env.feed(env.shop, message(OWNER, "/start upload"))
    assert "فایلی که می‌خوای بفروشی رو همین‌جا بفرست" in env.tg.texts(SHOP_ID)
    env.tg.clear()
    await env.feed(env.shop, message(STRANGER, "/start upload"))
    assert "فقط صاحب این ربات" in env.tg.texts(SHOP_ID)


async def test_stranger_cannot_upload_to_shop(env):
    """غریبه چیزی آپلود نمی‌کند؛ پیامش «پیام به سازنده» است (پیش‌فرض فقط برای فن‌ها)."""
    await env.feed(env.shop, photo_message(STRANGER))
    assert "فقط برای مشترک" in env.tg.texts(SHOP_ID)
    async with SessionLocal() as s:
        assert (await s.scalar(select(Content))) is None


# --- ویترین و پیشنهاد خرید ---

async def test_store_link_and_start_show_store_button(env):
    for text in ("/start store", "/start"):
        env.tg.clear()
        await env.feed(env.shop, message(BUYER, text))
        web_apps = [b["web_app"]["url"] for b in env.tg.buttons(SHOP_ID) if "web_app" in b]
        assert web_apps == [f"https://app.example/?store={SHOP_ID}&bot={SHOP_ID}"], text


async def test_offer_has_preview_more_from_shop_and_invoice(env):
    """باگ تست ۸: دکمه‌ی «محصولات دیگه‌ی این فروشگاه» در پیام فروش."""
    c = await make_product(env, price=10, title="پرتره")
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))
    methods = [m for b, m, _ in env.tg.calls if b == SHOP_ID]
    assert "SendPhoto" in methods                       # پیش‌نمایش تار
    assert methods[-1] == "SendInvoice"                 # فاکتور آخرین پیام
    assert "<b>پرتره</b>" in env.tg.texts(SHOP_ID)
    invoice = env.tg.sent(SHOP_ID, "SendInvoice")[0]
    rows = invoice["reply_markup"]["inline_keyboard"]
    assert rows[0][0]["pay"] is True                                   # تلگرام: اولین دکمه باید پرداخت باشد
    assert rows[1][0]["text"] == "🛍 محصولات دیگه‌ی این فروشگاه"       # زیر خود فاکتور
    assert rows[1][0]["web_app"]["url"].endswith(f"?store={SHOP_ID}&bot={SHOP_ID}")
    assert invoice["currency"] == "XTR" and invoice["prices"][0]["amount"] == 10 and invoice["title"] == "پرتره"


async def test_owner_opening_own_paid_link_gets_content(env):
    c = await make_product(env, price=10)
    await env.feed(env.shop, message(OWNER, f"/start {c.code}"))
    assert env.tg.sent(SHOP_ID, "SendInvoice") == []
    assert env.tg.sent(SHOP_ID, "SendPhoto")[0]["photo"] == c.file_id


# --- خرید، نمایش، بازپرداخت، گزارش ---

async def test_payment_then_show_then_refund_blocked(env):
    c = await make_product(env, price=10)
    p = await pay(env, c)
    assert p is not None and p.opened_at is None
    labels = [b["text"] for b in env.tg.buttons(SHOP_ID)]
    assert "👁 نمایش محتوا" in labels and "↩️ بازپرداخت" in labels
    assert env.tg.sent(SHOP_ID, "SendPhoto") == []      # محتوا قبل از «نمایش» فرستاده نمی‌شود

    await env.feed(env.shop, callback(BUYER, f"open:{p.id}"))
    photo = env.tg.sent(SHOP_ID, "SendPhoto")[-1]
    assert photo["photo"] == c.file_id and photo["protect_content"] is True
    assert "🚩 گزارش مشکل" in [b["text"] for b in env.tg.buttons(SHOP_ID)]

    env.tg.clear()
    await env.feed(env.shop, callback(BUYER, f"refund:{p.id}"))
    assert env.tg.sent(SHOP_ID, "RefundStarPayment") == []
    assert "دیدی" in env.tg.sent(SHOP_ID, "AnswerCallbackQuery")[0]["text"]


async def test_refund_before_viewing(env):
    c = await make_product(env, price=10)
    p = await pay(env, c, charge="ch-refund")
    await env.feed(env.shop, callback(BUYER, f"refund:{p.id}"))
    refund = env.tg.sent(SHOP_ID, "RefundStarPayment")
    assert refund and refund[0]["telegram_payment_charge_id"] == "ch-refund"
    async with SessionLocal() as s:
        assert (await s.get(Purchase, p.id)).refunded
    # بعد از بازپرداخت، لینک دوباره فاکتور می‌دهد
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))
    assert env.tg.sent(SHOP_ID, "SendInvoice")


async def test_allow_save_controls_protection(env):
    c = await make_product(env, price=5, allow_save=True)
    p = await pay(env, c, charge="ch-save")
    await env.feed(env.shop, callback(BUYER, f"open:{p.id}"))
    assert env.tg.sent(SHOP_ID, "SendPhoto")[-1]["protect_content"] is False


async def test_sensitive_content_scheduled_for_deletion(env):
    c = await make_product(env, price=5, sensitive=True, allow_save=True)
    p = await pay(env, c, charge="ch-sens")
    await env.feed(env.shop, callback(BUYER, f"open:{p.id}"))
    assert env.tg.sent(SHOP_ID, "SendPhoto")[-1]["protect_content"] is True   # حساس همیشه محافظت‌شده
    async with SessionLocal() as s:
        assert len((await s.scalars(select(DeleteJob))).all()) == 2           # محتوا + پیام هشدار


async def test_free_link_in_main_bot_is_protected(env):
    await env.feed(env.main, photo_message(BUYER))
    async with SessionLocal() as s:
        c = await s.scalar(select(Content).order_by(Content.id.desc()))
    env.tg.clear()
    await env.feed(env.main, message(STRANGER, f"/start {c.code}"))
    assert env.tg.sent(MAIN_ID, "SendPhoto")[0]["protect_content"] is True


# --- ساخت فروشگاه با یک ضربه ---

async def test_managed_bot_creates_and_connects_shop(env):
    new_bot = {"id": 3000003, "is_bot": True, "first_name": "Shop", "username": "buyer_shop_bot"}
    await env.feed(env.main, {"managed_bot": {"user": {"id": BUYER, "is_bot": False, "first_name": "B"},
                                              "bot_user": new_bot}})
    assert env.tg.sent(MAIN_ID, "GetManagedBotToken")[0]["user_id"] == 3000003
    async with SessionLocal() as s:
        seller = await s.scalar(select(Seller).where(Seller.bot_id == 3000003))
    assert seller and seller.owner_id == BUYER and seller.is_active
    assert 3000003 in env.manager.started
    assert "ساخته و وصل شد" in env.tg.texts(MAIN_ID)
    assert any("ساخته‌شده با @Uploadfly_Bot" in p.get("short_description", "")
               for p in env.tg.sent(3000003, "SetMyShortDescription"))
    # توضیح ربات به زبان هر خریدار
    by_lang = {p.get("language_code"): p["description"] for p in env.tg.sent(3000003, "SetMyDescription")}
    assert {"fa", "en", "ru", "ar", "zh"} <= set(by_lang) and "Добро пожаловать" in by_lang["ru"]


async def test_managed_bot_refused_when_user_already_has_shop(env):
    new_bot = {"id": 3000004, "is_bot": True, "first_name": "Shop2", "username": "owner_second_bot"}
    await env.feed(env.main, {"managed_bot": {"user": {"id": OWNER, "is_bot": False, "first_name": "O"},
                                              "bot_user": new_bot}})
    async with SessionLocal() as s:
        assert await s.scalar(select(Seller).where(Seller.bot_id == 3000004)) is None
    assert "از قبل یک فروشگاه فعال داری" in env.tg.texts(MAIN_ID)


async def test_bot_created_service_message_is_silent(env):
    await env.feed(env.main, message(BUYER, managed_bot_created={"bot_user": {
        "id": 3000005, "is_bot": True, "first_name": "S", "username": "s_bot"}}))
    assert env.tg.sent(MAIN_ID, "SendMessage") == []     # نباید «این نوع پیام پشتیبانی نمی‌شه» بفرستد


async def test_pasting_own_link_opens_it_instead_of_new_link(env):
    """کاربر لینک ربات را کپی و در چت فرستاد؛ نباید «لینکِ لینک» ساخته شود."""
    await env.feed(env.main, photo_message(BUYER))
    async with SessionLocal() as s:
        c = await s.scalar(select(Content).order_by(Content.id.desc()))
    env.tg.clear()
    await env.feed(env.main, message(STRANGER, f"https://t.me/Uploadfly_Bot?start={c.code}"))
    assert env.tg.sent(MAIN_ID, "SendPhoto")[0]["photo"] == c.file_id
    assert "لینک ساخته شد" not in env.tg.texts(MAIN_ID)
    async with SessionLocal() as s:
        assert len((await s.scalars(select(Content))).all()) == 1


async def test_pasting_other_bots_link_is_saved_as_text(env):
    await env.feed(env.main, message(BUYER, "https://t.me/someotherbot?start=abc"))
    assert "لینک ساخته شد" in env.tg.texts(MAIN_ID)


async def test_pasting_paid_link_in_shop_shows_offer(env):
    c = await make_product(env, price=10)
    await env.feed(env.shop, message(BUYER, f"t.me/bot{SHOP_ID}?start={c.code}"))
    assert env.tg.sent(SHOP_ID, "SendInvoice")


async def test_pasting_shop_link_in_main_bot_offers_to_open_it(env):
    """باگ از تست صاحب پروژه: لینک ربات فروشگاه در ربات اصلی، لینک متنی جدید می‌ساخت."""
    c = await make_product(env, price=10)
    await env.feed(env.main, message(BUYER, f"https://t.me/bot{SHOP_ID}?start={c.code}"))
    assert "لینک ساخته شد" not in env.tg.texts(MAIN_ID)
    urls = [b.get("url") for b in env.tg.buttons(MAIN_ID)]
    assert f"https://t.me/bot{SHOP_ID}?start={c.code}" in urls
    async with SessionLocal() as s:
        assert len((await s.scalars(select(Content).where(Content.bot_id == MAIN_ID))).all()) == 0


async def test_pasting_main_link_in_shop_offers_to_open_it(env):
    await env.feed(env.shop, message(OWNER, "https://t.me/Uploadfly_Bot?start=abc123"))
    assert any(b.get("url") == "https://t.me/Uploadfly_Bot?start=abc123" for b in env.tg.buttons(SHOP_ID))
    async with SessionLocal() as s:
        assert (await s.scalar(select(Content))) is None


async def test_pasting_bot_links_without_code(env):
    """از تست صاحب پروژه: لینک فروشگاه با start خالی یا بدون start هم باید شناخته شود."""
    for text in (f"https://t.me/bot{SHOP_ID}?start=", f"t.me/bot{SHOP_ID}", f"https://t.me/bot{SHOP_ID}/"):
        env.tg.clear()
        await env.feed(env.main, message(BUYER, text))
        assert [b.get("url") for b in env.tg.buttons(MAIN_ID)] == [f"https://t.me/bot{SHOP_ID}"], text
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "https://t.me/Uploadfly_Bot?start="))   # لینک خالی خود ربات = /start
    assert "خوش اومدی" in env.tg.texts(MAIN_ID)
    async with SessionLocal() as s:
        assert (await s.scalar(select(Content))) is None
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "https://t.me/durov"))                   # کانال/ربات غریبه: متن عادی
    assert "لینک ساخته شد" in env.tg.texts(MAIN_ID)


async def test_real_length_telegram_ids_are_stored(env):
    """باگ پیدا‌شده هنگام انتقال به PostgreSQL: شناسه‌ی پرداخت واقعی تلگرام ~۱۴۰ کاراکتر است و در
    ستون ۱۲۸تایی جا نمی‌شد. روی سرور یعنی: خریدار پول می‌دهد و خرید ثبت نمی‌شود."""
    c = await make_product(env, price=10)
    long_charge = "stx" + "A1b2C3d4-_" * 15              # ۱۵۳ کاراکتر
    p = await pay(env, c, charge=long_charge)
    assert p is not None and p.charge_id == long_charge
    long_file = "BQACAgIAAxkBAA" + "x" * 300
    await env.feed(env.shop, message(OWNER, document={"file_id": long_file, "file_unique_id": "u-long",
                                                      "file_name": "a.zip", "file_size": 10}))
    async with SessionLocal() as s:
        assert (await s.scalar(select(Content).where(Content.file_unique_id == "u-long"))).file_id == long_file


async def test_open_and_refund_at_the_same_time_only_one_wins(env):
    """هم‌زمانی «نمایش» و «بازپرداخت»: خریدار نباید هم پول را پس بگیرد هم محتوا را."""
    from app.payments import open_purchase, refund_purchase
    c = await make_product(env, price=10)
    p = await pay(env, c, charge="race-1")
    async with SessionLocal() as s_open, SessionLocal() as s_refund:
        stale = await s_open.get(Purchase, p.id)            # «نمایش» قبل از بازپرداخت خوانده شد
        buyer = await s_refund.get(User, BUYER)
        seller = await s_refund.scalar(select(Seller))
        assert await refund_purchase(env.shop, s_refund, await s_refund.get(Purchase, p.id), buyer, seller) is None
        env.tg.clear()
        await open_purchase(env.shop, BUYER, stale, await s_open.get(Content, c.id), s_open, "fa")
        assert env.tg.sent(SHOP_ID, "SendPhoto") == []      # پول برگشت، پس محتوا نه

    p2 = await pay(env, await make_product(env, price=10), charge="race-2")
    async with SessionLocal() as s_open, SessionLocal() as s_refund:
        stale = await s_refund.get(Purchase, p2.id)          # بازپرداخت قبل از نمایش خوانده شد
        await open_purchase(env.shop, BUYER, await s_open.get(Purchase, p2.id),
                            await s_open.get(Content, p2.content_id), s_open, "fa")
        buyer, seller = await s_refund.get(User, BUYER), await s_refund.scalar(select(Seller))
        assert await refund_purchase(env.shop, s_refund, stale, buyer, seller) == "refund_opened"


async def test_tampered_buttons_do_nothing(env):
    """دکمه‌ی دست‌کاری‌شده (با کلاینت غیررسمی): بدون خطا، بدون اثر."""
    for data in ("open:abc", "open:99999999999999999999", "refund:", "rate:x:5", "report:-1", "reportr:1:zzz",
                 "price:1", "price:abc:10", "sens:٣", "save:99999999999"):
        await env.feed(env.shop, callback(BUYER, data))
    async with SessionLocal() as s:
        assert (await s.scalar(select(Purchase))) is None


async def test_paysupport_and_terms(env):
    """تلگرام برای فروش با Stars دستور /paysupport می‌خواهد؛ در ربات فروشنده با راه‌های واقعی کمک."""
    async with SessionLocal() as s:
        (await s.get(User, OWNER)).username = "shop_owner"
        await s.commit()
    await env.feed(env.shop, message(BUYER, "/paysupport"))
    text = env.tg.texts(SHOP_ID)
    assert f"@bot{SHOP_ID}" in text and "@shop_owner" in text and "/terms" in text and "۲۴ ساعت" in text
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "/paysupport"))
    assert "ربات همان فروشگاه" in env.tg.texts(MAIN_ID)
    for bot, bid in ((env.main, MAIN_ID), (env.shop, SHOP_ID)):
        env.tg.clear()
        await env.feed(bot, message(BUYER, "/terms"))
        assert "telegram.org/tos/stars" in env.tg.texts(bid) and "کودکان" in env.tg.texts(bid)


async def test_admin_funnel(env):
    c = await make_product(env, price=10)
    await pay(env, c, buyer=BUYER, charge="fn-1")
    await env.feed(env.main, message(STRANGER, "سلام دنیا"))   # یک لینک رایگان
    env.tg.clear()
    await env.feed(env.main, message(OWNER, "/stats"))
    text = env.tg.texts(MAIN_ID)
    assert "مسیر کاربران" in text and "۷ روز اخیر" in text
    assert "۴. محصول منتشر کردند: 1 (100٪)" in text and "۵. اولین فروش را داشتند: 1 (100٪)" in text
    assert "🛍 خریدار شدند: 1 (33٪)" in text and "۳. فروشگاه ساختند: 1 (33٪)" in text
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "/stats"))                # غیرمدیر
    assert "مسیر کاربران" not in env.tg.texts(MAIN_ID)


async def test_user_source_tracking(env):
    """هر کاربر تازه یک منبع می‌گیرد (اولین تماس)؛ بعداً عوض نمی‌شود."""
    from app.db import User as U
    NEW_AD, NEW_LINK, NEW_SHOP, NEW_DIRECT = 9001, 9002, 9003, 9004
    await env.feed(env.main, message(NEW_AD, "/start src_Insta_Ali"))
    assert "خوش" in env.tg.texts(MAIN_ID) or env.tg.sent(MAIN_ID, "SendMessage")   # خوش‌آمد عادی
    await env.feed(env.main, message(NEW_AD, "/start src_telegram_ads"))          # دومی حساب نمی‌شود
    await env.feed(env.main, message(OWNER, "سلام"))                              # لینک رایگان
    async with SessionLocal() as s:
        code = (await s.scalar(select(Content).where(Content.owner_id == OWNER))).code
    await env.feed(env.main, message(NEW_LINK, f"/start {code}"))
    await env.feed(env.shop, message(NEW_SHOP, "/start store"))
    await env.feed(env.main, message(NEW_DIRECT, "/start"))
    await env.feed(env.main, message(9005, "/start src_<b>x</b>"))
    async with SessionLocal() as s:
        got = {u: (await s.get(U, u)).source for u in (NEW_AD, NEW_LINK, NEW_SHOP, NEW_DIRECT, 9005)}
    assert got == {NEW_AD: "src_insta_ali", NEW_LINK: "link", NEW_SHOP: "shop", NEW_DIRECT: "direct", 9005: "src_other"}
    env.tg.clear()
    await env.feed(env.main, message(OWNER, "/stats"))
    text = env.tg.texts(MAIN_ID)
    assert "منبع کاربران" in text and "🔗 insta_ali: 1 · 0 · 0 · 0" in text and "لینک رایگان: 1" in text
    env.tg.clear()
    await env.feed(env.main, message(OWNER, "/srclink Insta_Ali"))
    assert "https://t.me/Uploadfly_Bot?start=src_insta_ali" in env.tg.texts(MAIN_ID)
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "/srclink x"))                       # فقط مدیر
    assert "start=src_x" not in env.tg.texts(MAIN_ID)


async def test_stars_guide(env):
    c = await make_product(env, price=10)
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))
    assert "/stars" in env.tg.texts(SHOP_ID)                                    # زیر پیشنهاد خرید
    env.tg.clear()
    msg = message(BUYER, "/stars")
    msg["message"]["from"]["username"] = "buyer_one"
    await env.feed(env.shop, msg)
    text = env.tg.texts(SHOP_ID)
    assert "@buyer_one" in text and "کد ورود" in text and "تومان" in text
    env.tg.clear()
    await env.feed(env.shop, message(STRANGER, "/stars"))                       # بدون یوزرنیم
    assert "یوزرنیم بساز" in env.tg.texts(SHOP_ID)
