"""جذب فروشنده و رشد در بله: خوش‌آمد با دکمه‌ی فروش، تشخیص توکن از متن چسبانده‌شده، متن آماده‌ی تبلیغ،
دعوت بازدیدکننده‌ی لینک رایگان، و نام خریدار روی عکس و PDF (جایگزین قفل فوروارد)."""
import pymupdf
from sqlalchemy import func, select

from app import creator
from app.connect import find_bot_token, find_wallet_token
from app.db import Content, Seller, SessionLocal
from tests.conftest import BUYER, MAIN_ID, MockSession, OWNER, SHOP_ID, STRANGER, callback, message, photo_message
from tests.test_creator import set_seller
from tests.test_flows import make_product, pay


def pdf_bytes(pages: int = 2) -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 100), f"page {i + 1}")
    raw = doc.tobytes()
    doc.close()
    return raw


# --- خوش‌آمد ---
async def test_welcome_points_newcomers_straight_to_selling(env):
    await env.feed(env.main, message(STRANGER, "/start"))
    text, data = env.tg.texts(MAIN_ID), [b.get("callback_data") for b in env.tg.buttons(MAIN_ID)]
    assert "بدون سایت و بدون درگاه" in text and "کیف پول بله‌ی خودت" in text
    assert "shop:create" in data and "shop:home" not in data          # یک ضربه تا راهنمای ساخت فروشگاه
    env.tg.clear()
    await env.feed(env.main, callback(STRANGER, "shop:create"))
    assert "ساخت فروشگاه در ۳ قدم" in env.tg.texts(MAIN_ID)
    env.tg.clear()
    await env.feed(env.main, message(OWNER, "/start"))                # کسی که فروشگاه دارد: «فروشگاه من»
    data = [b.get("callback_data") for b in env.tg.buttons(MAIN_ID)]
    assert "shop:home" in data and "shop:create" not in data


# --- توکن ---
def test_tokens_are_found_inside_pasted_messages():
    token = "2090603377:AbCdEfGhIjKlMnOpQrStUvWxYz0123456789"
    assert find_bot_token(f"بازوی شما ساخته شد.\nتوکن:\n{token}\nآن را امن نگه دارید") == token
    assert find_bot_token("سلام 1234 خوبی") is None and find_bot_token("https://ble.ir/x?start=abc") is None
    assert find_wallet_token("WALLET-TEST-1111111111111111") == "WALLET-TEST-1111111111111111"
    assert find_wallet_token("توکن کیف پول:\nWALLET-ABCD-1234567890123456\nنگهش دار") == "WALLET-ABCD-1234567890123456"
    assert find_wallet_token("توکن غلط با فاصله") is None
    assert find_wallet_token(token) is None                           # توکن بازو، توکن کیف پول نیست


async def test_whole_botfather_message_connects_the_shop_even_without_the_command(env):
    token = "3000007:" + "E" * 35
    await env.feed(env.main, message(BUYER, f"بازوی شما ساخته شد ✅\nتوکن دسترسی:\n{token}\nاین توکن را به کسی ندهید."))
    assert env.tg.sent(MAIN_ID, "DeleteMessage")                      # پیام حاوی توکن از چت پاک شد
    async with SessionLocal() as s:
        seller = await s.scalar(select(Seller).where(Seller.bot_id == 3000007))
        assert seller and seller.owner_id == BUYER and seller.watermark is True   # فروشگاه تازه: نام خریدار روشن
        # توکن «لینک رایگان» نشد (وگرنه هر کس لینک را داشت توکن را می‌دید)
        assert await s.scalar(select(func.count(Content.id)).where(Content.owner_id == BUYER)) == 0
    assert "قدم ۳ از ۳" in env.tg.texts(MAIN_ID) and token not in env.tg.texts()


# --- متن آماده‌ی تبلیغ ---
async def test_published_product_offers_a_ready_post_to_copy(env):
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        c = await s.scalar(select(Content).order_by(Content.id.desc()))
        c.title = "جزوه‌ی ریاضی دهم"
        await s.commit()
    env.tg.clear()
    await env.feed(env.shop, callback(OWNER, f"price:{c.id}:25"))
    copies = [b["copy_text"]["text"] for b in env.tg.buttons(SHOP_ID) if b.get("copy_text")]
    link = f"https://ble.ir/bot{SHOP_ID}?start={c.code}"
    assert copies[0] == link
    assert "جزوه‌ی ریاضی دهم" in copies[1] and "25 تومان" in copies[1] and link in copies[1] and len(copies[1]) <= 256
    assert not any("share" in b.get("url", "") for b in env.tg.buttons(SHOP_ID))   # بله لینک اشتراک‌گذاری ندارد


async def test_free_link_in_main_bot_has_only_the_copy_link_button(env):
    await env.feed(env.main, photo_message(BUYER))
    buttons = env.tg.buttons(MAIN_ID)
    assert len(buttons) == 1 and buttons[0]["copy_text"]["text"].startswith("https://ble.ir/Uploadfly_Bot?start=")


