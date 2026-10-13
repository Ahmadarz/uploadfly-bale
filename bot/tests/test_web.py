"""API مینی‌اپ: ورود امضاشده، ویترین، خرید، نمایش و بازپرداخت از داخل Mini App، دسترسی‌ها."""
import hashlib
import hmac
import json
import re
import time
from urllib.parse import urlencode

import pytest
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy import select

from app.config import settings
from app.db import Content, Purchase, SessionLocal
from app.web import make_app
from tests.conftest import BUYER, OWNER, SHOP_ID, STRANGER
from tests.test_flows import make_product, pay

SHOP_TOKEN = f"{SHOP_ID}:" + "A" * 35


def signed(token: str, uid: int, age: int = 0, lang: str | None = None) -> str:
    tg_user = {"id": uid, "first_name": "T", **({"language_code": lang} if lang else {})}
    data = {"auth_date": str(int(time.time()) - age), "query_id": "q",
            "user": json.dumps(tg_user, separators=(",", ":"))}
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def as_user(uid: int, via_shop: bool = True) -> dict:
    token = SHOP_TOKEN if via_shop else settings.bot_token
    return {"Authorization": "tma " + signed(token, uid), "X-Bot-Id": str(SHOP_ID) if via_shop else ""}


@pytest.fixture
async def client(env):
    c = TestClient(TestServer(make_app(env.manager, "Uploadfly_Bot")))
    await c.start_server()
    yield c
    await c.close()


async def test_auth_rejects_missing_forged_and_old(client):
    assert (await client.get("/api/me")).status == 401
    forged = as_user(BUYER)
    forged["Authorization"] = forged["Authorization"].replace("first_name", "first_namX")
    assert (await client.get("/api/me", headers=forged)).status == 401
    old = {"Authorization": "tma " + signed(settings.bot_token, BUYER, age=2 * 86400)}
    assert (await client.get("/api/me", headers=old)).status == 401
    shop_signed_without_bot_id = {"Authorization": "tma " + signed(SHOP_TOKEN, BUYER)}
    assert (await client.get("/api/me", headers=shop_signed_without_bot_id)).status == 401


async def test_store_lists_only_published_products(env, client):
    c = await make_product(env, price=10, title="عنوان")
    await env.feed(env.shop, __import__("tests.conftest", fromlist=["photo_message"]).photo_message(OWNER))  # پیش‌نویس
    data = await (await client.get(f"/api/store/{SHOP_ID}", headers=as_user(BUYER))).json()
    assert [i["id"] for i in data["items"]] == [c.id]
    item = data["items"][0]
    assert item["title"] == "عنوان" and item["price"] == 10 and not item["bought"] and item["images"] == 1
    # همان ویترین از داخل Mini App ربات اصلی هم باز می‌شود (دکمه‌ی «دیدن ویترین» در داشبورد)
    assert (await client.get(f"/api/store/{SHOP_ID}", headers=as_user(OWNER, via_shop=False))).status == 200


async def test_buy_in_mini_app_then_show_in_chat(env, client):
    c = await make_product(env, price=10)
    r = await (await client.post(f"/api/store/{SHOP_ID}/invoice/{c.id}", headers=as_user(BUYER), json={})).json()
    assert r["invoice"].startswith("https://ble.ir/$")
    link = env.tg.sent(SHOP_ID, "CreateInvoiceLink")[0]
    assert link["currency"] == "XTR" and link["payload"] == f"c:{c.id}"

    # پرداخت هنوز به ربات نرسیده
    assert (await client.post(f"/api/store/{SHOP_ID}/open/{c.id}", headers=as_user(BUYER))).status == 409

    await pay(env, c, charge="web-1")
    env.tg.clear()
    data = await (await client.get(f"/api/store/{SHOP_ID}", headers=as_user(BUYER))).json()
    assert data["items"][0]["bought"] and not data["items"][0]["opened"]

    r = await client.post(f"/api/store/{SHOP_ID}/open/{c.id}", headers=as_user(BUYER))
    assert r.status == 200 and (await r.json())["chat"] == f"https://ble.ir/bot{SHOP_ID}"
    sent = env.tg.sent(SHOP_ID, "SendPhoto")
    assert sent[-1]["chat_id"] == BUYER and sent[-1]["photo"] == c.file_id and sent[-1]["protect_content"]

    # بعد از نمایش، بازپرداخت نه
    r = await client.post(f"/api/store/{SHOP_ID}/refund/{c.id}", headers=as_user(BUYER))
    assert r.status == 400 and (await r.json())["error"] == "refund_opened"


