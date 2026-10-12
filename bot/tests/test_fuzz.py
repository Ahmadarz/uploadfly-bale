"""فاز: هیچ ورودی بدی نباید خطای ۵۰۰ بدهد."""
import itertools
from tests.conftest import BUYER, OWNER, SHOP_ID
from tests.test_flows import make_product, pay
from tests.test_web import as_user, client  # noqa: F401

BAD = [None, "", "abc", -1, 0, 10**12, 1.5, [], {}, "x" * 5000, "<script>", "2020-01-01", "9999-99-99", True, "1e9", "٣"]


async def test_fuzz_no_500(env, client):  # noqa: F811
    c = await make_product(env, price=10)
    await pay(env, c, charge="fz")
    r = await client.post("/api/showcases", headers=as_user(OWNER, via_shop=False), json={"title": "t"})
    sc = await r.json()
    sid, code = sc["id"], sc["code"]
    o, b = as_user(OWNER, via_shop=False), as_user(BUYER)
    fields = {
        ("PATCH", f"/api/products/{c.id}"): ["title", "description", "price", "category", "sensitive", "allow_save",
                                             "in_store", "archived", "expires_at", "showcases"],
        ("POST", "/api/showcases"): ["title", "description", "access", "price", "private", "expires_at", "items"],
        ("PATCH", f"/api/showcases/{sid}"): ["title", "description", "access", "price", "private", "expires_at",
                                             "archived", "items"],
        ("PATCH", "/api/me"): ["lang"],
        ("POST", "/api/wallet/premium"): ["months"],
        ("POST", f"/api/store/{SHOP_ID}/rate/{c.id}"): ["stars"],
        ("POST", f"/api/sc/{code}/renewal"): ["cancel"],
        ("POST", "/api/client-error"): ["message", "where", "page"],
        ("PATCH", "/api/look"): ["sc", "theme", "cover", "logo", "style", "links"],
    }
    fails = []
    for (method, path), keys in fields.items():
        h = b if "/store/" in path or "/sc/" in path else o
        for k, v in itertools.product(keys, BAD):
            r = await client.request(method, path, headers=h, json={k: v})
            if r.status >= 500:
                fails.append((method, path, k, repr(v)[:30], r.status))
        for raw in ("not json", "[]", "null", "1", '"x"'):
            r = await client.request(method, path, headers={**h, "Content-Type": "application/json"}, data=raw)
            if r.status >= 500:
                fails.append((method, path, "RAW", raw, r.status))
    for path in ["/api/products/abc", "/api/products/999999", "/api/products/-1/thumb", "/api/showcases/x",
                 f"/api/store/abc", "/api/store/99999", f"/api/store/{SHOP_ID}/img/abc/0",
                 f"/api/store/{SHOP_ID}/img/{c.id}/999", f"/api/store/{SHOP_ID}/img/{c.id}/-1",
                 f"/api/store/{SHOP_ID}/audio/x", "/api/sc/../../etc", "/api/sc/" + "a" * 500, "/api/links/x/thumb",
                 "/api/products?tab=zzz", "/api/images/x", "/api/images/" + "z" * 300, "/api/qr", "/api/qr?text=",
                 "/story/../../x.jpg", "/api/products?tab=", "/static/../app/config.py", "/static/%2e%2e/.env"]:
        for h in (o, b):
            r = await client.get(path, headers=h)
            if r.status >= 500:
                fails.append(("GET", path, r.status))
    for path in [f"/api/store/{SHOP_ID}/invoice/x", f"/api/store/{SHOP_ID}/open/999", f"/api/store/{SHOP_ID}/refund/x",
                 f"/api/sc/{code}/open/x", f"/api/sc/{code}/join", f"/api/sc/{code}/refund", "/api/links/x/disable",
                 "/api/shop/disconnect"]:
        r = await client.post(path, headers=b, json={})
        if r.status >= 500:
            fails.append(("POST", path, r.status))
    assert not fails, fails
