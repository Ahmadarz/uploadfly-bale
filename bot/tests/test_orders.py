"""کالای فیزیکی: انتشار، کارت محصول، فرم سفارش با نشانی، فاکتور با هزینه‌ی ارسال، خبر به فروشنده،
کد رهگیری، موجودی، گزارش «نرسیده» و مینی‌اپ."""
from sqlalchemy import select

from app.db import Content, Order, Purchase, Seller, SessionLocal
from app.orders import clean_phone, clean_postal
from tests.conftest import BUYER, MAIN_ID, OWNER, SHOP_ID, STRANGER, callback, message, photo_message
from tests.test_web import as_user, client  # noqa: F401  (fixture)


async def make_physical(env, price=50, caption="کیف چرمی دست‌دوز"):
    """فروشنده عکس کالا را می‌فرستد، «کالای فیزیکی» را روشن و قیمت را انتخاب می‌کند."""
    upd = photo_message(OWNER)
    upd["message"]["caption"] = caption
    await env.feed(env.shop, upd)
    async with SessionLocal() as s:
        cid = (await s.scalar(select(Content).order_by(Content.id.desc()))).id
    await env.feed(env.shop, callback(OWNER, f"phys:{cid}"))
    await env.feed(env.shop, callback(OWNER, f"price:{cid}:{price}"))
    async with SessionLocal() as s:
        c = await s.get(Content, cid)
    env.tg.clear()
    return c


async def fill_form(env, c, buyer=BUYER, postal="1234567890"):
    await env.feed(env.shop, callback(buyer, f"order:{c.id}"))
    for text in ("علی رضایی", "۰۹۱۲ ۳۴۵ ۶۷۸۹", "تهران، خیابان ولیعصر، کوچه‌ی یکم، پلاک ۱۲، واحد ۳", postal):
        await env.feed(env.shop, message(buyer, text))
    async with SessionLocal() as s:
        return await s.scalar(select(Order).where(Order.buyer_id == buyer).order_by(Order.id.desc()))


async def pay_order(env, order, buyer=BUYER, charge="ord-1", amount=None):
    await env.feed(env.shop, message(buyer, successful_payment={
        "currency": "XTR", "total_amount": order.amount if amount is None else amount,
        "invoice_payload": f"o:{order.id}", "telegram_payment_charge_id": charge, "provider_payment_charge_id": ""}))


async def pre_checkout(env, order, amount, buyer=BUYER):
    env.tg.clear()
    await env.feed(env.shop, {"pre_checkout_query": {"id": "q1", "from": {"id": buyer, "is_bot": False, "first_name": "B"},
                                                     "currency": "XTR", "total_amount": amount,
                                                     "invoice_payload": f"o:{order.id}"}})
    return env.tg.sent(SHOP_ID, "AnswerPreCheckoutQuery")[-1]["ok"]


def test_phone_and_postal_are_normalised():
    assert clean_phone("۰۹۱۲ ۳۴۵ ۶۷۸۹") == "09123456789" and clean_phone("+98 912-345-6789") == "09123456789"
    assert clean_phone("0912345678") is None and clean_phone("02112345678") is None and clean_phone("سلام") is None
    assert clean_postal("۱۲۳۴۵-۶۷۸۹۰") == "1234567890" and clean_postal("12345") is None


async def test_seller_publishes_a_physical_product_without_blurred_preview(env):
    upd = photo_message(OWNER)
    upd["message"]["caption"] = "کیف چرمی"
    await env.feed(env.shop, upd)
    async with SessionLocal() as s:
        cid = (await s.scalar(select(Content).order_by(Content.id.desc()))).id
    await env.feed(env.shop, callback(OWNER, f"chatprice:{cid}"))
    assert any(b.get("callback_data") == f"phys:{cid}" and "خاموش" in b["text"] for b in env.tg.buttons(SHOP_ID))
    await env.feed(env.shop, callback(OWNER, f"phys:{cid}"))
    env.tg.clear()
    await env.feed(env.shop, callback(OWNER, f"price:{cid}:0"))           # کالای رایگان نه
    async with SessionLocal() as s:
        assert (await s.get(Content, cid)).is_draft
    await env.feed(env.shop, callback(OWNER, f"price:{cid}:50"))
    async with SessionLocal() as s:
        c = await s.get(Content, cid)
    assert c.is_physical and not c.is_draft and c.price_stars == 50 and c.preview is None
    assert not env.tg.sent(SHOP_ID, "SendPhoto")                           # پیش‌نمایش تار ساخته نشد
    text = env.tg.texts(SHOP_ID)
    assert "کالای فیزیکی" in text and "/orders" in text
    post = [b["copy_text"]["text"] for b in env.tg.buttons(SHOP_ID) if b.get("copy_text")][-1]
    assert "سفارش و پرداخت در بله" in post


