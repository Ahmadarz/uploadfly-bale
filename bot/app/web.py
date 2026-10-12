"""Mini App: وب‌سرور داخل همان برنامه‌ی ربات (aiohttp).

امنیت: هر درخواست API باید initData امضاشده‌ی تلگرام را در هدر Authorization داشته باشد.
Mini App یا از ربات اصلی باز می‌شود یا از دکمه‌ای در ربات فروشنده (هدر X-Bot-Id)؛ امضا با توکن
همان ربات بررسی می‌شود، پس کسی نمی‌تواند خودش را جای کاربر دیگری جا بزند.
"""
import asyncio
import hashlib
import io
import json
import logging
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiogram.utils.web_app import WebAppInitData, safe_parse_webapp_init_data
from aiohttp import web
from PIL import Image, ImageFilter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import looks, preview, showcases
from app.bots import BotManager, set_user_menu
from app.config import settings
from app.connect import active_seller, create_bot_link
from app.content import deliver
from app.payments import open_purchase, refund_purchase
from app.crypto import decrypt
from app.db import Image as StoredImage  # نام Image مال Pillow است
from app.db import Content, Purchase, Review, Seller, SessionLocal, Showcase, ShowcaseItem, User, is_id
from app.products import (CATEGORIES, DESCRIPTION_MAX, MAX_PRICE, MIN_PRICE, PRICE_PRESETS, TITLE_MAX, build_preview,
                          invoice_args, publish, rate, ratings_by_content, sales_by_content, shop_rating)
from app.shop import WITHDRAW_MIN, buy_premium, shop_stats, wallet_view
from app.texts import LANGUAGES, T, detect_language
from app.trust import price_cap

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
WEBAPP_DIR = ROOT / "webapp"
THUMB_DIR = ROOT / "cache" / "thumbs"
INIT_DATA_MAX_AGE = 24 * 3600  # initData قدیمی‌تر از ۲۴ ساعت پذیرفته نمی‌شود


def error(code: str, status: int = 400) -> web.Response:
    return web.json_response({"error": code}, status=status)


def is_int(v) -> bool:
    """عدد صحیح واقعی؛ true/false (که در پایتون عدد حساب می‌شوند) و "10" و 1.5 نه."""
    return isinstance(v, int) and not isinstance(v, bool)


async def json_object(request: web.Request) -> dict | None:
    """بدنه‌ی JSON فقط وقتی یک شیء است ({...})؛ هر چیز دیگر (خراب، [] ، null) = None."""
    try:
        body = await request.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


async def token_for(bot_id_header: str) -> tuple[str | None, Seller | None]:
    """توکنی که initData با آن امضا شده: ربات اصلی، یا ربات فروشنده‌ای که Mini App را باز کرده."""
    if not bot_id_header:
        return settings.bot_token, None
    if not is_id(bot_id_header, big=True):
        return None, None
    async with SessionLocal() as session:
        seller = await session.scalar(select(Seller).where(
            Seller.bot_id == int(bot_id_header), Seller.is_active.is_(True)))
    return (decrypt(seller.token_enc), seller) if seller else (None, None)


async def init_data_from(request: web.Request) -> WebAppInitData | None:
    auth = request.headers.get("Authorization", "")
    token, seller = await token_for(request.headers.get("X-Bot-Id", ""))
    if not auth.startswith("tma ") or token is None:
        return None
    try:
        data = safe_parse_webapp_init_data(token, auth[4:])
    except ValueError:
        return None
    if data.user is None or time.time() - data.auth_date.timestamp() > INIT_DATA_MAX_AGE:
        return None
    request["via_seller"] = seller
    return data


_STORE_PATH = re.compile(r"^/api/store/(\d+)(?:/|$)")


def guest_of_seller_bot(request: web.Request) -> int | None:
    """امضای ربات فروشنده فقط برای همان فروشگاه معتبر است.

    فروشنده توکن ربات خودش را دارد، پس می‌تواند initData را به اسم هر کسی امضا کند. برای همین چنین امضایی
    (وقتی کاربر صاحب همان ربات نیست) فقط ویترین و خرید از همان ربات را باز می‌کند، نه داشبورد، کیف پول،
    خریدهای دیگر، یا فروشگاه دیگری. خروجی: شناسه‌ی ربات، یا None اگر محدودیتی نیست.
    """
    seller = request.get("via_seller")
    if seller is None or request["tg_user"].id == seller.owner_id:
        return None
    return seller.bot_id


def allowed_for_guest(request: web.Request, bot_id: int) -> bool:
    path = request.path
    if path.startswith("/api/images/") or path == "/api/qr":
        return request.method == "GET"
    if path == "/api/client-error" or path.startswith("/api/sc/"):  # ویترین‌ها: بررسی ربات در buyer_showcase
        return True
    if path == "/api/me":
        return request.method == "GET"
    m = _STORE_PATH.match(path)
    return bool(m) and int(m.group(1)) == bot_id


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if not request.path.startswith("/api/"):
        return await handler(request)
    data = await init_data_from(request)
    if data is None:
        return error("unauthorized", 401)
    request["tg_user"] = data.user
    guest_of = guest_of_seller_bot(request)
    if guest_of is not None and not allowed_for_guest(request, guest_of):
        return error("forbidden", 403)
    return await handler(request)


async def get_user(session: AsyncSession, request: web.Request) -> User:
    tg_user = request["tg_user"]
    user = await session.get(User, tg_user.id)
    if user is None:  # کسی که Mini App را قبل از /start باز کرده
        user = User(id=tg_user.id, username=tg_user.username, first_name=tg_user.first_name,
                    language=detect_language(tg_user.language_code),
                    source="shop" if request.get("via_seller") else "miniapp")
        session.add(user)
    if user.is_banned:  # کاربر مسدود به هیچ بخشی از Mini App دسترسی ندارد
        raise web.HTTPForbidden(text='{"error": "banned"}', content_type="application/json")
    tz = request.headers.get("X-TZ-Offset", "")
    if tz.lstrip("-").isdigit() and abs(int(tz)) <= 14 * 60 and user.tz_offset != int(tz):
        user.tz_offset = int(tz)
    await session.commit()
    return user


async def owned_content(session: AsyncSession, user: User, content_id: str) -> tuple[Seller, Content] | None:
    """محصولی از فروشگاه همین کاربر؛ هیچ‌کس نمی‌تواند محصول دیگری را ببیند یا تغییر دهد."""
    seller = await active_seller(session, user)
    if seller is None or not is_id(content_id):
        return None
    content = await session.get(Content, int(content_id))
    if content is None or content.bot_id != seller.bot_id or content.owner_id != user.id:
        return None
    return seller, content


async def showcase_ids(session: AsyncSession, content_ids: list[int]) -> dict[int, list[int]]:
    """ویترین‌های اضافه‌ای که هر محصول در آن‌هاست (ویترین اصلی = in_store)."""
    out: dict[int, list[int]] = {}
    if content_ids:
        for cid, sid in (await session.execute(
                select(ShowcaseItem.content_id, ShowcaseItem.showcase_id).join(Showcase, Showcase.id == ShowcaseItem.showcase_id)
                .where(ShowcaseItem.content_id.in_(content_ids), Showcase.is_active.is_(True)))).all():
            out.setdefault(cid, []).append(sid)
    return out


def product_json(c: Content, seller: Seller, stats: dict | None = None, showcases_of: list[int] | None = None) -> dict:
    stats = stats or {"sales": 0, "revenue": 0, "reports": 0}
    status = "draft" if c.is_draft else "active" if c.is_active else "archived"
    return {
        "id": c.id, "kind": c.kind, "name": c.file_name, "size": c.file_size, "duration": c.duration,
        "title": c.title, "description": c.description, "category": c.category,
        "width": c.width, "height": c.height, "price": c.price_stars, "sensitive": c.is_sensitive,
        "allow_save": c.allow_save, "status": status, "views": c.views, "in_store": c.in_store,
        "physical": c.is_physical, "stock": c.stock,
        "showcases": showcases_of or [], "rating": (stats or {}).get("rating"),
        "expires_at": c.expires_at.isoformat() + "Z" if c.expires_at else None,
        "link": f"https://ble.ir/{seller.bot_username}?start={c.code}",
        "has_thumb": c.kind != "text", "text": (preview.plain_text(c)[:80] if c.kind == "text" else None),
        "preview": preview.stored(c).get("text"), "pages": preview.stored(c).get("pages"),
        "created": c.created_at.isoformat() if c.created_at else None, **stats,
        "publish_at": c.publish_at.isoformat() + "Z" if c.publish_at else None, "notified": c.notified_at is not None,
    }


# --- API ---

