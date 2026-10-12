"""ظاهر ویترین: آپلود امن عکس، تم/بنر/لوگو، QR، و چک‌لیست شروع."""
import io

from PIL import Image as PILImage

from app.db import Image, SessionLocal
from tests.conftest import BUYER, OWNER, SHOP_ID
from tests.test_showcases import create, owner
from tests.test_web import as_user, client, forged, attacker_shop  # noqa: F401


def picture(fmt="JPEG", size=(2400, 1600), exif_gps=False) -> bytes:
    buf = io.BytesIO()
    im = PILImage.new("RGB", size, (200, 80, 40))
    kw = {}
    if exif_gps:
        exif = PILImage.Exif()
        exif[0x8825] = {1: "N", 2: (35.0, 41.0, 0.0)}  # GPS
        kw["exif"] = exif
    im.save(buf, fmt, **kw)
    return buf.getvalue()


async def upload(client, kind, data, who=OWNER):  # noqa: F811
    r = await client.post(f"/api/images?kind={kind}", headers=as_user(who, via_shop=False), data=data)
    return r.status, await r.json()


async def test_upload_is_rebuilt_and_validated(env, client):  # noqa: F811
    st, cover = await upload(client, "cover", picture(exif_gps=True))
    assert st == 200
    async with SessionLocal() as s:
        raw = (await s.get(Image, cover["id"])).data
    im = PILImage.open(io.BytesIO(raw))
    assert im.format == "JPEG" and im.size == (1500, 600) and not im.getexif().get(0x8825)   # بدون GPS
    st, logo = await upload(client, "logo", picture("PNG", (300, 900)))
    assert st == 200 and PILImage.open(io.BytesIO(await (await client.get(
        f"/api/images/{logo['id']}", headers=as_user(BUYER))).read())).size == (512, 512)
    assert (await upload(client, "cover", b"<?php echo 1; ?>"))[0] == 400            # فایل جعلی
    assert (await upload(client, "cover", b"GIF89a" + b"0" * 100))[0] == 400
    assert (await upload(client, "banner", picture()))[0] == 400                      # نوع نامعتبر
    assert (await upload(client, "cover", b"0" * (7 * 1024 * 1024)))[0] == 413        # خیلی بزرگ
    assert (await upload(client, "cover", picture(), who=BUYER))[0] == 403            # بدون فروشگاه
    await attacker_shop()
    r = await client.post("/api/images?kind=cover", headers=forged(OWNER), data=picture())
    assert r.status == 403                                                            # امضای ربات دیگر


async def test_look_theme_cover_logo_and_cleanup(env, client):  # noqa: F811
    _, sc = await create(client, title="ویژه")
    _, c1 = await upload(client, "cover", picture())
    _, logo = await upload(client, "logo", picture())
    r = await client.patch("/api/look", headers=owner(), json={"sc": sc["id"], "theme": "sunset", "cover": c1["id"],
                                                              "logo": logo["id"]})
    pick = lambda d: {k: d[k] for k in ("theme", "cover", "logo")}  # noqa: E731
    assert r.status == 200 and pick(await r.json()) == {"theme": "sunset", "cover": c1["id"], "logo": logo["id"]}
    page = await (await client.get(f"/api/sc/{sc['code']}", headers=as_user(BUYER))).json()
    assert pick(page["look"]) == {"theme": "sunset", "cover": c1["id"], "logo": logo["id"]}
    store = await (await client.get(f"/api/store/{SHOP_ID}", headers=as_user(BUYER))).json()
    assert pick(store["look"]) == {"theme": "soft", "cover": None, "logo": logo["id"]}     # لوگو برای همه، تم جدا
    assert (await client.patch("/api/look", headers=owner(), json={"theme": "noir"})).status == 200  # ویترین اصلی
    # بنر تازه: قبلی پاک می‌شود
    _, c2 = await upload(client, "cover", picture())
    await client.patch("/api/look", headers=owner(), json={"sc": sc["id"], "cover": c2["id"]})
    async with SessionLocal() as s:
        assert await s.get(Image, c1["id"]) is None and await s.get(Image, c2["id"]) is not None
    # خطاها: تم ناشناخته، عکس کس دیگر، ویترین کس دیگر، خریدار
    assert (await client.patch("/api/look", headers=owner(), json={"theme": "pink"})).status == 400
    assert (await client.patch("/api/look", headers=owner(), json={"cover": "nope"})).status == 400
    assert (await client.patch("/api/look", headers=owner(), json={"sc": 99999})).status == 404
    assert (await client.patch("/api/look", headers=as_user(BUYER, via_shop=False), json={"theme": "noir"})).status == 403
    await attacker_shop()
    assert (await client.patch("/api/look", headers=forged(OWNER), json={"theme": "noir"})).status == 403


