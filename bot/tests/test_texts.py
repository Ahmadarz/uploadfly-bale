"""متن‌های چت ربات به ۵ زبان: کلیدها و جاهای خالی یکی، HTML معتبر تلگرام، /lang با ۵ گزینه."""
import re

import pytest

from app.texts import COMMANDS, LANGUAGES, TEXTS, T, human_wait
from tests.conftest import BUYER, MAIN_ID, callback, check_html, message


def flat(d, p=""):
    for k, v in d.items():
        yield from flat(v, p + k + ".") if isinstance(v, dict) else [(p + k, v)]


@pytest.mark.parametrize("lang", LANGUAGES)
def test_every_language_has_every_text(lang):
    en, other = dict(flat(TEXTS["en"])), dict(flat(TEXTS[lang]))
    assert other.keys() == en.keys(), set(en) ^ set(other)
    for key, value in en.items():
        names = lambda v: set(re.findall(r"\{(\w+)\}", v))
        assert names(other[key]) == names(value), (lang, key)
        check_html(other[key].replace("{", "").replace("}", ""), key)   # تلگرام HTML نامعتبر را رد می‌کند
    assert COMMANDS[lang].keys() == COMMANDS["en"].keys()


def test_wait_time_in_each_language():
    assert human_wait(3720, "fa") == "1 ساعت و 2 دقیقه"
    assert human_wait(3720, "ru") == "1 ч 2 мин" and human_wait(3600, "zh") == "1 小时"
    assert human_wait(30, "ar") == "1 دقيقة"


async def test_lang_command_offers_five_and_switches(env):
    await env.feed(env.main, message(BUYER, "/lang"))
    labels = [b["text"] for b in env.tg.buttons(MAIN_ID)]
    assert len(labels) == 5 and "✅ فارسی" in labels and "Русский" in labels and "中文" in labels
    env.tg.clear()
    await env.feed(env.main, callback(BUYER, "lang:ar"))
    assert "العربية" in env.tg.texts(MAIN_ID) or any(
        "العربية" in str(p) for p in env.tg.sent(MAIN_ID, "EditMessageText"))
    env.tg.clear()
    await env.feed(env.main, message(BUYER, "/help"))
    assert "المساعدة" in env.tg.texts(MAIN_ID)
    assert T("xx")["help"] == T("en")["help"]   # زبان ناشناخته → انگلیسی