async def api_me(request: web.Request) -> web.Response:
    manager: BotManager = request.app["manager"]
    async with SessionLocal() as session:
        user = await get_user(session, request)
        if user.is_banned:
            return error("banned", 403)
        # مهمانِ ربات فروشنده فقط زبان و اسم خودش را می‌گیرد (برای ویترین)، نه داشبورد
        seller = None if guest_of_seller_bot(request) is not None else await active_seller(session, user)
        shop = None
        if seller:
            shop = {"bot": seller.bot_username, "bot_id": seller.bot_id, "suspended": seller.is_suspended,
                    "price_cap": await price_cap(session, seller.bot_id),
                    "rating": await shop_rating(session, seller.bot_id),
                    "top": await top_products(session, seller),
                    # تعداد محصولات فعال هر نوع (کاشی‌های «نوع فایل» در خانه)
                    "kinds": dict((await session.execute(
                        select(Content.kind, func.count(Content.id)).where(
                            Content.bot_id == seller.bot_id, Content.is_active.is_(True), Content.is_draft.is_(False))
                        .group_by(Content.kind))).all()),
                    **await shop_stats(session, seller, manager, days=7, tz_offset=user.tz_offset)}
            # چک‌لیست شروع فروشنده (خانه): هر قدم از داده‌ی واقعی
            shop["showcases"] = await session.scalar(select(func.count(Showcase.id)).where(
                Showcase.bot_id == seller.bot_id, Showcase.is_active.is_(True))) or 0
            shop["has_look"] = bool(seller.logo or seller.cover or seller.style or seller.links
                                    or (seller.theme and seller.theme != "soft"))
    return web.json_response({
        "name": user.first_name or "", "lang": user.language, "main_bot": request.app["main_username"],
        "shop": shop, "presets": PRICE_PRESETS, "max_price": MAX_PRICE, "categories": CATEGORIES,
        "title_max": TITLE_MAX, "description_max": DESCRIPTION_MAX, "withdraw_min": WITHDRAW_MIN,
        "username": user.username, "adult_ok": user.adult_ok,
        "support": {"username": settings.support_username, "email": settings.support_email},
        "create_link": None if shop or guest_of_seller_bot(request) is not None
        else create_bot_link(request.app["main_username"], user),
    })


async def api_products(request: web.Request) -> web.Response:
    tab = request.query.get("tab", "active")
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await active_seller(session, user)
        if seller is None:
            return error("no_shop", 403)
        q = select(Content).where(Content.bot_id == seller.bot_id, Content.owner_id == user.id)
        if tab == "draft":
            q = q.where(Content.is_draft.is_(True))
        elif tab == "archived":
            q = q.where(Content.is_draft.is_(False), Content.is_active.is_(False))
        else:
            q = q.where(Content.is_draft.is_(False), Content.is_active.is_(True))
        rows = (await session.scalars(q.order_by(Content.id.desc()).limit(200))).all()
        stats = await sales_by_content(session, [c.id for c in rows])
        for cid, r in (await ratings_by_content(session, [c.id for c in rows])).items():
            stats.setdefault(cid, {"sales": 0, "revenue": 0, "reports": 0})["rating"] = r
        counts = {}
        for name, cond in (("active", (Content.is_draft.is_(False), Content.is_active.is_(True))),
                           ("draft", (Content.is_draft.is_(True),)),
                           ("archived", (Content.is_draft.is_(False), Content.is_active.is_(False)))):
            counts[name] = len((await session.scalars(select(Content.id).where(
                Content.bot_id == seller.bot_id, Content.owner_id == user.id, *cond))).all())
        sc_of = await showcase_ids(session, [c.id for c in rows])
    return web.json_response({"items": [product_json(c, seller, stats.get(c.id), sc_of.get(c.id)) for c in rows],
                              "counts": counts})


async def api_product(request: web.Request) -> web.Response:
    async with SessionLocal() as session:
        user = await get_user(session, request)
        found = await owned_content(session, user, request.match_info["id"])
        if found is None:
            return error("not_found", 404)
        seller, c = found
        stats = await sales_by_content(session, [c.id])
        sc_of = await showcase_ids(session, [c.id])
    return web.json_response(product_json(c, seller, stats.get(c.id), sc_of.get(c.id)))


async def api_product_update(request: web.Request) -> web.Response:
    """تغییر قیمت، حساس، اجازه‌ی کپی، بایگانی، و انتشار پیش‌نویس."""
    manager: BotManager = request.app["manager"]
    body = await json_object(request)
    if body is None:
        return error("bad_request")
    async with SessionLocal() as session:
        user = await get_user(session, request)
        found = await owned_content(session, user, request.match_info["id"])
        if found is None:
            return error("not_found", 404)
        seller, c = found
        bot = manager.get(seller.bot_id)
        if bot is None:
            return error("shop_offline", 503)

        sensitive_changed = False
        if "sensitive" in body and body["sensitive"] is True != c.is_sensitive:
            c.is_sensitive, sensitive_changed = body["sensitive"] is True, True
            if c.is_sensitive:
                c.allow_save = False  # محتوای حساس همیشه محافظت‌شده است
        if "physical" in body and c.is_draft:   # کالای فیزیکی (فقط قبل از انتشار عوض می‌شود)
            c.is_physical = body["physical"] is True
            if c.is_physical:
                c.is_sensitive, c.allow_save = False, False
        if "stock" in body and c.is_physical:   # موجودی: عدد، یا null = نامحدود
            if body["stock"] is not None and (not is_int(body["stock"]) or not 0 <= body["stock"] <= 100_000):
                return error("bad_stock")
            c.stock = body["stock"]
        if "in_store" in body:  # نمایش در ویترین؛ لینک محصول در هر حال کار می‌کند
            c.in_store = body["in_store"] is True
        if isinstance(body.get("showcases"), list):  # ویترین‌های اضافه؛ «رایگان برای اعضا» قبلی حفظ می‌شود
            await set_product_showcases(session, seller, c, body["showcases"])
        if "allow_save" in body:
            if body["allow_save"] and c.is_sensitive:
                return error("sensitive_protected")
            c.allow_save = body["allow_save"] is True
        price = c.price_stars
        if "price" in body:
            if not is_int(body["price"]) or not 0 <= body["price"] <= MAX_PRICE or 0 < body["price"] < MIN_PRICE:
                return error("bad_price")
            # سقف اعتماد فقط وقتی قیمت بالا می‌رود بررسی می‌شود (محصولات قدیمی دست نمی‌خورند)
            if body["price"] > c.price_stars and body["price"] > await price_cap(session, seller.bot_id):
                return error("price_cap")
            price = body["price"]
        if c.is_physical and price == 0 and (body.get("publish") or not c.is_draft):
            return error("bad_price")   # کالای فیزیکی رایگان معنی ندارد
        if "title" in body:
            title = str(body["title"] or "").strip()
            if len(title) > TITLE_MAX:
                return error("title_too_long")
            c.title = title or None
        if "description" in body:
            desc = str(body["description"] or "").strip()
            if len(desc) > DESCRIPTION_MAX:
                return error("description_too_long")
            c.description = desc or None
        if "category" in body:  # اختیاری (مالک تصمیم 2026-10-08)؛ null یعنی بدون دسته
            if body["category"] is not None and body["category"] not in CATEGORIES:
                return error("bad_category")
            c.category = body["category"]
        if "expires_at" in body:  # تاریخ پایان؛ در آن زمان خودکار به آرشیو می‌رود
            exp = showcases.parse_expiry(body["expires_at"])
            if exp == "bad_expiry":
                return error("bad_expiry")
            c.expires_at = exp
        if "archived" in body:
            if c.is_draft:
                return error("draft_cannot_archive")
            c.is_active = body["archived"] is not True
            if c.is_active and c.expires_at and c.expires_at <= showcases.utcnow():
                c.expires_at = None   # بازگرداندن از آرشیو: تاریخ پایانِ گذشته پاک می‌شود

        if "publish_at" in body:   # پست زمان‌بندی‌شده: فقط پیش‌نویس؛ پیش‌نمایش همین حالا ساخته می‌شود
            if not c.is_draft:
                return error("not_draft")
            when = showcases.parse_expiry(body["publish_at"])
            if when == "bad_expiry":
                return error("bad_schedule")
            c.publish_at = when
            if when is not None:
                c.price_stars = price
                if price > 0 and not c.preview:
                    await build_preview(bot, user.id, c, user.language)
        if c.is_draft and body.get("publish"):
            c.publish_at = None
            await publish(bot, user.id, c, price, user.language)
        else:
            c.price_stars = price
            # پیش‌نمایش لازم است اگر پولی شده و ندارد، یا میزان تاری‌اش (حساس) عوض شده
            if not c.is_draft and price > 0 and not c.is_physical and (not c.preview or sensitive_changed):
                c.preview = None
                await build_preview(bot, user.id, c, user.language)
        await session.commit()
        stats = await sales_by_content(session, [c.id])
        sc_of = await showcase_ids(session, [c.id])
    return web.json_response(product_json(c, seller, stats.get(c.id), sc_of.get(c.id)))


