"""سایت معرفی (نسخه‌ی بله): همه‌ی صفحه‌ها ساخته می‌شوند، جای‌گذاری کامل است، برچسب منبع درست است، سئو پایه سر
جایش است و هیچ ردی از نسخه‌ی تلگرام (استارز، t.me، ربات) در متن نیست."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
from pages import PAGES  # noqa: E402


def clean_source(tag: str) -> str:
    """همان قاعده‌ی بازو (bot/app/handlers.py): برچسب منبع فقط a-z، عدد و _ تا ۲۸ حرف؛ وگرنه در /stats «other» می‌شود."""
    tag = tag.lower()[:28]
    return f"src_{tag}" if re.fullmatch(r"[a-z0-9_]+", tag) else "src_other"


def page_file(out: Path, slug: str) -> Path:
    if slug == "/":
        return out / "index.html"
    return out / slug.lstrip("/") if slug.endswith(".html") else out / slug.strip("/") / "index.html"


def test_site_builds_with_seo_basics(tmp_path):
    out = tmp_path / "dist"
    pages = build.build("https://uploadfly.example", "uploadflybot", "UploadFlySupport", "help@uploadfly.example",
                        "gsc-token", out)
    assert len(pages) == len(PAGES) and all(p["lang"] == "fa" for p in PAGES)
    for page in PAGES:
        html = page_file(out, page["slug"]).read_text(encoding="utf-8")
        assert not re.search(r"\{(START|BOT|SUPPORT)\}", html), page["slug"]         # همه‌ی جاها پر شده
        assert html.count("<h1") == 1 and '<html lang="fa" dir="rtl">' in html
        assert len(page["title"]) <= 65 and 50 <= len(page["description"]) <= 165 or page.get("noindex"), page["slug"]
        assert f'<link rel="canonical" href="https://uploadfly.example{page["slug"]}">' in html
        tag = f"src_site_{page['tag']}"
        assert f"ble.ir/uploadflybot?start={tag}" in html and clean_source(tag[4:]) == tag   # در /stats همین اسم
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html):
            json.loads(block)                                                         # داده‌ی ساختاریافته معتبر
        assert 'google-site-verification" content="gsc-token"' in html
        assert "ble.ir/UploadFlySupport" in html and "help@uploadfly.example" in html
        assert "ble.ir/uploadflybot?start=support" in html
    sitemap = (out / "sitemap.xml").read_text(encoding="utf-8")
    for slug in ("/sell/", "/goods/", "/guide/", "/showcase/", "/free-link/"):
        assert f"https://uploadfly.example{slug}" in sitemap
    assert "404" not in sitemap
    assert "Sitemap: https://uploadfly.example/sitemap.xml" in (out / "robots.txt").read_text(encoding="utf-8")
    assert (out / "assets" / "og-fa.jpg").exists() and (out / "assets" / "fonts" / "vazirmatn-arabic-wght-normal.woff2").exists()


def test_no_trace_of_the_telegram_version(tmp_path):
    """نسخه‌ی بله جداست: نه استارز، نه t.me، نه «ربات»؛ پول تومان است و «بازو» گفته می‌شود."""
    out = tmp_path / "dist"
    build.build("https://uploadfly.example", "uploadflybot", "", "", "", out)
    banned = ("تلگرام", "استارز", "t.me/", "telegram", "Telegram", "Stars", "Fragment", "TON", "ربات")
    for page in PAGES:
        html = page_file(out, page["slug"]).read_text(encoding="utf-8")
        for word in banned:
            assert word not in html, (page["slug"], word)
    assert not (out / "en").exists() and not list((out / "assets").glob("globe*"))


def test_internal_links_exist(tmp_path):
    out = tmp_path / "dist"
    build.build("https://uploadfly.example", "uploadflybot", "", "", "", out)
    slugs = {p["slug"] for p in PAGES}
    for page in PAGES:
        html = page_file(out, page["slug"]).read_text(encoding="utf-8")
        for href in re.findall(r'href="(/[^"#?]*)"', html):
            if href.startswith("/assets/"):
                assert (out / href.lstrip("/")).exists(), (page["slug"], href)
            else:
                assert href in slugs, (page["slug"], href)
