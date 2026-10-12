"""سایت معرفی UploadFly (برای گوگل و معرفی ربات): صفحه‌های ثابت HTML، بدون جاوااسکریپت سنگین و بدون CDN.

ساخت:  python3 website/build.py --url https://uploadfly.example  [--bot Uploadfly_Bot] [--support-username X] [--support-email Y]
خروجی: website/dist  (Caddy همین پوشه را روی دامنه‌ی اصلی نشان می‌دهد)

فقط کتابخانه‌ی استاندارد پایتون لازم است تا روی هر سرور بدون نصب چیزی ساخته شود.
هر دکمه‌ی «شروع» با برچسب منبع (src_site_<صفحه>) به ربات می‌رود؛ در /stats معلوم است گوگل چند کاربر آورده.
"""
import argparse
import html
import json
import os
import re
import shutil
from datetime import date
from pathlib import Path

from pages import PAGES

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
# Official profiles (brand 2026-10-11): listed in Organization sameAs and the footer, so Google ties them to the site.
SOCIAL = {"instagram": "https://www.instagram.com/UploadFly", "telegram_fa": "https://t.me/UploadflyFA",
          "telegram_en": "https://t.me/UploadflyEN"}


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text)).strip()


def asset_version() -> str:
    """نسخه‌ی فایل‌های css/js در آدرس، تا بعد از هر تغییر حتماً تازه دانلود شوند."""
    stamp = max(p.stat().st_mtime for p in ASSETS.rglob("*") if p.is_file())
    return str(int(stamp))


def render(page: dict, ctx: dict) -> str:
    lang, slug = page["lang"], page["slug"]
    url = ctx["url"] + slug
    rtl = lang == "fa"
    t = ctx["ui"][lang]
    start = lambda tag: f"https://t.me/{ctx['bot']}?start=src_site_{tag}"  # noqa: E731
    body = page["body"].replace("{START}", start(page["tag"])).replace("{BOT}", ctx["bot"])
    body = body.replace("{SUPPORT}", support_html(ctx, lang))
    alt = next((p for p in PAGES if p["key"] == page["key"] and p["lang"] != lang), None)
    alternates = "".join(
        f'<link rel="alternate" hreflang="{p["lang"]}" href="{ctx["url"]}{p["slug"]}">'
        for p in PAGES if p["key"] == page["key"]) + (
        f'<link rel="alternate" hreflang="x-default" href="{ctx["url"]}{next(p for p in PAGES if p["key"] == page["key"] and p["lang"] == "fa")["slug"]}">'
        if alt else "")
    schema = [
        {"@context": "https://schema.org", "@type": "Organization", "name": "UploadFly", "url": ctx["url"] + "/",
         "logo": ctx["url"] + "/assets/icon-512.png", "sameAs": [f"https://t.me/{ctx['bot']}", *SOCIAL.values()]},
    ] + page.get("schema", [])
    if slug == "/" or slug == "/en/":
        schema.append({"@context": "https://schema.org", "@type": "WebSite", "name": "UploadFly", "url": ctx["url"] + "/",
                       "inLanguage": lang})
        schema.append({"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "UploadFly",
                       "applicationCategory": "BusinessApplication", "operatingSystem": "Telegram",
                       "url": f"https://t.me/{ctx['bot']}", "inLanguage": lang,
                       "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
                       "description": page["description"]})
    if page.get("faq"):
        schema.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": strip_tags(a)}}
            for q, a in page["faq"]]})
    if page.get("crumb"):
        home = "/" if lang == "fa" else "/en/"
        schema.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": t["home"], "item": ctx["url"] + home},
            {"@type": "ListItem", "position": 2, "name": page["crumb"], "item": url}]})
    faq_html = ""
    if page.get("faq"):
        faq_html = (f'<section class="section" id="faq"><div class="wrap narrow"><h2 class="h2">{esc(t["faq_title"])}</h2>'
                    '<div class="faq">' + "".join(
                        f'<details><summary>{esc(q)}</summary><div class="answer">{a}</div></details>' for q, a in page["faq"])
                    + "</div></div></section>")
    current = ' aria-current="page"'
    nav = "".join(f'<a href="{href}"{current if href == slug else ""}>{esc(label)}</a>' for href, label in t["nav"])
    other = ctx["ui"]["en" if rtl else "fa"]
    lang_link = alt["slug"] if alt else ("/en/" if rtl else "/")
    verify = (f'<meta name="google-site-verification" content="{esc(ctx["gsc"])}">' if ctx.get("gsc") else "")
    v = ctx["version"]
    globe = (f'\n<script src="/assets/globe-land.js?v={v}" defer></script><script src="/assets/globe.js?v={v}" defer></script>'
             if "data-globe" in body else "")
    return f"""<!doctype html>
<html lang="{lang}" dir="{"rtl" if rtl else "ltr"}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(page["title"])}</title>
<meta name="description" content="{esc(page["description"])}">
<link rel="canonical" href="{url}">
{alternates}
<meta name="robots" content="{"noindex, follow" if page.get("noindex") else "index, follow, max-image-preview:large"}">
<meta name="theme-color" content="#5b5bd6">
<meta property="og:type" content="website">
<meta property="og:site_name" content="UploadFly">
<meta property="og:locale" content="{"fa_IR" if rtl else "en_US"}">
<meta property="og:title" content="{esc(page["title"])}">
<meta property="og:description" content="{esc(page["description"])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{ctx["url"]}/assets/og-{lang}.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
{verify}
<link rel="icon" href="/assets/icon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/assets/icon-512.png">
<link rel="preload" href="/assets/fonts/{"vazirmatn-arabic" if rtl else "vazirmatn-latin"}-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/site.css?v={v}">
<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False, separators=(",", ":"))}</script>
</head>
<body>
<a class="skip" href="#main">{esc(t["skip"])}</a>
<header class="top"><div class="wrap top-in">
  <a class="brand" href="{"/" if rtl else "/en/"}" aria-label="UploadFly">{LOGO}<span>uploadfly</span></a>
  <nav class="nav" id="nav" aria-label="{esc(t["menu"])}">{nav}<a class="lang" href="{lang_link}" hreflang="{other["code"]}">{esc(other["name"])}</a></nav>
  <a class="btn btn-primary btn-sm top-cta" href="{start(page["tag"])}" rel="noopener">{esc(t["cta_short"])}</a>
  <button class="menu" type="button" aria-controls="nav" aria-expanded="false" aria-label="{esc(t["menu"])}"><span></span><span></span></button>
</div></header>
<main id="main">
{body}
{faq_html}
</main>
<footer class="foot"><div class="wrap foot-in">
  <div class="foot-brand"><a class="brand" href="{"/" if rtl else "/en/"}">{LOGO}<span>uploadfly</span></a><p>{esc(t["footer_line"])}</p>
    <p class="social">{"".join(f'<a href="{SOCIAL[key]}" rel="me noopener">{esc(label)}</a>' for key, label in t["social"])}</p></div>
  <nav aria-label="footer">{"".join(f'<a href="{href}">{esc(label)}</a>' for href, label in t["footer"])}</nav>
  <div class="foot-contact">{support_html(ctx, lang, compact=True)}</div>
  <p class="copy">© {date.today().year} UploadFly · {esc(t["not_affiliated"])}</p>
</div></footer>
<script src="/assets/site.js?v={v}" defer></script>{globe}
</body>
</html>
"""