async def test_refund_in_mini_app_before_viewing(env, client):
    c = await make_product(env, price=10)
    await pay(env, c, charge="web-2")
    r = await client.post(f"/api/store/{SHOP_ID}/refund/{c.id}", headers=as_user(BUYER))
    assert r.status == 200 and (await r.json())["refunded"] == 10
    assert env.tg.sent(SHOP_ID, "RefundStarPayment")[0]["telegram_payment_charge_id"] == "web-2"
    async with SessionLocal() as s:
        assert (await s.scalar(select(Purchase).where(Purchase.charge_id == "web-2"))).refunded


async def test_free_and_owner_items_open_in_chat_without_invoice(env, client):
    free = await make_product(env, price=0)
    r = await (await client.post(f"/api/store/{SHOP_ID}/invoice/{free.id}", headers=as_user(BUYER), json={})).json()
    assert r == {"open": f"https://ble.ir/bot{SHOP_ID}?start={free.code}"}
    paid = await make_product(env, price=7)
    r = await (await client.post(f"/api/store/{SHOP_ID}/invoice/{paid.id}", headers=as_user(OWNER), json={})).json()
    assert "open" in r and env.tg.sent(SHOP_ID, "CreateInvoiceLink") == []


async def test_store_images_never_expose_original(env, client):
    c = await make_product(env, price=10)
    r = await client.get(f"/api/store/{SHOP_ID}/img/{c.id}/0", headers=as_user(BUYER))
    assert r.status == 200 and r.headers["Content-Type"] == "image/jpeg"
    # فقط پیش‌نمایش ساخته‌شده‌ی سیستم دانلود شد، نه file_id اصلی
    downloads = [p for _, m, p in env.tg.calls if m == "GetFile"]
    assert all(p["file_id"] != c.file_id for p in downloads)


async def test_owner_api_is_private(env, client):
    c = await make_product(env, price=10)
    assert (await client.get(f"/api/products/{c.id}", headers=as_user(STRANGER, via_shop=False))).status == 404
    assert (await client.patch(f"/api/products/{c.id}", headers=as_user(STRANGER, via_shop=False),
                               json={"price": 1})).status == 404
    r = await client.patch(f"/api/products/{c.id}", headers=as_user(OWNER, via_shop=False), json={"price": -1})
    assert r.status == 400


async def test_publish_category_is_optional_and_saves_fields(env, client):
    from tests.conftest import photo_message
    h = as_user(OWNER, via_shop=False)
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        draft = await s.scalar(select(Content).order_by(Content.id.desc()))
    r = await client.patch(f"/api/products/{draft.id}", headers=h, json={"price": 10, "publish": True})
    body = await r.json()
    assert r.status == 200 and body["status"] == "active" and body["category"] is None  # بدون دسته هم منتشر می‌شود
    r = await client.patch(f"/api/products/{draft.id}", headers=h, json={
        "category": "music", "title": "آهنگ", "description": "توضیح"})
    body = await r.json()
    assert body["category"] == "music" and body["title"] == "آهنگ"
    assert (await (await client.patch(f"/api/products/{draft.id}", headers=h, json={"category": None})).json())["category"] is None
    assert (await client.patch(f"/api/products/{draft.id}", headers=h, json={"category": "weapons"})).status == 400


async def test_static_files_are_compressed_versioned_and_safe(client):
    page = await client.get("/", headers={"Accept-Encoding": "gzip"})
    html = await page.text()
    assert page.headers.get("Content-Encoding") == "gzip" and page.headers["Cache-Control"] == "no-cache"
    assert all(f"/static/{n}?v=" in html for n in ("app.js", "app.css", "tokens.css"))
    js = await client.get("/static/app.js?v=1", headers={"Accept-Encoding": "gzip"})
    assert js.status == 200 and js.headers.get("Content-Encoding") == "gzip" and "immutable" in js.headers["Cache-Control"]
    font = await client.get("/static/fonts/onest-latin-wght-normal.woff2")
    assert font.status == 200 and font.headers["Content-Type"] == "font/woff2"
    for bad in ("/static/../.env", "/static/%2e%2e/.env", "/static/..%2fuploadfly.db", "/static/../app/config.py"):
        assert (await client.get(bad)).status == 404, bad