async def test_buyer_sees_the_real_photo_and_order_button(env):
    c = await make_physical(env)
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))
    (card,) = env.tg.sent(SHOP_ID, "SendPhoto")
    assert card["photo"] == c.file_id and "کیف چرمی" in card["caption"] and "50 تومان" in card["caption"]
    assert "ارسال رایگان" in card["caption"]
    assert card["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == f"order:{c.id}"
    assert not env.tg.sent(SHOP_ID, "SendInvoice")                         # فاکتور بعد از گرفتن نشانی
    env.tg.clear()
    await env.feed(env.shop, message(OWNER, f"/start {c.code}"))           # خود فروشنده: دکمه‌ی موجودی
    (card,) = env.tg.sent(SHOP_ID, "SendPhoto")
    assert card["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == f"stock:{c.id}"


async def test_order_form_invoice_payment_and_shipping(env):
    async with SessionLocal() as s:
        (await s.scalar(select(Seller).where(Seller.bot_id == SHOP_ID))).shipping_fee = 30
        await s.commit()
    c = await make_physical(env, price=50)
    await env.feed(env.shop, callback(BUYER, f"order:{c.id}"))
    assert "۱ از ۴" in env.tg.texts(SHOP_ID)
    await env.feed(env.shop, message(BUYER, "ع"))                          # نام خیلی کوتاه
    await env.feed(env.shop, message(BUYER, "علی رضایی"))
    await env.feed(env.shop, message(BUYER, "12345"))                      # موبایل غلط
    assert "شماره درست نیست" in env.tg.texts(SHOP_ID)
    await env.feed(env.shop, message(BUYER, "۰۹۱۲ ۳۴۵ ۶۷۸۹"))
    await env.feed(env.shop, message(BUYER, "تهران، خیابان ولیعصر، کوچه‌ی یکم، پلاک ۱۲، واحد ۳"))
    await env.feed(env.shop, message(BUYER, "1234"))                       # کد پستی غلط
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, "1234567890"))
    (inv,) = env.tg.sent(SHOP_ID, "SendInvoice")
    async with SessionLocal() as s:
        order = await s.scalar(select(Order))
    assert (order.status, order.amount, order.shipping_fee, order.phone) == ("pending", 80, 30, "09123456789")
    assert inv["payload"] == f"o:{order.id}" and [p["amount"] for p in inv["prices"]] == [50, 30]
    assert "جمع: 80 تومان" in env.tg.texts(SHOP_ID) and "ولیعصر" in env.tg.texts(SHOP_ID)
    # پیام‌های فرم برای فروشنده فرستاده نشد (پیام خصوصی حساب نشد)
    assert not [m for m in env.tg.sent(SHOP_ID) if m.get("chat_id") == OWNER]

    assert await pre_checkout(env, order, 80) is True
    assert await pre_checkout(env, order, 50) is False                     # مبلغ دست‌کاری‌شده
    assert await pre_checkout(env, order, 80, buyer=STRANGER) is False     # سفارش کس دیگر
    env.tg.clear()
    await pay_order(env, order)
    await pay_order(env, order)                                            # پیام تکراری بله: یک خرید
    async with SessionLocal() as s:
        order = await s.get(Order, order.id)
        purchases = (await s.scalars(select(Purchase))).all()
    assert order.status == "paid" and len(purchases) == 1 and purchases[0].amount == 80
    to_owner = [m for m in env.tg.sent(SHOP_ID, "SendMessage") if m["chat_id"] == OWNER]
    assert len(to_owner) == 1 and "علی رضایی" in to_owner[0]["text"] and "09123456789" in to_owner[0]["text"]
    assert "ولیعصر" in to_owner[0]["text"] and not to_owner[0].get("disable_notification")
    assert to_owner[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == f"ship:{order.id}"
    assert "ثبت و پرداخت شد" in env.tg.texts(SHOP_ID)
    assert await pre_checkout(env, order, 80) is False                     # سفارش پرداخت‌شده دوباره پرداخت نمی‌شود

    # فروشنده ارسال را با کد رهگیری ثبت می‌کند؛ خریدار باخبر می‌شود
    await env.feed(env.shop, callback(STRANGER, f"ship:{order.id}"))       # غریبه: هیچ
    await env.feed(env.shop, callback(OWNER, f"ship:{order.id}"))
    env.tg.clear()
    await env.feed(env.shop, message(OWNER, "۱۲۳۴۵۶۷۸۹۰۱۲۳۴۵۶۷۸۹۰"))
    async with SessionLocal() as s:
        order = await s.get(Order, order.id)
        assert order.status == "shipped" and order.tracking == "12345678901234567890"
        assert (await s.scalar(select(Content).where(Content.id == c.id))).is_active
        # کد رهگیری «محصول تازه» نشد
        assert len((await s.scalars(select(Content))).all()) == 1
    to_buyer = [m for m in env.tg.sent(SHOP_ID, "SendMessage") if m["chat_id"] == BUYER]
    assert "ارسال شد" in to_buyer[0]["text"] and "12345678901234567890" in to_buyer[0]["text"]
    assert any(b.get("callback_data", "").startswith("rate:") for b in to_buyer[0]["reply_markup"]["inline_keyboard"][0])
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, "/orders"))
    assert "ارسال شد" in env.tg.texts(SHOP_ID) and f"#{order.id}" in env.tg.texts(SHOP_ID)