def support_html(ctx: dict, lang: str, compact: bool = False) -> str:
    t = ctx["ui"][lang]
    links = [f'<a href="https://t.me/{ctx["bot"]}?start=support">{esc(t["support_bot"])}</a>']
    if ctx.get("support_username"):
        links.append(f'<a href="https://t.me/{esc(ctx["support_username"])}" rel="noopener">{esc(t["support_chat"])}</a>')
    if ctx.get("support_email"):
        links.append(f'<a href="mailto:{esc(ctx["support_email"])}">{esc(ctx["support_email"])}</a>')
    return ("<span>" + " · ".join(links) + "</span>") if compact else '<p class="support-links">' + " · ".join(links) + "</p>"


LOGO = ('<svg class="mark" viewBox="18 18 204 204" aria-hidden="true"><defs><linearGradient id="ufl-sky" x1="48" y1="210" x2="215" y2="30" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#5b5bd6"/><stop offset="1" stop-color="#33c3e8"/></linearGradient><linearGradient id="ufl-gold" x1="0" y1="121" x2="0" y2="163" gradientUnits="userSpaceOnUse"><stop offset="0" stop-color="#ffd25e"/><stop offset="1" stop-color="#f2a900"/></linearGradient></defs><g transform="translate(-18 3)"><path d="M66 104 V144 A54 54 0 0 0 174 144 V142" fill="none" stroke="url(#ufl-sky)" stroke-width="36" stroke-linecap="round" stroke-linejoin="round"/><path d="M174 92 V46" fill="none" stroke="url(#ufl-sky)" stroke-width="36" stroke-linecap="round" stroke-linejoin="round"/><path d="M138 72 L174 35 L210 72" fill="none" stroke="url(#ufl-sky)" stroke-width="36" stroke-linecap="round" stroke-linejoin="round"/><path d="M120.00 123.00 L124.97 134.16 L137.12 135.44 L128.05 143.61 L130.58 155.56 L120.00 149.46 L109.42 155.56 L111.95 143.61 L102.88 135.44 L115.03 134.16 Z" fill="url(#ufl-gold)" stroke="url(#ufl-gold)" stroke-width="7.6" stroke-linejoin="round"/></g></svg>')