async def test_translations_are_served_and_complete(client):
    """هر ۵ زبان Mini App: فایل سرو شود، کلیدها و جاهای خالی ({n} و ...) با انگلیسی یکی باشد."""
    def flat(d, p=""):
        for k, v in d.items():
            yield from flat(v, p + k + ".") if isinstance(v, dict) else [(p + k, v)]
    dicts = {}
    for lang in ("fa",):   # نسخه‌ی بله فقط فارسی است
        r = await client.get(f"/static/i18n/{lang}.json?v=1")
        assert r.status == 200 and r.headers["Content-Type"].startswith("application/json")
        dicts[lang] = dict(flat(await r.json()))
    for lang, d in dicts.items():
        assert d.keys() == dicts["fa"].keys(), lang
        for k, v in dicts["fa"].items():
            assert set(re.findall(r"\{\w+\}", v)) == set(re.findall(r"\{\w+\}", d[k])), (lang, k)
    # هر کلیدی که صفحه استفاده می‌کند ترجمه دارد
    html = (await (await client.get("/")).text())
    for key in re.findall(r'data-i18n(?:-ph)?="(\w+)"', html):
        assert key in dicts["fa"], key


async def test_my_purchases_are_private(env, client):
    c = await make_product(env, price=10, title="خرید من")
    await pay(env, c, buyer=BUYER, charge="pp-1")
    mine = (await (await client.get("/api/purchases", headers=as_user(BUYER, via_shop=False))).json())["items"]
    assert len(mine) == 1 and mine[0]["title"] == "خرید من" and mine[0]["opened"] is False
    assert mine[0]["link"] == f"https://ble.ir/bot{SHOP_ID}?start={c.code}"
    others = (await (await client.get("/api/purchases", headers=as_user(STRANGER, via_shop=False))).json())["items"]
    assert others == []


async def test_refunded_purchase_hidden_from_my_purchases(env, client):
    c = await make_product(env, price=10)
    await pay(env, c, charge="pp-2")
    await client.post(f"/api/store/{SHOP_ID}/refund/{c.id}", headers=as_user(BUYER))
    assert (await (await client.get("/api/purchases", headers=as_user(BUYER, via_shop=False))).json())["items"] == []


async def test_disconnect_shop_from_profile(env, client):
    assert (await client.post("/api/shop/disconnect", headers=as_user(STRANGER, via_shop=False))).status == 404
    assert (await client.post("/api/shop/disconnect", headers=as_user(OWNER, via_shop=False))).status == 200
    me = await (await client.get("/api/me", headers=as_user(OWNER, via_shop=False))).json()
    assert me["shop"] is None and me["create_link"] == "https://ble.ir/Uploadfly_Bot?start=connect"


async def test_index_works_without_logo(client, monkeypatch, tmp_path):
    """باگ پیدا‌شده در تست Docker: روی سرور تازه logo.jpg هنوز نیست و صفحه‌ی اصلی خطای ۵۰۰ می‌داد."""
    import shutil
    from app import web as webmod
    for name in ("index.html", "app.css", "app.js"):
        shutil.copy(webmod.WEBAPP_DIR / name, tmp_path / name)
    monkeypatch.setattr(webmod, "WEBAPP_DIR", tmp_path)
    r = await client.get("/")
    assert r.status == 200 and "/static/logo.png?v=0" in await r.text()


async def test_translation_change_refreshes_app_version():
    """ترجمه‌ها با نسخه‌ی app.js دانلود و یک سال کش می‌شوند؛ تغییر ترجمه باید نسخه را عوض کند."""
    import os
    from app.web import WEBAPP_DIR, asset_version
    path = WEBAPP_DIR / "i18n" / "fa.json"
    st = path.stat()
    try:
        os.utime(path, (st.st_atime, st.st_mtime + 10_000_000))
        assert asset_version("app.js") == str(int(st.st_mtime + 10_000_000))
    finally:
        os.utime(path, (st.st_atime, st.st_mtime))
    # app.js نسخه را از تگ خودش می‌خواند، نه از telegram-web-app.js
    assert 'script[src*="/static/app.js"]' in (WEBAPP_DIR / "app.js").read_text()


async def test_me_counts_active_products_by_kind(env, client):
    await make_product(env, price=10)
    await make_product(env, price=0)
    from tests.conftest import photo_message
    await env.feed(env.shop, photo_message(OWNER))   # پیش‌نویس: شمرده نمی‌شود
    me = await (await client.get("/api/me", headers=as_user(OWNER, via_shop=False))).json()
    assert me["shop"]["kinds"] == {"photo": 2}