async def test_orders_list_and_shipping_without_tracking(env):
    c = await make_physical(env)
    order = await fill_form(env, c)
    await pay_order(env, order)
    env.tg.clear()
    await env.feed(env.shop, message(OWNER, "/orders"))
    assert "منتظر ارسال" in env.tg.texts(SHOP_ID) and "علی رضایی" in env.tg.texts(SHOP_ID)
    assert env.tg.buttons(SHOP_ID)[0]["callback_data"] == f"ship:{order.id}"
    await env.feed(env.shop, callback(OWNER, f"shipnow:{order.id}"))
    async with SessionLocal() as s:
        order = await s.get(Order, order.id)
    assert order.status == "shipped" and order.tracking is None
    assert "کد رهگیری ثبت نکرده" in env.tg.texts(SHOP_ID)
    env.tg.clear()
    await env.feed(env.shop, message(OWNER, "/orders"))
    assert "نداری" in env.tg.texts(SHOP_ID)


async def test_same_buyer_can_order_again_with_the_saved_address(env):
    c = await make_physical(env)
    first = await fill_form(env, c)
    await pay_order(env, first, charge="again-1")
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))           # دوباره کارت و دکمه‌ی سفارش، نه «قبلاً خریدی»
    assert env.tg.sent(SHOP_ID, "SendPhoto")[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == f"order:{c.id}"
    env.tg.clear()
    await env.feed(env.shop, callback(BUYER, f"order:{c.id}"))
    assert "همین نشانی قبلی" in env.tg.texts(SHOP_ID) and "ولیعصر" in env.tg.texts(SHOP_ID)
    await env.feed(env.shop, callback(BUYER, f"ordersame:{c.id}"))
    async with SessionLocal() as s:
        orders = (await s.scalars(select(Order).order_by(Order.id))).all()
    assert len(orders) == 2 and orders[1].status == "pending" and orders[1].address == orders[0].address
    await pay_order(env, orders[1], charge="again-2")
    async with SessionLocal() as s:
        assert len((await s.scalars(select(Purchase))).all()) == 2


async def test_stock_runs_out_and_blocks_new_orders(env):
    c = await make_physical(env)
    await env.feed(env.shop, callback(BUYER, f"stock:{c.id}"))             # خریدار نمی‌تواند موجودی را عوض کند
    await env.feed(env.shop, callback(OWNER, f"stock:{c.id}"))
    await env.feed(env.shop, message(OWNER, "۱"))
    async with SessionLocal() as s:
        assert (await s.get(Content, c.id)).stock == 1
    order = await fill_form(env, c)
    other = await fill_form(env, c, buyer=STRANGER)                        # دو نفر هم‌زمان فرم را پر کرده‌اند
    await pay_order(env, order, charge="st-1")
    async with SessionLocal() as s:
        assert (await s.get(Content, c.id)).stock == 0
    assert "تموم شد" in env.tg.texts(SHOP_ID)                              # به فروشنده خبر داده شد
    assert await pre_checkout(env, other, other.amount, buyer=STRANGER) is False   # نفر دوم: ناموجود
    env.tg.clear()
    await env.feed(env.shop, message(STRANGER, f"/start {c.code}"))
    (card,) = env.tg.sent(SHOP_ID, "SendPhoto")
    assert "ناموجود" in card["caption"] and "reply_markup" not in card
    await env.feed(env.shop, callback(OWNER, f"stockinf:{c.id}"))          # نامحدود
    async with SessionLocal() as s:
        assert (await s.get(Content, c.id)).stock is None


async def test_price_change_after_the_form_cancels_the_old_invoice(env):
    c = await make_physical(env, price=50)
    order = await fill_form(env, c)
    async with SessionLocal() as s:
        (await s.get(Content, c.id)).price_stars = 70
        await s.commit()
    assert await pre_checkout(env, order, 50) is False


async def test_form_can_be_cancelled_and_a_new_link_resets_it(env):
    c = await make_physical(env)
    await env.feed(env.shop, callback(BUYER, f"order:{c.id}"))
    await env.feed(env.shop, message(BUYER, "/cancel"))
    assert "لغو شد" in env.tg.texts(SHOP_ID)
    await env.feed(env.shop, callback(BUYER, f"order:{c.id}"))
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))           # وسط فرم دوباره لینک را باز کرد
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, "سلام، این کیف رنگ دیگه هم داره؟"))   # پیام عادی به فروشنده، نه «نام گیرنده»
    assert "۲ از ۴" not in env.tg.texts(SHOP_ID)
    async with SessionLocal() as s:
        assert await s.scalar(select(Order)) is None