async def test_qr_only_for_telegram_links(env, client):  # noqa: F811
    r = await client.get("/api/qr", params={"text": "https://ble.ir/bot?start=sc_abc"}, headers=as_user(BUYER))
    rows = (await r.json())["rows"]
    assert r.status == 200 and len(rows) == len(rows[0]) >= 21 and set("".join(rows)) <= {"0", "1"}
    for bad in ("https://evil.example", "javascript:alert(1)", "https://ble.ir/" + "a" * 300):
        assert (await client.get("/api/qr", params={"text": bad}, headers=as_user(BUYER))).status == 400


async def test_checklist_data_in_me(env, client):  # noqa: F811
    me = (await (await client.get("/api/me", headers=owner())).json())["shop"]
    assert me["showcases"] == 0 and me["has_look"] is False and me["total_n"] == 0
    await create(client, title="یک")
    await client.patch("/api/look", headers=owner(), json={"theme": "aurora"})
    me = (await (await client.get("/api/me", headers=owner())).json())["shop"]
    assert me["showcases"] == 1 and me["has_look"] is True


async def test_story_card_temporary_public_link(env, client):  # noqa: F811
    r = await client.post("/api/story", headers=as_user(OWNER, via_shop=False), data=picture(size=(1080, 1920)))
    url = (await r.json())["url"]
    assert r.status == 200 and url.startswith("/story/")
    got = await client.get(url)                                   # تلگرام بدون امضا دانلودش می‌کند
    assert got.status == 200 and got.headers["Content-Type"] == "image/jpeg"
    assert (await client.get("/story/nothing.jpg")).status == 404
    assert (await client.post("/api/story", headers=as_user(OWNER, via_shop=False), data=picture())).status == 400   # اندازه‌ی غلط
    assert (await client.post("/api/story", headers=as_user(OWNER, via_shop=False), data=b"<html>")).status == 400
    assert (await client.post("/api/story", headers=as_user(BUYER), data=picture(size=(1080, 1920)))).status == 403


async def test_style_and_social_links(env, client):  # noqa: F811
    from tests.test_flows import make_product
    a, b = await make_product(env, price=10), await make_product(env, price=20)
    _, sc = await create(client, title="ویژه", items=[{"id": a.id}])
    look = lambda r: r.json()  # noqa: E731
    r = await client.patch("/api/look", headers=owner(), json={"sc": sc["id"], "style": {
        "card": "polaroid", "layout": "list", "accent": "rose", "buttons": "outline", "stats": False, "pinned": a.id}})
    st = (await look(r))["style"]
    assert r.status == 200 and st["card"] == "polaroid" and st["layout"] == "list" and st["stats"] is False
    assert st["pinned"] == a.id and st["others"] is True                      # بقیه پیش‌فرض می‌مانند
    # جزئی: فقط یک کلید عوض می‌شود
    st = (await look(await client.patch("/api/look", headers=owner(), json={"sc": sc["id"], "style": {"card": "sharp"}})))["style"]
    assert st["card"] == "sharp" and st["layout"] == "list"
    # ویترین اصلی استایل خودش را دارد
    assert (await (await client.get(f"/api/store/{SHOP_ID}", headers=as_user(BUYER))).json())["look"]["style"]["card"] == "round"
    page = await (await client.get(f"/api/sc/{sc['code']}", headers=as_user(BUYER))).json()
    assert page["look"]["style"]["card"] == "sharp" and page["look"]["style"]["pinned"] == a.id
    # فقط گزینه‌های مجاز؛ سنجاق فقط محصول همین ویترین
    for bad in ({"card": "circle"}, {"layout": "masonry"}, {"accent": "#ff0000"}, {"stats": "no"}, {"css": "x"},
                {"pinned": "1"}, {"pinned": True}, "x", []):
        assert (await client.patch("/api/look", headers=owner(), json={"style": bad})).status == 400, bad
    assert (await client.patch("/api/look", headers=owner(), json={"sc": sc["id"], "style": {"pinned": b.id}})).status == 400
    assert (await client.patch("/api/look", headers=owner(), json={"style": {"pinned": 999999}})).status == 400
    assert (await client.patch("/api/look", headers=owner(), json={"style": {"pinned": b.id}})).status == 200   # اصلی

    # لینک‌ها: فقط https و دامنه‌ی همان شبکه؛ «website» هر سایت https
    r = await client.patch("/api/look", headers=owner(), json={"links": [
        {"kind": "instagram", "url": "instagram.com/my.page"}, {"kind": "telegram", "url": "https://t.me/mychannel"},
        {"kind": "website", "url": "https://example.com/shop?a=1#frag"}, {"kind": "youtube", "url": ""}]})
    links = (await r.json())["links"]
    assert r.status == 200 and links == [
        {"kind": "instagram", "url": "https://instagram.com/my.page"}, {"kind": "telegram", "url": "https://t.me/mychannel"},
        {"kind": "website", "url": "https://example.com/shop?a=1"}]
    assert (await (await client.get(f"/api/sc/{sc['code']}", headers=as_user(BUYER))).json())["look"]["links"] == links
    for bad in ([{"kind": "instagram", "url": "https://evil.com/instagram.com"}],
                [{"kind": "instagram", "url": "https://instagram.com.evil.com/x"}],
                [{"kind": "website", "url": "javascript:alert(1)"}], [{"kind": "website", "url": "http://plain.com"}],
                [{"kind": "website", "url": "https://user:pw@site.com"}], [{"kind": "website", "url": 'https://a.com/"><img'}],
                [{"kind": "telegram", "url": "https://ble.ir/a"}, {"kind": "telegram", "url": "https://ble.ir/b"}],
                [{"kind": "mastodon", "url": "https://m.social/x"}], {"kind": "x"}, "x",
                [{"kind": "website", "url": "https://" + "a" * 300 + ".com"}]):
        assert (await client.patch("/api/look", headers=owner(), json={"links": bad})).status == 400, bad
    me = (await (await client.get("/api/me", headers=owner())).json())["shop"]
    assert me["has_look"] is True