async def test_product_can_be_hidden_from_store_but_link_still_sells(env, client):
    """«نمایش در ویترین» خاموش: در ویترین نیست، ولی لینک خودش کار می‌کند و قابل خرید است."""
    from tests.conftest import message
    shown = await make_product(env, price=10, title="در ویترین")
    hidden = await make_product(env, price=20, title="فروش جدا")
    h = as_user(OWNER, via_shop=False)
    p = await (await client.get(f"/api/products/{hidden.id}", headers=h)).json()
    assert p["in_store"] is True                                     # پیش‌فرض: در ویترین
    r = await client.patch(f"/api/products/{hidden.id}", headers=h, json={"in_store": False})
    assert (await r.json())["in_store"] is False
    titles = [i["title"] for i in (await (await client.get(f"/api/store/{SHOP_ID}", headers=as_user(BUYER))).json())["items"]]
    assert titles == ["در ویترین"]
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, f"/start {hidden.code}"))   # لینک مستقیم هنوز فاکتور می‌دهد
    assert env.tg.sent(SHOP_ID, "SendInvoice")
    # مدیریت محصولات صاحب فروشگاه هر دو را نشان می‌دهد
    items = (await (await client.get("/api/products?tab=active", headers=h)).json())["items"]
    assert {i["id"]: i["in_store"] for i in items} == {shown.id: True, hidden.id: False}
    # در حالت پیش‌نویس هم می‌شود همان اول خاموشش کرد
    from tests.conftest import photo_message
    from app.db import Content
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        draft = await s.scalar(select(Content).order_by(Content.id.desc()))
    r = await client.patch(f"/api/products/{draft.id}", headers=h, json={"price": 5, "publish": True, "in_store": False})
    body = await r.json()
    assert body["status"] == "active" and body["in_store"] is False


async def test_free_links_in_mini_app(env, client):
    """لینک‌های رایگان ربات اصلی در Mini App: فقط مال خود کاربر، با تصویر کوچک، قابل خاموش کردن."""
    from tests.conftest import MAIN_ID, STRANGER, message, photo_message
    await env.feed(env.main, photo_message(BUYER))
    await env.feed(env.main, message(BUYER, "یک متن رایگان"))
    await env.feed(env.main, photo_message(STRANGER))
    h = as_user(BUYER, via_shop=False)
    items = (await (await client.get("/api/links", headers=h)).json())["items"]
    assert [i["kind"] for i in items] == ["text", "photo"]
    assert items[1]["link"].startswith("https://ble.ir/Uploadfly_Bot?start=") and items[0]["text"] == "یک متن رایگان"
    photo_id = items[1]["id"]
    r = await client.get(f"/api/links/{photo_id}/thumb", headers=h)
    assert r.status == 200 and r.headers["Content-Type"] == "image/jpeg"
    # دیگران نه می‌بینند نه خاموش می‌کنند
    hs = as_user(STRANGER, via_shop=False)
    assert (await client.get(f"/api/links/{photo_id}/thumb", headers=hs)).status == 404
    assert (await client.post(f"/api/links/{photo_id}/disable", headers=hs)).status == 404
    # محصول فروشگاه از این مسیر قابل دسترسی نیست
    c = await make_product(env, price=10)
    assert (await client.post(f"/api/links/{c.id}/disable", headers=as_user(OWNER, via_shop=False))).status == 404
    # خاموش کردن: از لیست می‌رود و لینک دیگر کار نمی‌کند
    assert (await client.post(f"/api/links/{photo_id}/disable", headers=h)).status == 200
    assert [i["id"] for i in (await (await client.get("/api/links", headers=h)).json())["items"]] == [items[0]["id"]]
    from app.db import Content
    async with SessionLocal() as s:
        code = (await s.get(Content, photo_id)).code
    env.tg.clear()
    await env.feed(env.main, message(STRANGER, f"/start {code}"))
    assert "وجود نداره" in env.tg.texts(MAIN_ID)


async def test_client_error_report_is_logged_safely(client, caplog):
    caplog.set_level("WARNING", logger="app.web")
    assert (await client.post("/api/client-error", json={"message": "x"})).status == 401   # بدون امضا نه
    r = await client.post("/api/client-error", headers=as_user(BUYER),
                          json={"message": "boom\nFAKE LOG LINE " + "a" * 1000, "where": "app.js:1:2", "page": "page-store"})
    assert r.status == 200
    line = [m.getMessage() for m in caplog.records if "Mini App error" in m.getMessage()][-1]
    assert "\n" not in line and len(line) < 800 and "page-store" in line
    for _ in range(30):
        await client.post("/api/client-error", headers=as_user(BUYER), json={"message": "spam"})
    assert sum("spam" in m.getMessage() for m in caplog.records) < 20                        # سقف هر کاربر


