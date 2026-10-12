"""فقط یک بار (یا بعد از تغییر شعار) اجرا می‌شود: تصویر اشتراک‌گذاری (og) و آیکن سایت. خروجی در website/assets.
نیاز: Pillow با raqm (برای فارسی). روی سرور لازم نیست؛ تصویرها در گیت هستند.
اجرا: .venv/bin/python website/make_images.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ASSETS = Path(__file__).resolve().parent / "assets"
FA = str(ASSETS / "fonts" / "vazirmatn-arabic-wght-normal.woff2")
LATIN = str(ASSETS / "fonts" / "vazirmatn-latin-wght-normal.woff2")
BRAND = str(ASSETS / "fonts" / "unbounded-latin-wght-normal.woff2")
A, B, NAVY1, NAVY2 = (91, 91, 214), (51, 195, 232), (45, 48, 96), (27, 29, 63)


def gradient(w: int, h: int, c1, c2) -> Image.Image:
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            t = (x / w * 0.6 + y / h * 0.4)
            px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    return img


def mark(size: int) -> Image.Image:
    m = gradient(size, size, A, B).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=int(size * 0.28), fill=255)
    m.putalpha(mask)
    d = ImageDraw.Draw(m)
    s, w = size / 32, max(2, int(size * 0.082))
    d.line([(16 * s, 22 * s), (16 * s, 10 * s)], fill="white", width=w)
    d.line([(11 * s, 15 * s), (16 * s, 10 * s), (21 * s, 15 * s)], fill="white", width=w, joint="curve")
    return m


def font(path: str, size: int, weight: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)
    try:
        f.set_variation_by_axes([weight])
    except (OSError, ValueError):
        pass
    return f


def og(lang: str) -> None:
    W, H = 1200, 630
    img = gradient(W, H, NAVY1, NAVY2).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([720, -320, 1480, 380], fill=(51, 195, 232, 70))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(120)))
    d = ImageDraw.Draw(img)
    rtl = lang == "fa"
    img.alpha_composite(mark(96), (W - 96 - 80, 72) if rtl else (80, 72))
    d.text((W - 80 - 96 - 24, 120) if rtl else (80 + 96 + 24, 120), "UPLOADFLY", font=font(BRAND, 34, 700),
           fill="white", anchor="rm" if rtl else "lm")
    if rtl:
        lines = [("فایل بفرست، لینک بگیر.", 66, 800, "white"), ("بفروش؛ پولش مستقیم مال خودت.", 66, 800, (140, 220, 245)),
                 ("ربات آپلودر و فروش فایل در تلگرام با استارز", 34, 500, (205, 208, 230))]
        fnt = FA
    else:
        lines = [("Send a file, get a link.", 64, 800, "white"), ("Sell it. The money is yours.", 64, 800, (140, 220, 245)),
                 ("Telegram file links and selling with Stars", 34, 500, (205, 208, 230))]
        fnt = LATIN
    y = 260
    for text, size, weight, color in lines:
        kw = {"direction": "rtl", "language": "fa"} if rtl else {}
        d.text((W - 80, y) if rtl else (80, y), text, font=font(fnt, size, weight), fill=color,
               anchor="ra" if rtl else "la", **kw)
        y += int(size * 1.55)
    img.convert("RGB").save(ASSETS / f"og-{lang}.png", optimize=True)


if __name__ == "__main__":
    og("fa")
    og("en")
    mark(512).save(ASSETS / "icon-512.png", optimize=True)
    print("ok")
