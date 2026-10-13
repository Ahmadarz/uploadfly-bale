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
    assert f"https://ble.ir/bot{SHOP_ID}?start=upload" in urls


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
    assert "می‌خوای بفروشی رو همین‌جا بفرست" in env.tg.texts(SHOP_ID)
    env.tg.clear()
    await env.feed(env.shop, message(STRANGER, "/start upload"))
    assert "فقط صاحب این بازو" in env.tg.texts(SHOP_ID)


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


# --- ساخت فروشگاه در بله: توکن بازو، بعد توکن کیف پول ---

async def test_connect_asks_bot_token_then_wallet_token(env):
    token = "3000003:" + "C" * 35
    await env.feed(env.main, message(BUYER, "/connect"))
    assert "botfather" in env.tg.texts(MAIN_ID) and env.tg.buttons(MAIN_ID)[0]["url"] == "https://ble.ir/botfather"
    env.tg.clear()
    await env.feed(env.main, message(BUYER, token))
    assert env.tg.sent(MAIN_ID, "DeleteMessage")                      # توکن در چت نمی‌ماند
    async with SessionLocal() as s:
        seller = await s.scalar(select(Seller).where(Seller.bot_id == 3000003))
    assert seller and seller.owner_id == BUYER and seller.is_active and seller.wallet_enc is None
    assert 3000003 in env.manager.started and "توکن پرداخت کیف پول" in env.tg.texts(MAIN_ID)
    # توکن کیف پول نامعتبر (شکل اشتباه) رد می‌شود و حالت می‌ماند
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "توکن غلط با فاصله"))
    assert "کار نکرد" in env.tg.texts(MAIN_ID)
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "WALLET-TEST-1111111111111111"))
    assert env.tg.sent(MAIN_ID, "DeleteMessage") and "ثبت شد" in env.tg.texts(MAIN_ID)
    assert env.tg.sent(3000003, "CreateInvoiceLink")                  # توکن با یک فاکتور آزمایشی سنجیده شد
    async with SessionLocal() as s:
        seller = await s.scalar(select(Seller).where(Seller.bot_id == 3000003))
    from app.crypto import decrypt
    assert decrypt(seller.wallet_enc) == "WALLET-TEST-1111111111111111"
    assert "WALLET-TEST" not in env.tg.texts()                        # توکن در هیچ پیامی تکرار نمی‌شود


async def test_wallet_can_be_skipped_and_then_paid_price_is_blocked(env):
    async with SessionLocal() as s:
        seller = await s.scalar(select(Seller).where(Seller.bot_id == SHOP_ID))
        seller.wallet_enc = None
        await s.commit()
    await env.feed(env.main, message(OWNER, "/wallet"))
    await env.feed(env.main, message(OWNER, "/skip"))
    assert "فقط محتوای رایگان" in env.tg.texts(MAIN_ID)
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        c = await s.scalar(select(Content).order_by(Content.id.desc()))
    env.tg.clear()
    await env.feed(env.shop, callback(OWNER, f"price:{c.id}:10"))
    assert "/wallet" in env.tg.texts(SHOP_ID)
    async with SessionLocal() as s:
        assert (await s.get(Content, c.id)).is_draft                  # منتشر نشد
    await env.feed(env.shop, callback(OWNER, f"price:{c.id}:0"))      # رایگان بدون کیف پول هم می‌شود
    async with SessionLocal() as s:
        assert not (await s.get(Content, c.id)).is_draft


async def test_wallet_command_needs_a_shop(env):
    await env.feed(env.main, message(STRANGER, "/wallet"))
    assert "/connect" in env.tg.texts(MAIN_ID)


async def test_connect_refused_when_user_already_has_shop(env):
    await env.feed(env.main, message(OWNER, "/connect"))
    assert "الان وصله" in env.tg.texts(MAIN_ID)

async def test_pasting_own_link_opens_it_instead_of_new_link(env):
    """کاربر لینک ربات را کپی و در چت فرستاد؛ نباید «لینکِ لینک» ساخته شود."""
    await env.feed(env.main, photo_message(BUYER))
    async with SessionLocal() as s:
        c = await s.scalar(select(Content).order_by(Content.id.desc()))
    env.tg.clear()
    await env.feed(env.main, message(STRANGER, f"https://ble.ir/Uploadfly_Bot?start={c.code}"))
    assert env.tg.sent(MAIN_ID, "SendPhoto")[0]["photo"] == c.file_id
    assert "لینک ساخته شد" not in env.tg.texts(MAIN_ID)
    async with SessionLocal() as s:
        assert len((await s.scalars(select(Content))).all()) == 1


async def test_pasting_other_bots_link_is_saved_as_text(env):
    await env.feed(env.main, message(BUYER, "https://ble.ir/someotherbot?start=abc"))
    assert "لینک ساخته شد" in env.tg.texts(MAIN_ID)


