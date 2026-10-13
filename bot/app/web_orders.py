"""API مینی‌اپ برای سفارش‌های کالای فیزیکی: فهرست سفارش‌های فروشگاه، ثبت ارسال (کد رهگیری)، لغو سفارش.

فقط صاحب فروشگاه (امضای بازوی اصلی، یا صاحب همان بازوی فروشگاه). مهمانِ بازوی فروشنده به هیچ‌کدام دسترسی ندارد،
چون web.allowed_for_guest فقط مسیرهای ویترین را باز می‌گذارد. نشانی خریدار فقط به فروشنده‌ی همان سفارش داده می‌شود."""
from aiohttp import web
from sqlalchemy import func, select

from app import orders
from app.connect import active_seller
from app.db import Content, Order, SessionLocal, is_id
from app.products import display_title
from app.web import error, get_user, json_object

TABS = {"waiting": ("paid",), "shipped": ("shipped",), "canceled": ("canceled",)}
LIST_LIMIT = 100


def order_json(o: Order, c: Content | None, lang: str = "fa") -> dict:
    iso = lambda d: d.isoformat() + "Z" if d else None   # noqa: E731
    return {"id": o.id, "status": o.status, "content_id": o.content_id,
            "title": display_title(c, lang) if c else "?", "kind": c.kind if c else "document",
            "amount": o.amount, "shipping_fee": o.shipping_fee,
            "name": o.name, "phone": o.phone, "address": o.address, "postal": o.postal_code,
            "tracking": o.tracking, "paid_at": iso(o.paid_at), "shipped_at": iso(o.shipped_at)}


async def waiting_count(session, bot_id: int) -> int:
    return await session.scalar(select(func.count(Order.id)).where(Order.bot_id == bot_id, Order.status == "paid")) or 0


async def api_orders(request: web.Request) -> web.Response:
    tab = request.query.get("tab", "waiting")
    if tab not in TABS:
        return error("bad_request")
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await active_seller(session, user)
        if seller is None:
            return error("no_shop", 403)
        q = select(Order, Content).join(Content, Content.id == Order.content_id, isouter=True).where(
            Order.bot_id == seller.bot_id, Order.status.in_(TABS[tab]))
        # منتظر ارسال: قدیمی‌ترین اول (همان که باید زودتر پست شود)؛ بقیه: تازه‌ترین اول
        rows = (await session.execute(q.order_by(Order.id if tab == "waiting" else Order.id.desc())
                                      .limit(LIST_LIMIT))).all()
        counts = dict((await session.execute(select(Order.status, func.count(Order.id)).where(
            Order.bot_id == seller.bot_id, Order.status != "pending").group_by(Order.status))).all())
    return web.json_response({
        "items": [order_json(o, c, user.language) for o, c in rows],
        "counts": {"waiting": counts.get("paid", 0), "shipped": counts.get("shipped", 0),
                   "canceled": counts.get("canceled", 0)},
        "shipping_fee": seller.shipping_fee or 0})


async def _own_waiting_order(session, request: web.Request):
    """سفارشِ «منتظر ارسال» از فروشگاه خود کاربر + بازوی روشن همان فروشگاه؛ یا پاسخ خطا."""
    user = await get_user(session, request)
    seller = await active_seller(session, user)
    if seller is None:
        return error("no_shop", 403)
    oid = request.match_info["id"]
    order = await session.get(Order, int(oid)) if is_id(oid) else None
    if order is None or order.bot_id != seller.bot_id:
        return error("not_found", 404)
    if order.status != "paid":
        return error("order_closed", 409)
    bot = request.app["manager"].get(seller.bot_id)
    if bot is None:
        return error("shop_offline", 503)
    return user, order, bot


async def api_order_ship(request: web.Request) -> web.Response:
    body = await json_object(request) or {}
    tracking = None
    if body.get("tracking") not in (None, ""):
        tracking = orders.clean_tracking(body["tracking"])
        if tracking is None:
            return error("bad_tracking")
    async with SessionLocal() as session:
        found = await _own_waiting_order(session, request)
        if isinstance(found, web.Response):
            return found
        user, order, bot = found
        await orders.ship_order(session, bot, order, tracking)
        c = await session.get(Content, order.content_id)
        return web.json_response(order_json(order, c, user.language))


async def api_order_cancel(request: web.Request) -> web.Response:
    async with SessionLocal() as session:
        found = await _own_waiting_order(session, request)
        if isinstance(found, web.Response):
            return found
        user, order, bot = found
        await orders.cancel_order(session, bot, order)
        c = await session.get(Content, order.content_id)
        return web.json_response(order_json(order, c, user.language))


def add_routes(app: web.Application) -> None:
    app.router.add_get("/api/orders", api_orders)
    app.router.add_post("/api/orders/{id}/ship", api_order_ship)
    app.router.add_post("/api/orders/{id}/cancel", api_order_cancel)
