"""نقشه‌ی خشکی برای کره‌ی صفحه‌ی اصلی (globe.js). فقط یک بار اجرا می‌شود؛ خروجی در گیت است.
ورودی: ne_110m_land.geojson از Natural Earth (مالکیت عمومی؛ github.com/nvkelso/natural-earth-vector).
خروجی: assets/globe-land.js = نقشه‌ی ۷۲۰×۳۶۰ (هر خانه نیم درجه) به صورت بیت، base64.
اجرا: .venv/bin/python website/make_globe.py path/to/ne_110m_land.geojson
"""
import base64
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 720, 360
OUT = Path(__file__).resolve().parent / "assets" / "globe-land.js"


def main(src: str) -> None:
    data = json.loads(Path(src).read_text())
    img = Image.new("1", (W, H), 0)
    d = ImageDraw.Draw(img)
    to_px = lambda lon, lat: ((lon + 180) / 360 * W, (90 - lat) / 180 * H)  # noqa: E731
    for feat in data["features"]:
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        for poly in polys:
            d.polygon([to_px(*p[:2]) for p in poly[0]], fill=1)
            for hole in poly[1:]:
                d.polygon([to_px(*p[:2]) for p in hole], fill=0)
    bits = bytearray(W * H // 8)
    px = img.load()
    for y in range(H):
        for x in range(W):
            if px[x, y]:
                i = y * W + x
                bits[i >> 3] |= 1 << (i & 7)
    b64 = base64.b64encode(bytes(bits)).decode()
    OUT.write_text("// Land mask " + f"{W}x{H}" + " (Natural Earth 110m, public domain), made by website/make_globe.py\n"
                   f'window.UF_LAND = "{b64}";\n')
    print(OUT, len(b64), "chars")


if __name__ == "__main__":
    main(sys.argv[1])
