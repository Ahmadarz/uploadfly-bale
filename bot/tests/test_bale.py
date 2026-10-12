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