async def api_thumb(request: web.Request) -> web.Response:
    """تصویر کوچک محصول برای کارت‌ها. محتوای حساس همیشه از پیش‌نمایش تار نشان داده می‌شود."""
    manager: BotManager = request.app["manager"]
    async with SessionLocal() as session:
        user = await get_user(session, request)
        found = await owned_content(session, user, request.match_info["id"])
    if found is None:
        return error("not_found", 404)
    seller, c = found
    return await thumb_response(manager.get(seller.bot_id), c)


async def thumb_response(bot, c: Content) -> web.StreamResponse:
    """تصویر کوچک یک محتوا (محصول فروشگاه یا لینک رایگان) با رباتی که فایل در آن است."""
    photos = preview.stored(c).get("photos") or []
    if c.is_sensitive:
        source, blur_more = (photos[0] if photos else c.thumb_file_id), not photos
    elif c.kind == "photo":
        source, blur_more = c.file_id, False
    else:
        source, blur_more = c.thumb_file_id or (photos[0] if photos else None), False
    if source is None or bot is None:
        return error("no_thumb", 404)

    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    path = THUMB_DIR / f"{c.id}-{hashlib.sha1(source.encode()).hexdigest()[:10]}{'-b' if blur_more else ''}.jpg"
    if not path.exists():
        try:
            raw = (await bot.download(source)).read()
        except Exception:
            log.warning("Thumbnail download failed for content %s", c.id)
            return error("no_thumb", 404)
        path.write_bytes(await asyncio.to_thread(make_thumb, raw, blur_more))
    return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})


def make_thumb(raw: bytes, blur: bool, size: int = 360) -> bytes:
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img.thumbnail((size, size))
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(radius=max(img.size) * preview.BLUR_SENSITIVE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=75)
    return out.getvalue()


# --- پروفایل ---

async def api_me_update(request: web.Request) -> web.Response:
    body = await json_object(request)
    if body is None:
        return error("bad_request")
    if body.get("lang") not in LANGUAGES:
        return error("bad_lang")
    async with SessionLocal() as session:
        user = await get_user(session, request)
        user.language = body["lang"]  # همان زبانی که /lang در ربات عوض می‌کند
        await session.commit()
    # منوی دستورهای ربات هم به زبان تازه (ربات اصلی، و ربات فروشگاهی که Mini App از آن باز شده)
    manager: BotManager = request.app["manager"]
    bot_id = request.headers.get("X-Bot-Id", "")
    seller_bot = manager.get(int(bot_id)) if is_id(bot_id, big=True) else None
    tg_code = request["tg_user"].language_code
    for bot, is_seller in ((manager.main_bot, False), (seller_bot, True)):
        if bot is not None:
            await set_user_menu(bot, user.id, body["lang"], tg_code, is_seller, force=True)
    return web.json_response({"lang": body["lang"]})


