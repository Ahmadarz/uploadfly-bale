"""لایه‌ی بله: تبدیل متن HTML برنامه به Markdown بله و رد کردن متدهایی که بله ندارد."""
from aiogram.methods import SendMediaGroup, SendMessage, SendPhoto, SetMyDescription
from aiogram.types import InputMediaPhoto

from app.bale import BaleMiddleware, bot_link, to_bale


def test_html_becomes_bale_markdown():
    assert to_bale("<b>سلام</b> <i>دنیا</i>") == "*سلام* _دنیا_"
    assert to_bale('<a href="https://ble.ir/bot?start=a&amp;b">باز کن</a>') == "[باز کن](https://ble.ir/bot?start=a&b)"
    # بله «کد» تک‌خطی ندارد: فقط خود متن می‌ماند (لینک خام در بله خودش قابل لمس است)
    assert to_bale("<code>https://ble.ir/bot?start=abc</code>") == "https://ble.ir/bot?start=abc"
    # متن کاربر که در برنامه escape شده، دوباره همان متن اصلی می‌شود
    assert to_bale("a &lt; b &amp; c") == "a < b & c"
    assert to_bale("my_file_name.pdf 2*3") == "my_file_name.pdf 2*3"


def test_bot_link():
    assert bot_link("shop_bot") == "https://ble.ir/shop_bot"
    assert bot_link("shop_bot", "abc") == "https://ble.ir/shop_bot?start=abc"


async def test_middleware_converts_text_and_skips_missing_methods():
    seen = []

    async def make_request(bot, method):
        seen.append(method)
        return "sent"

    mw = BaleMiddleware()
    assert await mw(make_request, None, SendMessage(chat_id=1, text="<b>x</b>", parse_mode="HTML")) == "sent"
    assert seen[-1].text == "*x*" and seen[-1].parse_mode is None
    await mw(make_request, None, SendPhoto(chat_id=1, photo="f", caption="<i>y</i>"))
    assert seen[-1].caption == "_y_"
    await mw(make_request, None, SendMediaGroup(chat_id=1, media=[
        InputMediaPhoto(media="a", caption="<b>z</b>"), InputMediaPhoto(media="b")]))
    assert [m.caption for m in seen[-1].media] == ["*z*", None]
    # بله این متد را ندارد: درخواستی فرستاده نمی‌شود و برنامه هم خطا نمی‌گیرد
    before = len(seen)
    assert await mw(make_request, None, SetMyDescription(description="d")) is True
    assert len(seen) == before


async def test_invoice_goes_out_in_rials_with_the_shop_wallet():
    import pytest
    from aiogram.methods import CreateInvoiceLink, SendInvoice
    from aiogram.types import LabeledPrice

    from app.bale import NoWallet, set_wallet

    class FakeBot:
        id = 4242

    seen = []

    async def make_request(bot, method):
        seen.append(method)
        return "sent"

    mw, price = BaleMiddleware(), [LabeledPrice(label="قیمت", amount=25_000)]   # داخل برنامه: تومان
    invoice = SendInvoice(chat_id=1, title="t", description="d", payload="c:1", currency="XTR", prices=price,
                          subscription_period=2592000)
    set_wallet(4242, None)
    with pytest.raises(NoWallet):            # فروشگاه بدون کیف پول فاکتور نمی‌سازد
        await mw(make_request, FakeBot(), invoice)
    set_wallet(4242, "WALLET-TEST-1111111111111111")
    await mw(make_request, FakeBot(), invoice)
    out = seen[-1]
    assert out.currency == "IRR" and out.prices[0].amount == 250_000        # بله ریال می‌خواهد
    assert out.provider_token == "WALLET-TEST-1111111111111111" and out.subscription_period is None
    await mw(make_request, FakeBot(), CreateInvoiceLink(title="t", description="d", payload="c:1", currency="XTR",
                                                        prices=price))
    assert seen[-1].currency == "IRR" and seen[-1].prices[0].amount == 250_000
    set_wallet(4242, None)