ATTACK_ID = 3000003
ATTACK_TOKEN = f"{ATTACK_ID}:" + "B" * 35


async def attacker_shop():
    from app.crypto import encrypt
    from app.db import Seller
    async with SessionLocal() as s:
        s.add(Seller(owner_id=STRANGER, bot_id=ATTACK_ID, bot_username="attackbot", token_enc=encrypt(ATTACK_TOKEN)))
        await s.commit()


def forged(uid: int) -> dict:
    """فروشنده‌ی بدجنس با توکن ربات خودش initData را به اسم یک نفر دیگر امضا می‌کند."""
    return {"Authorization": "tma " + signed(ATTACK_TOKEN, uid), "X-Bot-Id": str(ATTACK_ID)}


async def test_seller_bot_signature_cannot_impersonate_on_other_pages(env, client):
    c = await make_product(env, price=10, title="کالا")
    p = await pay(env, c, buyer=BUYER, charge="atk-1")
    await attacker_shop()
    _, sc = (await client.post("/api/showcases", headers=as_user(OWNER, via_shop=False),
                               json={"title": "عضویت", "access": "once", "price": 5})).status, None
    sc = (await (await client.get("/api/showcases", headers=as_user(OWNER, via_shop=False))).json())["items"][0]

    # داشبورد، کیف پول، خریدها، لینک‌ها و تنظیمات قربانی بسته است
    for method, path, body in [
        ("GET", "/api/products", None), (f"GET", f"/api/products/{c.id}", None),
        ("PATCH", f"/api/products/{c.id}", {"price": 1}), ("GET", "/api/wallet", None),
        ("POST", "/api/wallet/premium", {"months": 3}), ("POST", "/api/shop/disconnect", {}),
        ("GET", "/api/purchases", None), ("GET", "/api/links", None), ("GET", "/api/showcases", None),
        ("PATCH", f"/api/showcases/{sc['id']}", {"title": "x"}), ("DELETE", f"/api/showcases/{sc['id']}", None),
        ("PATCH", "/api/me", {"lang": "en"}),
    ]:
        for victim in (OWNER, BUYER):
            r = await client.request(method, path, headers=forged(victim), json=body)
            assert r.status == 403, (method, path, victim, r.status)
    # /api/me فقط زبان، بدون اطلاعات فروشگاه
    me = await (await client.get("/api/me", headers=forged(OWNER))).json()
    assert me["shop"] is None and me["create_link"] is None
    # فروشگاه و ویترین فروشنده‌ی دیگر هم از این امضا در دسترس نیست (بازپرداخت، امتیاز، تمدید)
    for method, path in [("GET", f"/api/store/{SHOP_ID}"), ("POST", f"/api/store/{SHOP_ID}/refund/{c.id}"),
                         ("POST", f"/api/store/{SHOP_ID}/rate/{c.id}"), ("POST", f"/api/store/{SHOP_ID}/open/{c.id}")]:
        assert (await client.request(method, path, headers=forged(BUYER), json={"stars": 1})).status == 403, path
    for path in (f"/api/sc/{sc['code']}", f"/api/sc/{sc['code']}/renewal", f"/api/sc/{sc['code']}/refund"):
        r = await client.request("GET" if path.count("/") == 3 else "POST", path, headers=forged(BUYER), json={"cancel": False})
        assert r.status == 404, path
    async with SessionLocal() as s:
        assert (await s.get(Purchase, p.id)).refunded is False
    # فروشگاه خود مهاجم کار می‌کند؛ صاحب واقعی در ربات خودش همه‌چیز دارد
    assert (await client.get(f"/api/store/{ATTACK_ID}", headers=forged(BUYER))).status == 200
    assert (await client.get("/api/products", headers=as_user(OWNER))).status == 200
    assert (await (await client.get("/api/me", headers=as_user(OWNER))).json())["shop"] is not None
    # خریدار واقعی در ربات همان فروشگاه
    assert (await client.get(f"/api/store/{SHOP_ID}", headers=as_user(BUYER))).status == 200
    assert (await client.get(f"/api/sc/{sc['code']}", headers=as_user(BUYER))).status == 200


async def test_mini_app_first_contact_source(env, client):
    from app.db import User as U
    await client.get("/api/me", headers=as_user(7001, via_shop=False))
    await client.get(f"/api/store/{SHOP_ID}", headers=as_user(7002))
    async with SessionLocal() as s:
        assert (await s.get(U, 7001)).source == "miniapp" and (await s.get(U, 7002)).source == "shop"