async def top_products(session: AsyncSession, seller: Seller, days: int = 30, limit: int = 3) -> list[dict]:
    """پرفروش‌ترین محصولات ۳۰ روز اخیر (بر اساس درآمد) برای خانه‌ی فروشنده."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (await session.execute(
        select(Content, func.count(Purchase.id), func.sum(Purchase.amount))
        .join(Purchase, Purchase.content_id == Content.id)
        .where(Purchase.bot_id == seller.bot_id, Purchase.refunded.is_(False), Purchase.amount > 0,
               Purchase.created_at >= since)
        .group_by(Content.id).order_by(func.sum(Purchase.amount).desc()).limit(limit))).all()
    return [{"id": c.id, "kind": c.kind, "title": c.title or c.file_name, "sales": n, "revenue": total,
             "has_thumb": c.kind != "text"} for c, n, total in rows]


# --- ویترین‌ها: مدیریت فروشنده ---
async def set_product_showcases(session: AsyncSession, seller: Seller, c: Content, wanted: list) -> None:
    wanted_ids = {int(x) for x in wanted if is_id(x)}
    own = set((await session.scalars(select(Showcase.id).where(
        Showcase.bot_id == seller.bot_id, Showcase.is_active.is_(True), Showcase.id.in_(wanted_ids or {0})))).all())
    current = {it.showcase_id: it for it in (await session.scalars(
        select(ShowcaseItem).where(ShowcaseItem.content_id == c.id))).all()}
    for sid, it in current.items():
        if sid not in own:
            await session.delete(it)
    for sid in own - set(current):
        session.add(ShowcaseItem(showcase_id=sid, content_id=c.id, member_free=True))


async def showcase_json(session: AsyncSession, sc: Showcase, seller: Seller) -> dict:
    items = len(await showcases.showcase_items(session, sc))
    return {"id": sc.id, "code": sc.code, "title": sc.title, "description": sc.description, "access": sc.access,
            "price": sc.price, "items": items, **await showcases.showcase_stats(session, sc),
            "private": sc.private, "archived": sc.archived,
            "expires_at": sc.expires_at.isoformat() + "Z" if sc.expires_at else None,
            "trial_days": sc.trial_days, "bundles": showcases.bundle_discounts(sc),
            "link": showcases.showcase_link(sc, seller.bot_username)}


def showcase_fields(body: dict, cap: int) -> dict | str:
    """اعتبارسنجی فرم ویترین؛ خروجی: فیلدها یا کد خطا."""
    out = {}
    if "title" in body:
        title = str(body["title"] or "").strip()
        if not title:
            return "sc_need_title"
        if len(title) > showcases.TITLE_MAX:
            return "title_too_long"
        out["title"] = title
    if "description" in body:
        desc = str(body["description"] or "").strip()
        if len(desc) > showcases.DESCRIPTION_MAX:
            return "description_too_long"
        out["description"] = desc or None
    if "access" in body:
        if body["access"] not in showcases.ACCESS_TYPES:
            return "bad_access"
        out["access"] = body["access"]
    if "price" in body:
        if not is_int(body["price"]):
            return "bad_price"
        out["price"] = body["price"]
    if "private" in body:
        out["private"] = body["private"] is True
    if "expires_at" in body:
        exp = showcases.parse_expiry(body["expires_at"])
        if exp == "bad_expiry":
            return "bad_expiry"
        out["expires_at"] = exp
    if "archived" in body:
        out["archived"] = body["archived"] is True
    if "trial_days" in body:   # دوره‌ی آزمایشی رایگان (فقط اشتراک ماهانه از آن استفاده می‌کند)
        if not is_int(body["trial_days"]) or body["trial_days"] not in showcases.TRIAL_DAYS:
            return "bad_trial"
        out["trial_days"] = body["trial_days"]
    if "bundles" in body:      # {"3": تخفیف٪, "6": ..., "12": ...}
        bundles = showcases.clean_bundles(body["bundles"])
        if bundles is False:
            return "bad_bundles"
        out["bundles"] = bundles
    return out


async def api_showcases(request: web.Request) -> web.Response:
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await active_seller(session, user)
        if seller is None:
            return error("no_shop", 403)
        rows = (await session.scalars(select(Showcase).where(
            Showcase.bot_id == seller.bot_id, Showcase.is_active.is_(True))
            .order_by(Showcase.archived, Showcase.id))).all()
        main_items = await session.scalar(select(func.count(Content.id)).where(
            Content.bot_id == seller.bot_id, Content.is_active.is_(True), Content.is_draft.is_(False),
            Content.in_store.is_(True)))
        items = [await showcase_json(session, sc, seller) for sc in rows]
    return web.json_response({"main": {"items": main_items, "link": f"https://ble.ir/{seller.bot_username}?start=store"},
                              "items": items, "max": showcases.MAX_SHOWCASES})


async def api_showcase_create(request: web.Request) -> web.Response:
    body = await json_object(request)
    if body is None:
        return error("bad_request")
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await active_seller(session, user)
        if seller is None:
            return error("no_shop", 403)
        count = await session.scalar(select(func.count(Showcase.id)).where(
            Showcase.bot_id == seller.bot_id, Showcase.is_active.is_(True)))
        if count >= showcases.MAX_SHOWCASES:
            return error("sc_limit")
        fields = showcase_fields({"title": "", "access": "free", "price": 0, **body}, 0)
        if isinstance(fields, str):
            return error(fields)
        bad = await check_showcase_price(session, seller, fields)
        if bad:
            return error(bad)
        sc = Showcase(code=await showcases.new_code(session), bot_id=seller.bot_id, owner_id=user.id, **fields)
        session.add(sc)
        await session.flush()
        if isinstance(body.get("items"), list):
            await set_showcase_items(session, seller, sc, body["items"])
        await session.commit()
        return web.json_response(await showcase_detail(session, sc, seller, user))


async def check_showcase_price(session: AsyncSession, seller: Seller, fields: dict) -> str | None:
    if fields.get("access", "free") == "free":
        fields["price"] = 0
        return None
    price = fields.get("price", 0)
    if not MIN_PRICE <= price <= MAX_PRICE:
        return "bad_price"
    if price > await price_cap(session, seller.bot_id):   # همان سقف تدریجی محصولات
        return "price_cap"
    return None


async def set_showcase_items(session: AsyncSession, seller: Seller, sc: Showcase, items: list) -> None:
    """فهرست کامل محتواهای ویترین: [{id, member_free}]؛ فقط محصولات همین فروشگاه."""
    wanted = {int(x["id"]): bool(x.get("member_free", True)) for x in items
              if isinstance(x, dict) and is_id(x.get("id", ""))}
    valid = set((await session.scalars(select(Content.id).where(
        Content.bot_id == seller.bot_id, Content.id.in_(set(wanted) or {0})))).all())
    current = {it.content_id: it for it in (await session.scalars(
        select(ShowcaseItem).where(ShowcaseItem.showcase_id == sc.id))).all()}
    for cid, it in current.items():
        if cid not in valid:
            await session.delete(it)
        else:
            it.member_free = wanted[cid]
    for cid in valid - set(current):
        session.add(ShowcaseItem(showcase_id=sc.id, content_id=cid, member_free=wanted[cid]))


async def showcase_detail(session: AsyncSession, sc: Showcase, seller: Seller, user: User) -> dict:
    """ویترین برای صفحه‌ی ویرایش: همه‌ی محصولات فعال فروشگاه، با تیک «در این ویترین»."""
    inside = {it.content_id: it.member_free for it in (await session.scalars(
        select(ShowcaseItem).where(ShowcaseItem.showcase_id == sc.id))).all()}
    products = (await session.scalars(select(Content).where(
        Content.bot_id == seller.bot_id, Content.owner_id == user.id, Content.is_active.is_(True),
        Content.is_draft.is_(False)).order_by(Content.id.desc()).limit(300))).all()
    return {**await showcase_json(session, sc, seller),
            "products": [{"id": c.id, "kind": c.kind, "title": c.title or c.file_name, "price": c.price_stars,
                          "has_thumb": c.kind != "text", "included": c.id in inside,
                          "member_free": inside.get(c.id, True)} for c in products]}


async def api_showcase(request: web.Request) -> web.Response:
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await active_seller(session, user)
        sc = await showcases.shop_showcase(session, seller, request.match_info["id"]) if seller else None
        if sc is None:
            return error("not_found", 404)
        return web.json_response(await showcase_detail(session, sc, seller, user))


async def api_showcase_update(request: web.Request) -> web.Response:
    body = await json_object(request)
    if body is None:
        return error("bad_request")
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await active_seller(session, user)
        sc = await showcases.shop_showcase(session, seller, request.match_info["id"]) if seller else None
        if sc is None:
            return error("not_found", 404)
        fields = showcase_fields(body, 0)
        if isinstance(fields, str):
            return error(fields)
        merged = {"access": sc.access, "price": sc.price, **fields}
        bad = await check_showcase_price(session, seller, merged)
        if bad:
            return error(bad)
        if fields.get("archived") is False and sc.expires_at and sc.expires_at <= showcases.utcnow() \
                and "expires_at" not in fields:
            fields["expires_at"] = None   # فعال کردن دوباره: فقط تاریخ پایانِ گذشته پاک می‌شود
        archiving = fields.get("archived") and not sc.archived
        for k, v in {**fields, "access": merged["access"], "price": merged["price"]}.items():
            setattr(sc, k, v)
        if archiving:
            await showcases.stop_renewals(request.app["manager"], session, sc)
        if isinstance(body.get("items"), list):
            await set_showcase_items(session, seller, sc, body["items"])
        await session.commit()
        return web.json_response(await showcase_detail(session, sc, seller, user))


async def api_showcase_delete(request: web.Request) -> web.Response:
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await active_seller(session, user)
        sc = await showcases.shop_showcase(session, seller, request.match_info["id"]) if seller else None
        if sc is None:
            return error("not_found", 404)
        if await showcases.member_count(session, sc.id):   # کسی که پول ورودی داده نباید دسترسی‌اش را از دست بدهد
            return error("sc_has_members")
        sc.is_active = False
        await showcases.stop_renewals(request.app["manager"], session, sc)  # اشتراک تمام‌شده دوباره شارژ نشود
        await session.commit()
    return web.json_response({"ok": True})


# --- صفحه‌ی ویترین برای خریدار ---
async def buyer_showcase(session: AsyncSession, request: web.Request):
    sc = await showcases.by_code(session, request.match_info["code"])
    guest_of = guest_of_seller_bot(request)
    if sc is not None and guest_of is not None and sc.bot_id != guest_of:
        sc = None  # امضای ربات دیگری: این ویترین برایش وجود ندارد
    seller = await store_seller(session, str(sc.bot_id)) if sc else None
    if sc is None or seller is None:
        return None, None, None
    return sc, seller, await get_user(session, request)


async def api_sc_page(request: web.Request) -> web.Response:
    async with SessionLocal() as session:
        sc, seller, user = await buyer_showcase(session, request)
        if sc is None:
            return error("not_found", 404)
        rows = await showcases.showcase_items(session, sc)
        stats = await sales_by_content(session, [c.id for c, _ in rows])
        bought = {cid: opened is not None for cid, opened in (await session.execute(
            select(Purchase.content_id, Purchase.opened_at).where(
                Purchase.buyer_id == user.id, Purchase.bot_id == seller.bot_id, Purchase.refunded.is_(False)))).all()}
        m = await showcases.active_membership(session, sc.id, user.id)
        is_owner = sc.owner_id == user.id
        member = bool(m) or is_owner
        if sc.archived and not member:
            return error("sc_ended", 410)
        locked_page = sc.access != "free" and not member
        owner = await session.get(User, seller.owner_id)
        # ویترین خصوصی جدا از بقیه است: نه خودش در فهرست بقیه می‌آید، نه بقیه را نشان می‌دهد
        others = [] if sc.private else (await session.scalars(select(Showcase).where(
            Showcase.bot_id == seller.bot_id, Showcase.is_active.is_(True), Showcase.id != sc.id,
            Showcase.private.is_(False), Showcase.archived.is_(False)))).all()
        items = []
        for c, it in rows:
            item = store_item(c, stats.get(c.id), c.id in bought or is_owner, bought.get(c.id, is_owner))
            free_for_member = sc.access != "free" and it.member_free
            item.update({"member_free": free_for_member, "locked": locked_page,
                         "unlocked": member and free_for_member})
            items.append(item)
        await add_ratings(session, items, user.id)
        rating = await shop_rating(session, seller.bot_id)
        trial_used = bool(await session.scalar(select(showcases.Membership.id).where(
            showcases.Membership.showcase_id == sc.id, showcases.Membership.user_id == user.id).limit(1)))
        data = {
            "showcase": {"code": sc.code, "title": sc.title, "description": sc.description, "access": sc.access,
                         "price": sc.price, "members": await showcases.member_count(session, sc.id),
                         "archived": sc.archived,
                         "is_member": bool(m), "is_owner": is_owner,
                         "expires_at": m.expires_at.isoformat() if m and m.expires_at else None,
                         "can_refund": bool(settings.refunds and m and m.opened_at is None and m.amount and not m.expires_at),
                         "is_subscription": bool(m and m.sub_charge_id), "renewal_canceled": bool(m and m.canceled),
                         "is_trial": showcases.is_trial(m), "trial_days": sc.trial_days if sc.access == "monthly" else 0,
                         "trial_available": sc.access == "monthly" and bool(sc.trial_days) and not trial_used
                         and not is_owner and not sc.archived,
                         "bundles": showcases.bundle_options(sc),
                         "link": showcases.showcase_link(sc, seller.bot_username), "id": sc.id if is_owner else None},
            "look": looks.look_json(seller, sc),
            "shop": {"bot": seller.bot_username, "bot_id": seller.bot_id, "owner_name": owner.first_name if owner else "",
                     "suspended": seller.is_suspended, "is_owner": is_owner,
                     "sales": sum(x["sales"] for x in stats.values()), "rating": rating, **creator_shop(seller)},
            "items": items,
            "others": [{"code": o.code, "title": o.title, "access": o.access, "price": o.price} for o in others],
            "main_bot": request.app["main_username"],
        }
    return web.json_response(data)


async def api_sc_join(request: web.Request) -> web.Response:
    async with SessionLocal() as session:
        sc, seller, user = await buyer_showcase(session, request)
        if sc is None:
            return error("not_found", 404)
        months = (await json_object(request) or {}).get("months")
        if months is not None and (not is_int(months) or showcases.bundle_price(sc, months) is None):
            return error("bad_bundles")
        active = await showcases.active_membership(session, sc.id, user.id)
        if sc.access == "free" or sc.owner_id == user.id:
            return web.json_response({"member": True})
        if active and not showcases.is_trial(active) and not (months and not active.sub_charge_id):
            return web.json_response({"member": True})
        if months and active and active.sub_charge_id and not active.canceled:
            return error("sc_has_subscription")
        if sc.archived:
            return error("sc_ended", 410)
        if seller.is_suspended:
            return error("suspended", 403)
        bot = request.app["manager"].get(seller.bot_id)
        if bot is None:
            return error("shop_offline", 503)
        if not rate_ok(f"inv:{user.id}", 30, 600):
            return error("slow_down", 429)
        link = await bot.create_invoice_link(**showcases.invoice_args(sc, user.language, months))
    return web.json_response({"invoice": link})


async def api_sc_open(request: web.Request) -> web.Response:
    """محتوای «رایگان برای اعضا»: در چت ربات فروشنده (محافظت‌شده) تحویل می‌شود."""
    async with SessionLocal() as session:
        sc, seller, user = await buyer_showcase(session, request)
        cid = request.match_info["id"]
        if sc is None or not is_id(cid):
            return error("not_found", 404)
        row = next(((c, it) for c, it in await showcases.showcase_items(session, sc) if c.id == int(cid)), None)
        if row is None:
            return error("not_found", 404)
        c, it = row
        bot = request.app["manager"].get(seller.bot_id)
        if bot is None:
            return error("shop_offline", 503)
        if sc.owner_id == user.id:
            await deliver(bot, user.id, c, session, user.language)
            return web.json_response({"chat": f"https://ble.ir/{seller.bot_username}"})
        m = await showcases.active_membership(session, sc.id, user.id)
        if m is None:
            return error("sc_not_member", 403)
        if not it.member_free or c.is_physical:
            return error("sc_paid_item", 409)   # قیمت جدا دارد (یا کالای فیزیکی است)؛ از مسیر خرید عادی
        purchase = await showcases.unlock_item(session, m, c, user.id)
        if purchase is None:
            return error("sc_not_member", 403)
        await open_purchase(bot, user.id, purchase, c, session, user.language)
    return web.json_response({"chat": f"https://ble.ir/{seller.bot_username}"})


async def api_sc_renewal(request: web.Request) -> web.Response:
    """عضو اشتراک ماهانه تمدید خودکار را خاموش/روشن می‌کند."""
    try:
        cancel = bool((await json_object(request) or {})["cancel"])
    except (ValueError, KeyError, TypeError):
        return error("bad_request")
    async with SessionLocal() as session:
        sc, seller, user = await buyer_showcase(session, request)
        if sc is None:
            return error("not_found", 404)
        m = await showcases.active_membership(session, sc.id, user.id)
        if m is None:
            return error("sc_not_member", 403)
        bot = request.app["manager"].get(seller.bot_id)
        if bot is None:
            return error("shop_offline", 503)
        reason = await showcases.set_renewal(bot, session, m, cancel)
    if reason:
        return error(reason)
    return web.json_response({"renewal_canceled": cancel})


async def api_sc_refund(request: web.Request) -> web.Response:
    async with SessionLocal() as session:
        sc, seller, user = await buyer_showcase(session, request)
        if sc is None:
            return error("not_found", 404)
        m = await showcases.active_membership(session, sc.id, user.id)
        if m is None:
            return error("sc_not_member", 403)
        bot = request.app["manager"].get(seller.bot_id)
        if bot is None:
            return error("shop_offline", 503)
        reason = await showcases.refund_membership(bot, session, m)
    if reason:
        return error(reason)
    return web.json_response({"refunded": m.amount})


# --- ظاهر ویترین: تم، بنر، لوگو ---
async def api_image_upload(request: web.Request) -> web.Response:
    """عکس لوگو/بنر؛ بدنه = خود فایل. بیشتر از سقف خوانده نمی‌شود و حتماً دوباره ساخته می‌شود."""
    kind = request.query.get("kind", "")
    if kind not in looks.SIZES:
        return error("bad_request")
    raw = bytearray()  # جدا از سقف ۶۴ کیلوبایتی درخواست‌های JSON؛ بیشتر از سقف عکس خوانده نمی‌شود
    while len(raw) <= looks.IMAGE_MAX_BYTES:
        chunk = await request.content.read(64 * 1024)
        if not chunk:
            break
        raw += chunk
    raw = bytes(raw)
    async with SessionLocal() as session:
        user = await get_user(session, request)
        if await active_seller(session, user) is None:
            return error("no_shop", 403)
        if len(raw) > looks.IMAGE_MAX_BYTES:
            return error("image_too_big", 413)
        if not await looks.upload_allowed(session, user.id):
            return error("too_many_uploads", 429)
        data = await asyncio.to_thread(looks.process_image, raw, kind)
        if data is None:
            return error("bad_image")
        image_id = await looks.save_image(session, user.id, data)
        await session.commit()
    return web.json_response({"id": image_id})


async def api_image(request: web.Request) -> web.Response:
    async with SessionLocal() as session:
        image = await session.get(StoredImage, request.match_info["id"])
    if image is None:
        return error("not_found", 404)
    return web.Response(body=image.data, content_type="image/jpeg",
                        headers={"Cache-Control": "private, max-age=604800, immutable"})


async def api_look_update(request: web.Request) -> web.Response:
    """{"sc": شناسه‌ی ویترین یا null برای ویترین اصلی, "theme", "cover", "logo"} — هر کدام اختیاری؛ null = حذف عکس."""
    body = await json_object(request)
    if body is None:
        return error("bad_request")
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await active_seller(session, user)
        if seller is None:
            return error("no_shop", 403)
        sc = None
        if body.get("sc") is not None:
            sc = await showcases.shop_showcase(session, seller, str(body["sc"]))
            if sc is None:
                return error("not_found", 404)
        holder = sc if sc is not None else seller
        old = []
        if "style" in body:
            style = looks.merge_style(holder, body["style"])
            if isinstance(style, str):
                return error(style)
            if style["pinned"] is not None and not await pinnable(session, seller, sc, style["pinned"]):
                return error("bad_pinned")
            holder.style = json.dumps(style)
        if "links" in body:  # لینک‌های شبکه‌ها مال کل فروشگاه است (مثل لوگو)
            links = looks.clean_links(body["links"])
            if isinstance(links, str):
                return error(links)
            seller.links = json.dumps(links)
        if "theme" in body:
            if body["theme"] not in looks.THEMES:
                return error("bad_theme")
            holder.theme = body["theme"]
        for field, target in (("cover", holder), ("logo", seller), ("background", holder)):
            if field not in body:
                continue
            value = body[field]
            if value is not None and await looks.owned_image(session, user.id, value) is None:
                return error("bad_image")
            old.append(getattr(target, field))
            setattr(target, field, value)
        await session.flush()
        for image_id in old:
            if image_id not in (seller.logo, seller.cover, seller.background, sc.cover if sc else None,
                                sc.background if sc else None):
                await looks.drop_if_unused(session, image_id)
        await session.commit()
        look = looks.look_json(seller, sc)
    return web.json_response(look)


_stories: dict[str, tuple[float, bytes]] = {}
STORY_TTL, STORY_MAX = 30 * 60, 200  # کارت استوری فقط ۳۰ دقیقه برای دانلود تلگرام نگه داشته می‌شود


async def api_story_upload(request: web.Request) -> web.Response:
    """کارت استوری ساخته‌شده در گوشی → آدرس عمومی موقت (تلگرام برای ذخیره/استوری آدرس می‌خواهد)."""
    raw = bytearray()
    while len(raw) <= looks.IMAGE_MAX_BYTES:
        chunk = await request.content.read(64 * 1024)
        if not chunk:
            break
        raw += chunk
    async with SessionLocal() as session:
        user = await get_user(session, request)
        if await active_seller(session, user) is None:
            return error("no_shop", 403)
    data = await asyncio.to_thread(looks.process_story, bytes(raw))
    if data is None:
        return error("bad_image")
    now = time.time()
    for key in [k for k, (at, _) in _stories.items() if now - at > STORY_TTL]:
        _stories.pop(key, None)
    while len(_stories) >= STORY_MAX:
        _stories.pop(next(iter(_stories)))
    token = secrets.token_urlsafe(18)
    _stories[token] = (now, data)
    return web.json_response({"url": f"/story/{token}.jpg"})


async def story_file(request: web.Request) -> web.Response:
    item = _stories.get(request.match_info["token"])
    if item is None or time.time() - item[0] > STORY_TTL:
        raise web.HTTPNotFound()
    return web.Response(body=item[1], content_type="image/jpeg", headers={
        "Content-Disposition": 'attachment; filename="uploadfly-story.jpg"', "Cache-Control": "no-store"})


async def pinnable(session: AsyncSession, seller: Seller, sc: Showcase | None, content_id: int) -> bool:
    """پست سنجاق‌شده باید محصول فعال همین ویترین باشد."""
    if not is_id(content_id):
        return False
    c = await session.get(Content, content_id)
    if c is None or c.bot_id != seller.bot_id or not c.is_active or c.is_draft:
        return False
    if sc is None:
        return c.in_store
    return bool(await session.scalar(select(ShowcaseItem.id).where(
        ShowcaseItem.showcase_id == sc.id, ShowcaseItem.content_id == c.id)))


async def api_qr(request: web.Request) -> web.Response:
    text = request.query.get("text", "")
    if not text.startswith("https://ble.ir/") or len(text) > 256:
        return error("bad_request")
    return web.json_response({"rows": looks.qr_matrix(text)})


# --- لینک‌های رایگان (ربات اصلی) ---
def link_json(c: Content, main_username: str) -> dict:
    return {"id": c.id, "kind": c.kind, "title": c.file_name, "views": c.views, "size": c.file_size,
            "duration": c.duration, "created": c.created_at.isoformat() if c.created_at else None,
            "link": f"https://ble.ir/{main_username}?start={c.code}", "has_thumb": c.kind != "text",
            "text": preview.plain_text(c)[:80] if c.kind == "text" else None}


async def own_free_link(session: AsyncSession, request: web.Request) -> Content | None:
    """فقط لینک رایگانِ خود همین کاربر در ربات اصلی."""
    user = await get_user(session, request)
    cid = request.match_info["id"]
    c = await session.get(Content, int(cid)) if is_id(cid) else None
    main_id = request.app["manager"].main_bot.id
    return c if c and c.owner_id == user.id and c.bot_id == main_id and c.is_active else None


async def api_links(request: web.Request) -> web.Response:
    main_id = request.app["manager"].main_bot.id
    async with SessionLocal() as session:
        user = await get_user(session, request)
        rows = (await session.scalars(select(Content).where(
            Content.owner_id == user.id, Content.bot_id == main_id, Content.is_active.is_(True))
            .order_by(Content.id.desc()).limit(200))).all()
    return web.json_response({"items": [link_json(c, request.app["main_username"]) for c in rows]})


async def api_link_thumb(request: web.Request) -> web.StreamResponse:
    async with SessionLocal() as session:
        c = await own_free_link(session, request)
    if c is None:
        return error("not_found", 404)
    return await thumb_response(request.app["manager"].main_bot, c)


async def api_link_disable(request: web.Request) -> web.Response:
    """خاموش کردن لینک رایگان: لینک دیگر کار نمی‌کند (مثل /mylinks، از لیست هم حذف می‌شود)."""
    async with SessionLocal() as session:
        c = await own_free_link(session, request)
        if c is None:
            return error("not_found", 404)
        c.is_active = False
        await session.commit()
    return web.json_response({"ok": True})


async def api_wallet(request: web.Request) -> web.Response:
    manager: BotManager = request.app["manager"]
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await active_seller(session, user)
        if seller is None:
            return error("no_shop", 404)
        from app.creator import earnings
        return web.json_response({**await wallet_view(session, seller, manager),
                                  "earnings": await earnings(session, seller.bot_id)})


async def api_wallet_premium(request: web.Request) -> web.Response:
    try:
        months = int((await json_object(request) or {}).get("months"))
    except (ValueError, TypeError, AttributeError):
        return error("bad_months")
    manager: BotManager = request.app["manager"]
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await active_seller(session, user)  # فقط صاحب فروشگاه، برای خودش
        if seller is None:
            return error("no_shop", 404)
        code = await buy_premium(manager, seller, months, T(user.language)["premium_gift_text"])
        if code:
            return error(code)
        return web.json_response(await wallet_view(session, seller, manager))


async def api_purchases(request: web.Request) -> web.Response:
    """خریدهای خود کاربر از همه‌ی فروشگاه‌ها (بازپرداخت‌شده‌ها نه)."""
    async with SessionLocal() as session:
        user = await get_user(session, request)
        rows = (await session.execute(
            select(Purchase, Content, Seller).join(Content, Content.id == Purchase.content_id)
            .join(Seller, Seller.bot_id == Purchase.bot_id)
            .where(Purchase.buyer_id == user.id, Purchase.refunded.is_(False))
            .order_by(Purchase.id.desc()).limit(100))).all()
        # عضویت‌های ویترین (آخرین دوره‌ی هر ویترین)
        memberships = {}
        for m, sc, s in (await session.execute(
                select(showcases.Membership, Showcase, Seller).join(Showcase, Showcase.id == showcases.Membership.showcase_id)
                .join(Seller, Seller.bot_id == showcases.Membership.bot_id)
                .where(showcases.Membership.user_id == user.id, showcases.Membership.refunded.is_(False),
                       Showcase.is_active.is_(True))
                .order_by(showcases.Membership.id))).all():
            memberships[sc.id] = (m, sc, s)
    now = showcases.utcnow()
    return web.json_response({
        "memberships": [{
            "title": sc.title, "access": sc.access, "amount": m.amount, "shop": s.bot_username,
            "expires_at": m.expires_at.isoformat() + "Z" if m.expires_at else None,
            "active": m.expires_at is None or m.expires_at > now, "canceled": m.canceled,
            "link": showcases.showcase_link(sc, s.bot_username),
        } for m, sc, s in reversed(list(memberships.values()))],
        "items": [{
            "id": p.id, "content_id": c.id, "kind": c.kind, "title": c.title or c.file_name, "amount": p.amount,
            "shop": s.bot_username, "shop_bot_id": s.bot_id, "opened": p.opened_at is not None,
            "date": p.created_at.date().isoformat() if p.created_at else None,
            "link": f"https://ble.ir/{s.bot_username}?start={c.code}",
        } for p, c, s in rows]})


async def api_shop_disconnect(request: web.Request) -> web.Response:
    manager: BotManager = request.app["manager"]
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await active_seller(session, user)
        if seller is None:
            return error("no_shop", 404)
        seller.is_active = False
        await session.commit()
        await manager.stop(seller.bot_id)
    return web.json_response({"ok": True})


# --- ویترین فروشگاه (برای همه‌ی کاربران تلگرام) ---

def creator_shop(seller: Seller) -> dict:
    """اطلاعات صفحه‌ی سازنده برای خریدار: معرفی، دونیت، پیام خصوصی."""
    from app.creator import TIP_MAX, TIP_PRESETS
    return {"bio": seller.bio, "category": seller.category, "dm_mode": seller.dm_mode,
            "tips": list(TIP_PRESETS), "tip_max": TIP_MAX,
            "chat": f"https://ble.ir/{seller.bot_username}"}


async def store_seller(session: AsyncSession, bot_id: str) -> Seller | None:
    if not is_id(bot_id, big=True):
        return None
    return await session.scalar(select(Seller).where(Seller.bot_id == int(bot_id), Seller.is_active.is_(True)))


def store_item(c: Content, stats: dict | None, bought: bool, opened: bool = False) -> dict:
    p = preview.stored(c)
    return {
        "id": c.id, "code": c.code, "kind": c.kind, "title": c.title or c.file_name, "description": c.description,
        "category": c.category, "price": c.price_stars, "size": c.file_size, "duration": c.duration,
        "width": c.width, "height": c.height, "pages": p.get("pages"), "sensitive": c.is_sensitive,
        "allow_save": c.allow_save and not c.is_sensitive, "sales": (stats or {}).get("sales", 0),
        "images": len(p.get("photos") or []) or (1 if c.thumb_file_id or (c.kind == "photo" and (not c.price_stars or c.is_physical)) else 0),
        "audio": bool(p.get("voice")), "snippet": p.get("text") or (preview.text_snippet(c) if c.kind == "text" else None),
        # کالای فیزیکی هر بار دوباره سفارش داده می‌شود و چیزی برای «نمایش» ندارد
        "bought": bought and not c.is_physical, "opened": opened and not c.is_physical,
        "physical": c.is_physical, "in_stock": c.stock is None or c.stock > 0,
        "created": c.created_at.isoformat() if c.created_at else None,
    }


async def api_store(request: web.Request) -> web.Response:
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await store_seller(session, request.match_info["bot"])
        if seller is None:
            return error("not_found", 404)
        rows = (await session.scalars(select(Content).where(
            Content.bot_id == seller.bot_id, Content.is_draft.is_(False), Content.is_active.is_(True),
            Content.in_store.is_(True))
            .order_by(Content.id.desc()).limit(300))).all()
        stats = await sales_by_content(session, [c.id for c in rows])
        bought = {cid: opened is not None for cid, opened in (await session.execute(
            select(Purchase.content_id, Purchase.opened_at).where(
                Purchase.buyer_id == user.id, Purchase.bot_id == seller.bot_id, Purchase.refunded.is_(False)))).all()}
        owner = await session.get(User, seller.owner_id)
        others = (await session.scalars(select(Showcase).where(
            Showcase.bot_id == seller.bot_id, Showcase.is_active.is_(True), Showcase.private.is_(False),
            Showcase.archived.is_(False)).order_by(Showcase.id))).all()
        items = [store_item(c, stats.get(c.id), c.id in bought or c.owner_id == user.id,
                            bought.get(c.id, c.owner_id == user.id)) for c in rows]
        await add_ratings(session, items, user.id)
        rating = await shop_rating(session, seller.bot_id)
    return web.json_response({
        "others": [{"code": o.code, "title": o.title, "access": o.access, "price": o.price} for o in others],
        "look": looks.look_json(seller),
        "link": f"https://ble.ir/{seller.bot_username}?start=store",
        "main_bot": request.app["main_username"],
        "shop": {"bot": seller.bot_username, "bot_id": seller.bot_id, "owner_name": owner.first_name if owner else "",
                 "suspended": seller.is_suspended, "is_owner": seller.owner_id == user.id,
                 "sales": sum(x["sales"] for x in stats.values()), "rating": rating, **creator_shop(seller)},
        "items": items,
    })


async def add_ratings(session: AsyncSession, items: list[dict], user_id: int) -> None:
    """میانگین امتیاز هر محصول + امتیازی که خود این کاربر داده (برای ستاره‌های برگه‌ی خرید)."""
    ids = [i["id"] for i in items]
    ratings = await ratings_by_content(session, ids)
    mine = dict((await session.execute(select(Review.content_id, Review.stars).where(
        Review.buyer_id == user_id, Review.content_id.in_(ids or [0])))).all())
    from app.web_creator import likes_for
    likes, liked = await likes_for(session, ids, user_id)
    for i in items:
        i["rating"], i["my_rating"] = ratings.get(i["id"]), mine.get(i["id"], 0)
        i["likes"], i["liked"] = likes.get(i["id"], 0), i["id"] in liked


async def store_content(request: web.Request) -> tuple[Seller, Content] | None:
    async with SessionLocal() as session:
        seller = await store_seller(session, request.match_info["bot"])
        cid = request.match_info["id"]
        if seller is None or not is_id(cid):
            return None
        c = await session.get(Content, int(cid))
    if c is None or c.bot_id != seller.bot_id or c.is_draft or not c.is_active:
        return None
    return seller, c


async def api_store_image(request: web.Request) -> web.Response:
    """تصاویر پیش‌نمایش برای ویترین. هیچ‌وقت خود فایل پولی نشان داده نمی‌شود؛ فقط پیش‌نمایش تار سیستم."""
    found = await store_content(request)
    n = request.match_info["n"]
    if found is None or not is_id(n):
        return error("not_found", 404)
    seller, c = found
    photos = preview.stored(c).get("photos") or []
    if c.is_physical and c.kind == "photo":
        source, blur = c.file_id, False   # عکس کالا باید واضح دیده شود؛ خودِ «محتوا» نیست
    elif photos:
        source, blur = photos[min(int(n), len(photos) - 1)], False   # از قبل تار است
    elif c.thumb_file_id:  # هر تصویری غیر از پیش‌نمایش سیستم تار می‌شود؛ هیچ محتوایی از ربات بیرون نمی‌رود
        source, blur = c.thumb_file_id, True
    elif c.kind == "photo" and not c.price_stars:
        source, blur = c.file_id, True
    else:
        return error("no_image", 404)
    return await cached_image(request, c, source, blur)


async def cached_image(request: web.Request, c: Content, source: str, blur: bool) -> web.Response:
    bot = request.app["manager"].get(c.bot_id)
    if bot is None:
        return error("no_image", 404)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    path = THUMB_DIR / f"s{c.id}-{hashlib.sha1(source.encode()).hexdigest()[:10]}{'-b' if blur else ''}.jpg"
    if not path.exists():
        try:
            raw = (await bot.download(source)).read()
        except Exception:
            return error("no_image", 404)
        path.write_bytes(await asyncio.to_thread(make_thumb, raw, blur, 720))
    return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})


async def api_store_audio(request: web.Request) -> web.Response:
    """۱۵ ثانیه پیش‌نمایش صوتی، تبدیل‌شده به m4a تا روی آیفون هم پخش شود."""
    found = await store_content(request)
    voice = preview.stored(found[1]).get("voice") if found else None
    bot = request.app["manager"].get(found[1].bot_id) if found else None
    if not voice or bot is None:
        return error("not_found", 404)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    path = THUMB_DIR / f"a{found[1].id}-{hashlib.sha1(voice.encode()).hexdigest()[:10]}.m4a"
    if not path.exists():
        src = THUMB_DIR / f"a{found[1].id}.ogg"
        try:
            await bot.download(voice, destination=src)
            await preview.run("ffmpeg", "-y", "-i", str(src), "-c:a", "aac", "-b:a", "64k", str(path))
        except Exception:
            log.warning("Audio preview failed for content %s", found[1].id)
            path.unlink(missing_ok=True)
            return error("no_audio", 404)
        finally:
            src.unlink(missing_ok=True)
    return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400", "Content-Type": "audio/mp4"})


async def api_store_invoice(request: web.Request) -> web.Response:
    """لینک فاکتور استارز از ربات خود فروشنده؛ پول مستقیم به موجودی همان ربات می‌رود."""
    found = await store_content(request)
    if found is None:
        return error("not_found", 404)
    seller, c = found
    bot = request.app["manager"].get(seller.bot_id)
    async with SessionLocal() as session:
        user = await get_user(session, request)
        bought = await session.scalar(select(Purchase.id).where(
            Purchase.content_id == c.id, Purchase.buyer_id == user.id, Purchase.refunded.is_(False)))
    if seller.is_suspended:
        return error("suspended", 403)
    if c.is_sensitive and c.owner_id != user.id and not user.adult_ok:
        return error("adult_confirm", 409)   # یک بار تأیید ۱۸+ (POST /api/store/<bot>/adult)
    if c.price_stars == 0 or bought or c.owner_id == user.id or c.is_physical:   # کالا: فرم نشانی در چت
        return web.json_response({"open": f"https://ble.ir/{seller.bot_username}?start={c.code}"})
    if bot is None:
        return error("shop_offline", 503)
    if not rate_ok(f"inv:{user.id}", 30, 600):  # هر کاربر ۳۰ فاکتور در ۱۰ دقیقه (سهمیه‌ی ربات فروشنده هدر نرود)
        return error("slow_down", 429)
    link = await bot.create_invoice_link(**invoice_args(c, user.language))
    return web.json_response({"invoice": link, "bot": seller.bot_username})


async def buyer_purchase(request: web.Request):
    """خرید همین کاربر از این محصول (بازپرداخت‌نشده)."""
    found = await store_content(request)
    if found is None:
        return None, None, None, None
    seller, c = found
    session = SessionLocal()
    try:
        user = await get_user(session, request)
    except BaseException:
        await session.close()  # کاربر مسدود (HTTPForbidden): اتصال برگردد
        raise
    purchase = await session.scalar(select(Purchase).where(
        Purchase.content_id == c.id, Purchase.buyer_id == user.id, Purchase.refunded.is_(False)))
    return session, user, seller, (c, purchase)


async def api_store_open(request: web.Request) -> web.Response:
    """«نمایش» از داخل Mini App بعد از خرید: محتوا در چت ربات فروشنده تحویل می‌شود (فقط آن‌جا محافظت‌شده است)."""
    session, user, seller, found = await buyer_purchase(request)
    if session is None:
        return error("not_found", 404)
    async with session:
        c, purchase = found
        bot = request.app["manager"].get(seller.bot_id)
        if purchase is None and c.owner_id != user.id and c.price_stars:
            return error("not_paid_yet", 409)  # پرداخت ثبت شده ولی هنوز به ربات نرسیده؛ Mini App دوباره تلاش می‌کند
        if bot is None:
            return error("shop_offline", 503)
        if purchase is not None:
            await open_purchase(bot, user.id, purchase, c, session, user.language)
        else:
            await deliver(bot, user.id, c, session, user.language)
    return web.json_response({"chat": f"https://ble.ir/{seller.bot_username}"})


async def api_store_rate(request: web.Request) -> web.Response:
    """امتیاز ۱ تا ۵ از داخل Mini App؛ فقط خریدار واقعی که محتوا را باز کرده."""
    try:
        stars = int((await json_object(request) or {})["stars"])
    except (ValueError, KeyError, TypeError):
        return error("bad_request")
    session, user, seller, found = await buyer_purchase(request)
    if session is None:
        return error("not_found", 404)
    async with session:
        c, purchase = found
        if purchase is None or not await rate(session, purchase, stars):
            return error("rate_not_allowed", 403)
        rating = (await ratings_by_content(session, [c.id])).get(c.id)
    return web.json_response({"my_rating": stars, "rating": rating})


async def api_store_refund(request: web.Request) -> web.Response:
    session, user, seller, found = await buyer_purchase(request)
    if session is None:
        return error("not_found", 404)
    async with session:
        c, purchase = found
        bot = request.app["manager"].get(seller.bot_id)
        if purchase is None:
            return error("not_paid_yet", 409)
        if bot is None:
            return error("shop_offline", 503)
        reason = await refund_purchase(bot, session, purchase, user, seller)
    if reason:
        return error(reason)
    return web.json_response({"refunded": purchase.amount})


# --- فایل‌های Mini App: فشرده (gzip) و با نسخه، تا از تونل/اینترنت کند سریع برسند و دوباره دانلود نشوند ---
COMPRESSIBLE = {".html": "text/html", ".css": "text/css", ".js": "application/javascript", ".svg": "image/svg+xml",
                ".json": "application/json"}
BINARY = {".woff2": "font/woff2", ".jpg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
_asset_cache: dict[Path, tuple[float, bytes]] = {}


# فقط فایل‌های خودمان و اسکریپت رسمی مینی‌اپ بله؛ اگر متنی از کاربر هم جایی بد نمایش داده شود، اسکریپتش اجرا نمی‌شود
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; font-src 'self'; "
       "object-src 'none'; base-uri 'none'; form-action 'none'; "
       "frame-src https://*.bale.ai; frame-ancestors 'self' https://*.bale.ai")  # بله‌ی وب مینی‌اپ را در iframe باز می‌کند


@web.middleware
async def security_headers(request: web.Request, handler):
    resp = await handler(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


_rates: dict[str, list[float]] = {}


def rate_ok(key: str, limit: int, window: float) -> bool:
    """سقف ساده در حافظه: حداکثر `limit` بار در `window` ثانیه برای هر کلید."""
    now = time.time()
    recent = [x for x in _rates.get(key, []) if now - x < window]
    if len(recent) >= limit:
        _rates[key] = recent
        return False
    if len(_rates) > 20000:
        _rates.clear()
    _rates[key] = recent + [now]
    return True


_client_errors: dict[int, list[float]] = {}
CLIENT_ERROR_LIMIT = 20  # در هر ۱۰ دقیقه برای هر کاربر؛ بیشتر از این نادیده گرفته می‌شود


async def api_client_error(request: web.Request) -> web.Response:
    """خطاهای جاوااسکریپت گوشی واقعی کاربر در لاگ؛ فقط متن کوتاه، بدون initData یا داده‌ی شخصی."""
    uid, now = request["tg_user"].id, time.time()
    recent = [x for x in _client_errors.get(uid, []) if now - x < 600]
    if len(recent) >= CLIENT_ERROR_LIMIT:
        return web.json_response({"ok": False})
    if len(_client_errors) > 5000:  # حافظه بی‌انتها رشد نکند
        _client_errors.clear()
    _client_errors[uid] = recent + [now]
    body = await json_object(request)
    if body is None:
        return error("bad_request")
    clean = lambda v, n: " ".join(str(v or "").split())[:n]  # noqa: E731  یک خط، کوتاه (جلوی جعل خط لاگ)
    log.warning("Mini App error user=%s page=%s: %s | %s", uid, clean(body.get("page"), 40),
                clean(body.get("message"), 300), clean(body.get("where"), 300))
    return web.json_response({"ok": True})


def asset_version(name: str) -> str:
    paths = [WEBAPP_DIR / name]
    if name == "app.js":  # ترجمه‌ها با نسخه‌ی app.js دانلود می‌شوند؛ تغییر ترجمه هم نسخه را عوض می‌کند
        paths += (WEBAPP_DIR / "i18n").glob("*.json")
    # لوگو بعد از اولین اجرا دانلود می‌شود و ممکن است هنوز نباشد؛ صفحه نباید به‌خاطرش خراب شود
    mtimes = [p.stat().st_mtime for p in paths if p.exists()]
    return str(int(max(mtimes))) if mtimes else "0"


def read_asset(path: Path) -> bytes:
    mtime = path.stat().st_mtime
    cached = _asset_cache.get(path)
    if cached is None or cached[0] != mtime:
        _asset_cache[path] = cached = (mtime, path.read_bytes())
    return cached[1]


async def index(request: web.Request) -> web.Response:
    html = read_asset(WEBAPP_DIR / "index.html").decode()
    for name in ("tokens.css", "app.css", "bale-sdk.js", "bale.js", "app.js", "creator.js", "logo.jpg"):  # نسخه در آدرس: فایل تغییرکرده حتماً دوباره دانلود می‌شود
        html = html.replace(f"/static/{name}", f"/static/{name}?v={asset_version(name)}")
    resp = web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-cache", "Content-Security-Policy": CSP})
    resp.enable_compression()
    return resp


async def static_file(request: web.Request) -> web.Response:
    rel = request.match_info["path"]
    path = (WEBAPP_DIR / rel).resolve()
    if WEBAPP_DIR not in path.parents or not path.is_file():  # جلوگیری از خواندن فایل بیرون از webapp/
        raise web.HTTPNotFound()
    ext = path.suffix.lower()
    if ext not in COMPRESSIBLE and ext not in BINARY:
        raise web.HTTPNotFound()
    # فایل نسخه‌دار یک سال کش؛ فونت‌ها هم تغییر نمی‌کنند
    cache = "public, max-age=31536000, immutable" if "v" in request.query or ext == ".woff2" else "public, max-age=3600"
    resp = web.Response(body=read_asset(path), content_type=COMPRESSIBLE.get(ext) or BINARY[ext],
                        headers={"Cache-Control": cache})
    if ext in COMPRESSIBLE:
        resp.enable_compression()
    return resp


def make_app(manager: BotManager, main_username: str) -> web.Application:
    app = web.Application(middlewares=[security_headers, auth_middleware], client_max_size=64 * 1024)
    app["manager"] = manager
    app["main_username"] = main_username
    app.router.add_get("/", index)
    app.router.add_get("/api/me", api_me)
    app.router.add_post("/api/client-error", api_client_error)
    app.router.add_post("/api/images", api_image_upload)
    app.router.add_get("/api/images/{id}", api_image)
    app.router.add_patch("/api/look", api_look_update)
    app.router.add_get("/api/qr", api_qr)
    app.router.add_post("/api/story", api_story_upload)
    app.router.add_get("/story/{token}.jpg", story_file)
    app.router.add_patch("/api/me", api_me_update)
    app.router.add_get("/api/purchases", api_purchases)
    app.router.add_get("/api/wallet", api_wallet)
    app.router.add_get("/api/links", api_links)
    app.router.add_get("/api/showcases", api_showcases)
    app.router.add_post("/api/showcases", api_showcase_create)
    app.router.add_get("/api/showcases/{id}", api_showcase)
    app.router.add_patch("/api/showcases/{id}", api_showcase_update)
    app.router.add_delete("/api/showcases/{id}", api_showcase_delete)
    app.router.add_get("/api/sc/{code}", api_sc_page)
    app.router.add_post("/api/sc/{code}/join", api_sc_join)
    app.router.add_post("/api/sc/{code}/open/{id}", api_sc_open)
    app.router.add_post("/api/sc/{code}/refund", api_sc_refund)
    app.router.add_post("/api/sc/{code}/renewal", api_sc_renewal)
    app.router.add_post("/api/store/{bot}/rate/{id}", api_store_rate)
    app.router.add_get("/api/links/{id}/thumb", api_link_thumb)
    app.router.add_post("/api/links/{id}/disable", api_link_disable)
    app.router.add_post("/api/wallet/premium", api_wallet_premium)
    app.router.add_post("/api/shop/disconnect", api_shop_disconnect)
    app.router.add_get("/api/products", api_products)
    app.router.add_get("/api/products/{id}", api_product)
    app.router.add_patch("/api/products/{id}", api_product_update)
    app.router.add_get("/api/products/{id}/thumb", api_thumb)
    app.router.add_get("/api/store/{bot}", api_store)
    app.router.add_get("/api/store/{bot}/img/{id}/{n}", api_store_image)
    app.router.add_get("/api/store/{bot}/audio/{id}", api_store_audio)
    app.router.add_post("/api/store/{bot}/invoice/{id}", api_store_invoice)
    app.router.add_post("/api/store/{bot}/open/{id}", api_store_open)
    app.router.add_post("/api/store/{bot}/refund/{id}", api_store_refund)
    app.router.add_get("/static/{path:.+}", static_file)
    from app import web_creator   # صفحه‌ی سازنده: تنظیمات، فن‌ها، کشف، دونیت، لایک، آزمایشی
    web_creator.add_routes(app)
    return app


async def start_web(manager: BotManager, main_username: str, port: int) -> web.AppRunner:
    runner = web.AppRunner(make_app(manager, main_username), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, settings.webapp_host, port).start()
    log.info("Mini App web server on http://%s:%s", settings.webapp_host, port)
    return runner