def test_incoming_bale_payment_becomes_toman():
    from aiogram.types import Update

    from app.bale import to_toman
    user = {"id": 5, "is_bot": False, "first_name": "x"}
    q = to_toman(Update.model_validate({"update_id": 1, "pre_checkout_query": {
        "id": "1", "from": user, "currency": "IRR", "total_amount": 250_000, "invoice_payload": "c:1"}}))
    assert q.pre_checkout_query.currency == "XTR" and q.pre_checkout_query.total_amount == 25_000
    # نمونه‌ی واقعی بله: پیام پرداخت موفق با message_id صفر
    m = to_toman(Update.model_validate({"update_id": 2, "message": {
        "message_id": 0, "date": 1, "chat": {"id": 5, "type": "private"}, "from": user,
        "successful_payment": {"currency": "IRR", "total_amount": 10_000, "invoice_payload": "c:1",
                               "telegram_payment_charge_id": "1625851548857042109",
                               "provider_payment_charge_id": ""}}}))
    assert m.message.successful_payment.total_amount == 1_000 and m.message.successful_payment.currency == "XTR"
    plain = Update.model_validate({"update_id": 3, "message": {
        "message_id": 1, "date": 1, "chat": {"id": 5, "type": "private"}, "from": user, "text": "سلام"}})
    assert to_toman(plain) is plain


def test_uploads_put_the_file_in_its_own_field():
    """بله «attach://» را نمی‌فهمد: فایل باید مستقیم در همان فیلد (photo، document ...) باشد."""
    from aiogram.types import BufferedInputFile

    from app.bale import make_bale_bot
    bot = make_bale_bot("4242:" + "A" * 35)
    form = bot.session.build_form_data(bot, SendPhoto(chat_id=7, photo=BufferedInputFile(b"jpeg-bytes", "p.jpg"),
                                                      caption="c"))
    fields = {opts["name"]: (opts.get("filename"), value) for opts, _headers, value in form._fields}
    assert fields["photo"][0] == "p.jpg" and set(fields) == {"chat_id", "photo", "caption"}
    assert not any(isinstance(v, str) and v.startswith("attach://") for _name, v in fields.values())
    # آلبوم: خود بله مرجع attach:// را داخل media می‌پذیرد، پس همان شکل استاندارد می‌ماند
    form = bot.session.build_form_data(bot, SendMediaGroup(chat_id=7, media=[
        InputMediaPhoto(media=BufferedInputFile(b"a", "a.jpg")), InputMediaPhoto(media=BufferedInputFile(b"b", "b.jpg"))]))
    names = [opts["name"] for opts, _headers, _value in form._fields]
    assert "media" in names and len(names) == 4


async def test_failed_preview_upload_does_not_block_publishing(env, monkeypatch):
    """دیده‌شده روی بله: آپلود پیش‌نمایش رد شد و محصول «پیش‌نویس» ماند. حالا بدون پیش‌نمایش منتشر می‌شود."""
    from aiogram.exceptions import TelegramBadRequest
    from sqlalchemy import select

    from app.db import Content, SessionLocal
    from tests.conftest import OWNER, SHOP_ID, callback, photo_message
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        c = await s.scalar(select(Content).order_by(Content.id.desc()))

    async def refuse(*args, **kwargs):
        raise TelegramBadRequest(method=None, message="Bad Request: failed to get HTTP URL content")
    monkeypatch.setattr(env.shop, "send_photo", refuse)
    await env.feed(env.shop, callback(OWNER, f"price:{c.id}:10"))
    async with SessionLocal() as s:
        c = await s.get(Content, c.id)
    assert not c.is_draft and c.is_active and c.price_stars == 10 and c.preview is None
    assert "لینک ساخته شد" in env.tg.texts(SHOP_ID)