async def test_pasting_paid_link_in_shop_shows_offer(env):
    c = await make_product(env, price=10)
    await env.feed(env.shop, message(BUYER, f"t.me/bot{SHOP_ID}?start={c.code}"))
    assert env.tg.sent(SHOP_ID, "SendInvoice")


async def test_pasting_shop_link_in_main_bot_offers_to_open_it(env):
    """باگ از تست صاحب پروژه: لینک ربات فروشگاه در ربات اصلی، لینک متنی جدید می‌ساخت."""
    c = await make_product(env, price=10)
    await env.feed(env.main, message(BUYER, f"https://ble.ir/bot{SHOP_ID}?start={c.code}"))
    assert "لینک ساخته شد" not in env.tg.texts(MAIN_ID)
    urls = [b.get("url") for b in env.tg.buttons(MAIN_ID)]
    assert f"https://ble.ir/bot{SHOP_ID}?start={c.code}" in urls
    async with SessionLocal() as s:
        assert len((await s.scalars(select(Content).where(Content.bot_id == MAIN_ID))).all()) == 0


async def test_pasting_main_link_in_shop_offers_to_open_it(env):
    await env.feed(env.shop, message(OWNER, "https://ble.ir/Uploadfly_Bot?start=abc123"))
    assert any(b.get("url") == "https://ble.ir/Uploadfly_Bot?start=abc123" for b in env.tg.buttons(SHOP_ID))
    async with SessionLocal() as s:
        assert (await s.scalar(select(Content))) is None


async def test_pasting_bot_links_without_code(env):
    """از تست صاحب پروژه: لینک فروشگاه با start خالی یا بدون start هم باید شناخته شود."""
    for text in (f"https://ble.ir/bot{SHOP_ID}?start=", f"t.me/bot{SHOP_ID}", f"https://ble.ir/bot{SHOP_ID}/"):
        env.tg.clear()
        await env.feed(env.main, message(BUYER, text))
        assert [b.get("url") for b in env.tg.buttons(MAIN_ID)] == [f"https://ble.ir/bot{SHOP_ID}"], text
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "https://ble.ir/Uploadfly_Bot?start="))   # لینک خالی خود ربات = /start
    assert "خوش اومدی" in env.tg.texts(MAIN_ID)
    async with SessionLocal() as s:
        assert (await s.scalar(select(Content))) is None
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "https://ble.ir/durov"))                   # کانال/ربات غریبه: متن عادی
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
    assert f"@bot{SHOP_ID}" in text and "@shop_owner" in text and "/terms" in text and "کیف پول" in text
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "/paysupport"))
    assert "بازوی همان فروشگاه" in env.tg.texts(MAIN_ID)
    for bot, bid in ((env.main, MAIN_ID), (env.shop, SHOP_ID)):
        env.tg.clear()
        await env.feed(bot, message(BUYER, "/terms"))
        assert "کیف پول بله" in env.tg.texts(bid) and "ممنوع" in env.tg.texts(bid)


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
    assert "https://ble.ir/Uploadfly_Bot?start=src_insta_ali" in env.tg.texts(MAIN_ID)
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "/srclink x"))                       # فقط مدیر
    assert "start=src_x" not in env.tg.texts(MAIN_ID)


async def test_payment_guide(env):
    c = await make_product(env, price=10)
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))
    assert "کیف پول بله" in env.tg.texts(SHOP_ID)                               # زیر پیشنهاد خرید
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, "/stars"))
    assert "کیف پول بله" in env.tg.texts(SHOP_ID) and "استارز" not in env.tg.texts(SHOP_ID)


async def test_without_refunds_content_is_delivered_right_after_payment(env, monkeypatch):
    """بله (پیش‌فرض): بازپرداخت خودکار خاموش است؛ خریدار بعد از پرداخت محتوا را مستقیم می‌گیرد."""
    import dataclasses

    from app import payments
    monkeypatch.setattr(payments, "settings", dataclasses.replace(payments.settings, refunds=False))
    c = await make_product(env, price=10)
    env.tg.clear()
    purchase = await pay(env, c, charge="no-refund-1")
    assert env.tg.sent(SHOP_ID, "SendPhoto")                                   # محتوا تحویل شد
    assert not any(b.get("callback_data", "").startswith("refund:") for b in env.tg.buttons(SHOP_ID))
    async with SessionLocal() as s:
        assert (await s.get(Purchase, purchase.id)).opened_at is not None
    await env.feed(env.shop, callback(BUYER, f"refund:{purchase.id}"))         # دکمه‌ی قدیمی/دست‌کاری‌شده
    assert not env.tg.sent(SHOP_ID, "RefundStarPayment")


async def test_welcome_has_a_mini_app_button(env):
    """بله دکمه‌ی منوی مینی‌اپ را از طریق API نمی‌گذارد؛ خوش‌آمد خودش دکمه‌ی مینی‌اپ دارد."""
    await env.feed(env.main, message(STRANGER, "/start"))
    urls = [b["web_app"]["url"] for b in env.tg.buttons(MAIN_ID) if b.get("web_app")]
    assert urls == ["https://app.example"]