async def test_background_header_font(env, client):  # noqa: F811
    _, sc = await create(client, title="پس‌زمینه")
    st, bg = await upload(client, "background", picture(size=(900, 900)))
    async with SessionLocal() as s:
        assert st == 200 and PILImage.open(io.BytesIO((await s.get(Image, bg["id"])).data)).size == (1080, 1920)
    r = await client.patch("/api/look", headers=owner(), json={"sc": sc["id"], "background": bg["id"],
                                                              "style": {"header": "center", "font": "plex"}})
    look = await r.json()
    assert r.status == 200 and look["background"] == bg["id"] and look["style"]["header"] == "center"
    assert look["style"]["font"] == "plex"
    page = await (await client.get(f"/api/sc/{sc['code']}", headers=as_user(BUYER))).json()
    assert page["look"]["background"] == bg["id"]
    assert (await (await client.get(f"/api/store/{SHOP_ID}", headers=as_user(BUYER))).json())["look"]["background"] is None
    for bad in ({"header": "left"}, {"font": "comic"}):
        assert (await client.patch("/api/look", headers=owner(), json={"style": bad})).status == 400
    # حذف پس‌زمینه: عکس هم پاک می‌شود
    await client.patch("/api/look", headers=owner(), json={"sc": sc["id"], "background": None})
    async with SessionLocal() as s:
        assert await s.get(Image, bg["id"]) is None


async def test_upload_cap_and_orphan_cleanup(env, client, monkeypatch):  # noqa: F811
    from datetime import datetime, timedelta
    from app import looks
    monkeypatch.setattr(looks, "UPLOADS_PER_DAY", 2)
    _, a = await upload(client, "logo", picture())
    _, b = await upload(client, "logo", picture())
    assert (await upload(client, "logo", picture()))[0] == 429                     # سقف روزانه
    await client.patch("/api/look", headers=owner(), json={"logo": a["id"]})       # a استفاده شد، b یتیم
    async with SessionLocal() as s:
        for img in (await s.scalars(__import__("sqlalchemy").select(Image))).all():
            img.created_at = datetime.utcnow() - timedelta(days=2)
        await s.commit()
        assert await looks.cleanup_orphans(s) == 1
        assert await s.get(Image, a["id"]) is not None and await s.get(Image, b["id"]) is None


async def test_invoice_rate_limit(env, client, monkeypatch):  # noqa: F811
    from app import web as w
    from tests.test_flows import make_product
    c = await make_product(env, price=10)
    w._rates.clear()
    monkeypatch.setattr(w, "rate_ok", lambda key, limit, window, _orig=w.rate_ok: _orig(key, 2, window))
    codes = [(await client.post(f"/api/store/{SHOP_ID}/invoice/{c.id}", headers=as_user(BUYER), json={})).status for _ in range(3)]
    assert codes == [200, 200, 429]
