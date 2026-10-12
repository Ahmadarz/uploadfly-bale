"""سایت معرفی: همه‌ی صفحه‌ها ساخته می‌شوند، جای‌گذاری کامل است، برچسب منبع درست است و سئو پایه سر جایش است."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
from pages import PAGES  # noqa: E402


def clean_source(tag: str) -> str:
    """همان قاعده‌ی ربات (bot/app/handlers.py): برچسب منبع فقط a-z، عدد و _ تا ۲۸ حرف؛ وگرنه در /stats «other» می‌شود."""
    tag = tag.lower()[:28]
    return f"src_{tag}" if re.fullmatch(r"[a-z0-9_]+", tag) else "src_other"


def test_site_builds_with_seo_basics(tmp_path):
    out = tmp_path / "dist"
    pages = build.build("https://uploadfly.example", "Uploadfly_Bot", "UploadFlySupport", "help@uploadfly.example",
                        "gsc-token", out)
    assert len(pages) == len(PAGES)
    for page in PAGES:
        path = out / (page["slug"].lstrip("/") if page["slug"].endswith(".html") else page["slug"].strip("/") + "/index.html")
        if page["slug"] == "/":
            path = out / "index.html"
        html = path.read_text()
        assert not re.search(r"\{(START|BOT|SUPPORT)\}", html), page["slug"]         # همه‌ی جاها پر شده
        assert html.count("<h1") == 1 and f'<html lang="{page["lang"]}"' in html
        assert len(page["title"]) <= 65 and 50 <= len(page["description"]) <= 165 or page.get("noindex"), page["slug"]
        assert f'<link rel="canonical" href="https://uploadfly.example{page["slug"]}">' in html
        tag = f"src_site_{page['tag']}"
        assert f"t.me/Uploadfly_Bot?start={tag}" in html and clean_source(tag[4:]) == tag   # در /stats همین اسم
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html):
            json.loads(block)                                                         # داده‌ی ساختاریافته معتبر
        assert 'google-site-verification" content="gsc-token"' in html
        assert "t.me/UploadFlySupport" in html and "help@uploadfly.example" in html
    sitemap = (out / "sitemap.xml").read_text()
    assert "https://uploadfly.example/sell/" in sitemap and "404" not in sitemap
    assert "Sitemap: https://uploadfly.example/sitemap.xml" in (out / "robots.txt").read_text()
    home, home_en = (out / "index.html").read_text(), (out / "en" / "index.html").read_text()
    for profile in build.SOCIAL.values():                                       # پروفایل‌های رسمی در sameAs
        assert f'"{profile}"' in home and f'"{profile}"' in home_en
    for page_html, channel in ((home, "telegram_fa"), (home_en, "telegram_en")):  # و در فوتر، کانال هم‌زبان
        assert f'href="{build.SOCIAL[channel]}"' in page_html and f'href="{build.SOCIAL["instagram"]}"' in page_html
    assert (out / "assets" / "og-fa.png").exists() and (out / "assets" / "fonts" / "vazirmatn-arabic-wght-normal.woff2").exists()


def test_globe_only_on_home_pages(tmp_path):
    """کره‌ی «بازار تو: کل زمین» و اسکریپتش فقط در صفحه‌ی اصلی فارسی و انگلیسی؛ فروشنده‌ی فارسی در ایران."""
    out = tmp_path / "dist"
    build.build("https://uploadfly.example", "Uploadfly_Bot", "", "", "", out)
    fa, en, sell = ((out / p / "index.html").read_text() for p in ("", "en", "sell"))
    assert 'data-globe data-hub="35.7,51.4"' in fa and "data-globe" in en and "data-hub" not in en
    for html in (fa, en):
        assert "/assets/globe-land.js" in html and "/assets/globe.js" in html
    assert "globe" not in sell
    assert (out / "assets" / "globe-land.js").stat().st_size < 60_000
