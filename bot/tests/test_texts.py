"""متن‌های چت در بله: فقط فارسی، HTML معتبر (لایه‌ی بله به Markdown تبدیلش می‌کند)، بدون حرفی از تلگرام و استارز."""
from app.bale import to_bale
from app.texts import COMMANDS, LANGUAGES, MAIN_COMMANDS, SELLER_COMMANDS, T, human_wait
from tests.conftest import BUYER, MAIN_ID, check_html, message


def flat(d, p=""):
    for k, v in d.items():
        yield from flat(v, p + k + ".") if isinstance(v, dict) else [(p + k, v)]


def test_texts_are_persian_only_and_valid():
    assert LANGUAGES == ("fa",) and T("en") is T("fa") and T("xx") is T("fa")
    for key, value in flat(T("fa")):
        plain = value.replace("{", "").replace("}", "")
        check_html(plain, key)
        to_bale(plain)                       # تبدیل به قالب بله خطا نمی‌دهد


def test_no_telegram_or_stars_left_in_texts():
    for key, value in flat(T("fa")):
        for word in ("تلگرام", "استارز", "Telegram", "Stars", "BotFather", "Fragment", "t.me", "Premium"):
            assert word not in value, (key, word)
        assert "⭐" not in value or key in ("rate_hint", "rate_thanks"), key   # ستاره فقط برای امتیاز


def test_command_menus():
    assert set(MAIN_COMMANDS) | set(SELLER_COMMANDS) <= set(COMMANDS["fa"])
    assert "lang" not in MAIN_COMMANDS and "wallet" in MAIN_COMMANDS


def test_wait_time():
    assert human_wait(3720, "fa") == "1 ساعت و 2 دقیقه"


async def test_lang_command_says_persian_only(env):
    await env.feed(env.main, message(BUYER, "/lang"))
    assert "فارسی" in env.tg.texts(MAIN_ID) and not env.tg.buttons(MAIN_ID)