async def test_undelivered_report_is_open_for_orders(env):
    c = await make_physical(env)
    order = await fill_form(env, c)
    await pay_order(env, order, charge="rep-1")
    async with SessionLocal() as s:
        pid = (await s.scalar(select(Purchase))).id
    env.tg.clear()
    await env.feed(env.shop, callback(BUYER, f"report:{pid}"))
    reasons = [b["callback_data"] for b in env.tg.buttons(SHOP_ID)]
    assert f"reportr:{pid}:undelivered" in reasons and f"reportr:{pid}:broken" not in reasons
    await env.feed(env.shop, callback(BUYER, f"reportr:{pid}:undelivered"))
    async with SessionLocal() as s:
        assert (await s.get(Purchase, pid)).report_reason == "undelivered"
    env.tg.clear()
    await env.feed(env.main, message(OWNER, "/reports"))
    assert "کالا نرسیده" in env.tg.texts(MAIN_ID)


async def test_physical_product_cannot_be_bought_as_a_file(env, client):  # noqa: F811
    c = await make_physical(env)
    env.tg.clear()
    # فاکتور «محتوا» برای کالا پذیرفته نمی‌شود (بدون نشانی نمی‌شود فروخت)
    await env.feed(env.shop, {"pre_checkout_query": {"id": "q9", "from": {"id": BUYER, "is_bot": False, "first_name": "B"},
                                                     "currency": "XTR", "total_amount": c.price_stars,
                                                     "invoice_payload": f"c:{c.id}"}})
    assert env.tg.sent(SHOP_ID, "AnswerPreCheckoutQuery")[-1]["ok"] is False
    # مینی‌اپ: به‌جای فاکتور، خریدار به چت بازو فرستاده می‌شود؛ کارت کالا عکس واضح و برچسب دارد
    r = await client.post(f"/api/store/{SHOP_ID}/invoice/{c.id}", headers=as_user(BUYER))
    assert (await r.json()) == {"open": f"https://ble.ir/bot{SHOP_ID}?start={c.code}"}
    store = await (await client.get(f"/api/store/{SHOP_ID}", headers=as_user(BUYER))).json()
    item = store["items"][0]
    assert item["physical"] is True and item["in_stock"] is True and item["images"] == 1 and item["bought"] is False
    assert (await client.get(f"/api/store/{SHOP_ID}/img/{c.id}/0", headers=as_user(BUYER))).status == 200


async def test_seller_sets_shipping_fee_in_main_bot(env):
    await env.feed(env.main, message(OWNER, "/shop"))
    assert any(b.get("callback_data") == "shop:shipping" and "رایگان" in b["text"] for b in env.tg.buttons(MAIN_ID))
    await env.feed(env.main, callback(OWNER, "shop:shipping"))
    await env.feed(env.main, message(OWNER, "ارزان"))
    env.tg.clear()
    await env.feed(env.main, message(OWNER, "۴۵٬۰۰۰"))
    async with SessionLocal() as s:
        assert (await s.scalar(select(Seller).where(Seller.bot_id == SHOP_ID))).shipping_fee == 45000
        assert await s.scalar(select(Content)) is None                     # عدد «لینک رایگان» نشد
    assert "45,000 تومان" in env.tg.texts(MAIN_ID)


async def test_stock_and_physical_flag_through_the_mini_app_api(env, client):  # noqa: F811
    c = await make_physical(env)
    h = as_user(OWNER, via_shop=False)
    r = await client.patch(f"/api/products/{c.id}", headers=h, json={"stock": 3})
    body = await r.json()
    assert r.status == 200 and body["physical"] is True and body["stock"] == 3
    assert (await client.patch(f"/api/products/{c.id}", headers=h, json={"stock": -1})).status == 400
    assert (await client.patch(f"/api/products/{c.id}", headers=h, json={"price": 0})).status == 400   # کالای رایگان نه
    assert (await (await client.patch(f"/api/products/{c.id}", headers=h, json={"stock": None})).json())["stock"] is None


async def test_owner_tapping_order_on_own_product_gets_a_clear_hint(env):
    c = await make_physical(env)
    await env.feed(env.shop, callback(OWNER, f"order:{c.id}"))
    assert "محصول خودته" in env.tg.texts(SHOP_ID)
    async with SessionLocal() as s:
        assert await s.scalar(select(Order)) is None
