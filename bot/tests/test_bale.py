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