UI = {
    "fa": {"code": "fa", "name": "فارسی", "home": "خانه", "skip": "رفتن به محتوا", "menu": "منو", "cta_short": "شروع در تلگرام",
           "faq_title": "سؤال‌های رایج", "support_bot": "پشتیبانی در ربات", "support_chat": "چت با پشتیبانی",
           "footer_line": "ساخت لینک و فروش فایل در تلگرام؛ پول فروش مستقیم به ربات خود فروشنده.",
           "not_affiliated": "UploadFly سرویسی مستقل است و وابسته به تلگرام نیست.",
           "social": [("telegram_fa", "کانال تلگرام"), ("instagram", "اینستاگرام")],
           "nav": [("/sell/", "فروش فایل"), ("/free-link/", "لینک رایگان"), ("/showcase/", "ویترین و لینک بیو"),
                   ("/telegram-stars/", "استارز تلگرام"), ("/faq/", "سؤالات")],
           "footer": [("/sell/", "فروش فایل در تلگرام"), ("/free-link/", "ساخت لینک فایل"), ("/showcase/", "ویترین"),
                      ("/telegram-stars/", "راهنمای استارز"), ("/faq/", "سؤالات رایج"), ("/terms/", "شرایط استفاده"),
                      ("/privacy/", "حریم خصوصی")]},
    "en": {"code": "en", "name": "English", "home": "Home", "skip": "Skip to content", "menu": "Menu", "cta_short": "Open in Telegram",
           "faq_title": "Questions", "support_bot": "Support in the bot", "support_chat": "Chat with support",
           "footer_line": "File links and selling on Telegram. Every Star goes straight to the seller's own bot.",
           "not_affiliated": "UploadFly is an independent service, not affiliated with Telegram.",
           "social": [("telegram_en", "Telegram channel"), ("instagram", "Instagram")],
           "nav": [("/en/#sell", "Sell"), ("/en/#links", "Free links"), ("/en/#faq", "Questions")],
           "footer": [("/en/", "Home"), ("/terms/", "Terms (Persian)"), ("/privacy/", "Privacy (Persian)")]},
}


def build(url: str, bot: str, support_username: str | None, support_email: str | None, gsc: str | None,
          out: Path) -> list[str]:
    ctx = {"url": url.rstrip("/"), "bot": bot, "ui": UI, "support_username": support_username,
           "support_email": support_email, "gsc": gsc, "version": asset_version()}
    # محتوای پوشه پاک می‌شود، نه خود پوشه: روی سرور خروجی یک volume داکر است و حذف خودش ممکن نیست
    out.mkdir(parents=True, exist_ok=True)
    for old in out.iterdir():
        shutil.rmtree(old) if old.is_dir() and not old.is_symlink() else old.unlink()
    shutil.copytree(ASSETS, out / "assets")
    written = []
    for page in PAGES:
        target = out / page["slug"].strip("/") / "index.html" if page["slug"] != "/" else out / "index.html"
        if page["slug"].endswith(".html"):
            target = out / page["slug"].lstrip("/")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render(page, ctx), encoding="utf-8")
        written.append(page["slug"])
    today = date.today().isoformat()
    urls = "".join(
        f"<url><loc>{ctx['url']}{p['slug']}</loc><lastmod>{today}</lastmod>"
        + "".join(f'<xhtml:link rel="alternate" hreflang="{q["lang"]}" href="{ctx["url"]}{q["slug"]}"/>'
                  for q in PAGES if q["key"] == p["key"] and sum(1 for r in PAGES if r["key"] == p["key"]) > 1)
        + f"<priority>{p.get('priority', '0.7')}</priority></url>"
        for p in PAGES if not p.get("noindex"))
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        f'xmlns:xhtml="http://www.w3.org/1999/xhtml">{urls}</urlset>\n', encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {ctx['url']}/sitemap.xml\n", encoding="utf-8")
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the UploadFly website into website/dist")
    ap.add_argument("--url", default=os.getenv("SITE_URL", "https://uploadfly.example"))
    ap.add_argument("--bot", default=os.getenv("MAIN_BOT", "Uploadfly_Bot"))
    ap.add_argument("--support-username", default=os.getenv("SUPPORT_USERNAME", "").lstrip("@") or None)
    ap.add_argument("--support-email", default=os.getenv("SUPPORT_EMAIL") or None)
    ap.add_argument("--gsc", default=os.getenv("GOOGLE_SITE_VERIFICATION") or None, help="Google Search Console token")
    ap.add_argument("--out", default=str(ROOT / "dist"))
    a = ap.parse_args()
    if not re.fullmatch(r"https?://[A-Za-z0-9.:-]+", a.url.rstrip("/")):
        raise SystemExit("--url must look like https://example.com")
    pages = build(a.url, a.bot, a.support_username, a.support_email, a.gsc, Path(a.out))
    print(f"Built {len(pages)} pages into {a.out} for {a.url}")


if __name__ == "__main__":
    main()