# --- حلقه‌ی رشد زیر لینک رایگان ---
async def test_viewer_of_a_free_link_is_invited_once(env):
    await env.feed(env.main, photo_message(BUYER))
    async with SessionLocal() as s:
        code = (await s.scalar(select(Content).order_by(Content.id.desc()))).code
    env.tg.clear()
    await env.feed(env.main, message(STRANGER, f"/start {code}"))
    invites = [m for m in env.tg.sent(MAIN_ID, "SendMessage") if "تو هم هر فایلی" in m["text"]]
    assert len(invites) == 1 and invites[0]["disable_notification"] is True
    assert invites[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "shop:create"
    env.tg.clear()
    await env.feed(env.main, message(STRANGER, f"/start {code}"))     # همان هفته: دوباره نه
    assert "تو هم هر فایلی" not in env.tg.texts(MAIN_ID)
    await env.feed(env.main, message(BUYER, f"/start {code}"))        # صاحب لینک: هیچ‌وقت
    assert "تو هم هر فایلی" not in env.tg.texts(MAIN_ID)
    # کسی که خودش لینک ساخته، دعوت لازم ندارد
    await env.feed(env.main, photo_message(777))
    env.tg.clear()
    await env.feed(env.main, message(777, f"/start {code}"))
    assert "تو هم هر فایلی" not in env.tg.texts(MAIN_ID)


# --- نام خریدار روی فایل ---
def test_pdf_gets_the_buyer_name_on_every_page():
    out = creator.watermark_pdf(pdf_bytes(3), "@buyer_one")
    doc = pymupdf.open(stream=out, filetype="pdf")
    assert doc.page_count == 3 and all(pg.get_text().count("@buyer_one") == 2 for pg in doc)   # پانویس + مورب
    assert "page 2" in doc[1].get_text()                              # خود محتوا دست نخورده


async def test_bought_pdf_is_delivered_as_a_personal_copy(env, monkeypatch):
    await set_seller(watermark=True)
    raw = pdf_bytes()

    async def pdf_download(self, *args, **kwargs):
        yield raw
    monkeypatch.setattr(MockSession, "stream_content", pdf_download)
    await env.feed(env.shop, message(OWNER, document={"file_id": "doc1", "file_unique_id": "ud1", "file_name": "jozve.pdf",
                                                      "mime_type": "application/pdf", "file_size": len(raw)}))
    async with SessionLocal() as s:
        c = await s.scalar(select(Content).order_by(Content.id.desc()))
    await env.feed(env.shop, callback(OWNER, f"price:{c.id}:10"))
    async with SessionLocal() as s:
        c = await s.get(Content, c.id)
    p = await pay(env, c)
    env.tg.clear()
    await env.feed(env.shop, callback(BUYER, f"open:{p.id}"))
    (doc,) = [x for x in env.tg.sent(SHOP_ID, "SendDocument") if x["chat_id"] == BUYER]
    assert not isinstance(doc["document"], str)                       # فایل تازه، نه همان file_id فروشنده
    sent = pymupdf.open(stream=doc["document"].data, filetype="pdf")
    # خریدار ساختگی نام کاربری ندارد، پس شناسه‌اش ثبت می‌شود
    assert f"id {BUYER}" in sent[0].get_text() and doc["document"].filename == "jozve.pdf"
    assert "شناسه‌ات رویش ثبت شده" in env.tg.texts(SHOP_ID)            # خریدار می‌داند نسخه‌اش نشانه‌دار است


async def test_unmarkable_or_switched_off_content_is_sent_as_is(env):
    await set_seller(watermark=False)
    c = await make_product(env, price=10)
    p = await pay(env, c)
    env.tg.clear()
    await env.feed(env.shop, callback(BUYER, f"open:{p.id}"))
    (photo,) = [x for x in env.tg.sent(SHOP_ID, "SendPhoto") if x["chat_id"] == BUYER]
    assert isinstance(photo["photo"], str) and "شناسه‌ات رویش" not in env.tg.texts(SHOP_ID)


async def test_seller_switches_buyer_name_marking_from_the_shop_panel(env):
    await set_seller(watermark=False)
    await env.feed(env.main, message(OWNER, "/shop"))
    assert any(b.get("callback_data") == "shop:mark" and "خاموش" in b["text"] for b in env.tg.buttons(MAIN_ID))
    env.tg.clear()
    await env.feed(env.main, callback(OWNER, "shop:mark"))
    async with SessionLocal() as s:
        assert (await s.scalar(select(Seller).where(Seller.bot_id == SHOP_ID))).watermark is True
    (alert,) = env.tg.sent(MAIN_ID, "AnswerCallbackQuery")
    assert "روشن شد" in alert["text"] and alert["show_alert"] is True
    await env.feed(env.main, callback(STRANGER, "shop:mark"))         # بدون فروشگاه: هیچ
