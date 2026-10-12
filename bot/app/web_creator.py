"""API مینی‌اپ برای صفحه‌ی سازنده: تنظیمات سازنده، فهرست فن‌ها، صفحه‌ی کشف، دونیت، لایک، دوره‌ی آزمایشی،
خبر «پست تازه». همه از همان auth_middleware و قانون مهمانِ ربات فروشنده (allowed_for_guest) رد می‌شوند:
مسیرهای /api/store/<bot>/… و /api/sc/… برای مهمان باز است، بقیه فقط با امضای ربات اصلی یا صاحب همان ربات."""
import html

from aiohttp import web
from sqlalchemy import func, or_, select

from app import creator, looks, showcases
from app.connect import active_seller
from app.db import Content, Like, Membership, Seller, SessionLocal, User, is_id
from app.products import shop_rating
from app.texts import T
from app.web import error, get_user, guest_of_seller_bot, is_int, json_object, owned_content, rate_ok, store_content


# --- تنظیمات سازنده ---
async def creator_json(session, seller: Seller, user: User, main_username: str) -> dict:
    invited = await session.scalar(select(func.count(User.id)).where(User.referrer_id == user.id)) or 0
    invited_shops = await session.scalar(select(func.count(Seller.id)).join(User, User.id == Seller.owner_id).where(
        User.referrer_id == user.id, Seller.is_active.is_(True))) or 0
    view = await creator.fans_view(session, seller)
    return {"bio": seller.bio or "", "category": seller.category, "listed": seller.listed, "dm_mode": seller.dm_mode,
            "welcome": seller.welcome or "", "watermark": seller.watermark,
            "categories": creator.CREATOR_CATEGORIES, "dm_modes": creator.DM_MODES,
            "bio_max": creator.BIO_MAX, "welcome_max": creator.WELCOME_MAX,
            "followers": view["followers"], "counts": view["counts"],
            "earnings": await creator.earnings(session, seller.bot_id),
            "referral": {"link": f"https://ble.ir/{main_username}?start=ref_{user.id}", "invited": invited,
                         "shops": invited_shops},
            "broadcast_link": f"https://ble.ir/{seller.bot_username}?start=broadcast",
            "broadcasts_left": max(0, creator.BROADCASTS_PER_DAY - await creator.broadcasts_today(session, seller.bot_id))}


async def owner_seller(request: web.Request):
    session = SessionLocal()
    try:
        user = await get_user(session, request)
        seller = await active_seller(session, user)
    except BaseException:
        await session.close()
        raise
    return session, user, seller


async def api_creator(request: web.Request) -> web.Response:
    session, user, seller = await owner_seller(request)
    async with session:
        if seller is None:
            return error("no_shop", 403)
        return web.json_response(await creator_json(session, seller, user, request.app["main_username"]))


async def api_creator_update(request: web.Request) -> web.Response:
    body = await json_object(request)
    if body is None:
        return error("bad_request")
    session, user, seller = await owner_seller(request)
    async with session:
        if seller is None:
            return error("no_shop", 403)
        if "bio" in body:
            bio = str(body["bio"] or "").strip()
            if len(bio) > creator.BIO_MAX:
                return error("description_too_long")
            seller.bio = bio or None
        if "welcome" in body:
            welcome = str(body["welcome"] or "").strip()
            if len(welcome) > creator.WELCOME_MAX:
                return error("description_too_long")
            seller.welcome = welcome or None
        if "category" in body:
            if body["category"] is not None and body["category"] not in creator.CREATOR_CATEGORIES:
                return error("bad_category")
            seller.category = body["category"]
        if "dm_mode" in body:
            if body["dm_mode"] not in creator.DM_MODES:
                return error("bad_request")
            seller.dm_mode = body["dm_mode"]
        for key in ("listed", "watermark"):
            if key in body:
                setattr(seller, key, body[key] is True)
        await session.commit()
        return web.json_response(await creator_json(session, seller, user, request.app["main_username"]))


async def api_fans(request: web.Request) -> web.Response:
    session, user, seller = await owner_seller(request)
    async with session:
        if seller is None:
            return error("no_shop", 403)
        view = await creator.fans_view(session, seller)
    for f in view["fans"]:   # ناشناس: آیدی تلگرام فن به Mini App سازنده نمی‌رود
        f.pop("id", None)
    return web.json_response(view)


# --- صفحه‌ی کشف سازنده‌ها (فقط از ربات اصلی) ---
EXPLORE_LIMIT = 60


async def api_explore(request: web.Request) -> web.Response:
    q = request.query.get("q", "").strip()[:40]
    cat = request.query.get("cat")
    async with SessionLocal() as session:
        await get_user(session, request)
        posts = (select(Content.bot_id, func.count(Content.id).label("n")).where(
            Content.is_active.is_(True), Content.is_draft.is_(False), Content.in_store.is_(True))
            .group_by(Content.bot_id).subquery())
        # محتوای بزرگسالان هرگز در صفحه‌ی کشف نیست: فروشگاهی که حتی یک محتوای حساس فعال دارد، نشان داده نمی‌شود
        sensitive = select(Content.bot_id).where(Content.is_active.is_(True), Content.is_sensitive.is_(True))
        query = (select(Seller, User, posts.c.n).join(posts, posts.c.bot_id == Seller.bot_id)
                 .join(User, User.id == Seller.owner_id)
                 .where(Seller.is_active.is_(True), Seller.is_suspended.is_(False), Seller.listed.is_(True),
                        User.is_banned.is_(False), Seller.bot_id.not_in(sensitive)))
        if cat in creator.CREATOR_CATEGORIES:
            query = query.where(Seller.category == cat)
        if q:
            like = f"%{q.lower()}%"
            query = query.where(or_(func.lower(User.first_name).like(like), func.lower(Seller.bot_username).like(like),
                                    func.lower(Seller.bio).like(like)))
        rows = (await session.execute(query.order_by(posts.c.n.desc(), Seller.id).limit(EXPLORE_LIMIT))).all()
        now = showcases.utcnow()
        members = dict((await session.execute(select(Membership.bot_id, func.count(func.distinct(Membership.user_id)))
                                              .where(Membership.refunded.is_(False),
                                                     or_(Membership.expires_at.is_(None), Membership.expires_at > now),
                                                     Membership.bot_id.in_([s.bot_id for s, _, _ in rows] or [0]))
                                              .group_by(Membership.bot_id))).all())
        out = []
        for s, owner, n in rows:
            look = looks.look_json(s)
            out.append({"bot_id": s.bot_id, "bot": s.bot_username, "name": owner.first_name or s.bot_username,
                        "bio": s.bio, "category": s.category, "logo": look["logo"], "cover": look["cover"],
                        "theme": look["theme"], "posts": n, "members": members.get(s.bot_id, 0),
                        "rating": await shop_rating(session, s.bot_id)})
        out.sort(key=lambda x: (x["members"], x["posts"]), reverse=True)
    return web.json_response({"items": out, "categories": creator.CREATOR_CATEGORIES})


# --- خریدار: دونیت، لایک، دوره‌ی آزمایشی ---
async def api_store_tip(request: web.Request) -> web.Response:
    body = await json_object(request) or {}
    amount = body.get("amount")
    if not is_int(amount) or not creator.TIP_MIN <= amount <= creator.TIP_MAX:
        return error("bad_price")
    cid = body.get("content_id")
    async with SessionLocal() as session:
        user = await get_user(session, request)
        bot_id = request.match_info["bot"]
        seller = await session.scalar(select(Seller).where(Seller.bot_id == int(bot_id), Seller.is_active.is_(True))) \
            if is_id(bot_id, big=True) else None
        if seller is None:
            return error("not_found", 404)
        if seller.owner_id == user.id:
            return error("tip_self")
        if seller.is_suspended:
            return error("suspended", 403)
        if cid is not None:
            c = await session.get(Content, cid) if is_int(cid) and is_id(cid) else None
            if c is None or c.bot_id != seller.bot_id:
                return error("not_found", 404)
    bot = request.app["manager"].get(seller.bot_id)
    if bot is None:
        return error("shop_offline", 503)
    if not rate_ok(f"inv:{user.id}", 30, 600):
        return error("slow_down", 429)
    link = await bot.create_invoice_link(**creator.tip_invoice_args(amount, user.language, cid))
    return web.json_response({"invoice": link})


async def api_store_like(request: web.Request) -> web.Response:
    found = await store_content(request)
    if found is None:
        return error("not_found", 404)
    _, c = found
    async with SessionLocal() as session:
        user = await get_user(session, request)
        if not rate_ok(f"like:{user.id}", 120, 60):
            return error("slow_down", 429)
        row = await session.scalar(select(Like).where(Like.content_id == c.id, Like.user_id == user.id))
        if row is None:
            session.add(Like(content_id=c.id, user_id=user.id))
            liked = True
        else:
            await session.delete(row)
            liked = False
        await session.commit()
        likes = await session.scalar(select(func.count(Like.id)).where(Like.content_id == c.id)) or 0
    return web.json_response({"liked": liked, "likes": likes})


async def likes_for(session, content_ids: list[int], user_id: int) -> tuple[dict[int, int], set[int]]:
    if not content_ids:
        return {}, set()
    counts = dict((await session.execute(select(Like.content_id, func.count(Like.id)).where(
        Like.content_id.in_(content_ids)).group_by(Like.content_id))).all())
    mine = set((await session.scalars(select(Like.content_id).where(
        Like.content_id.in_(content_ids), Like.user_id == user_id))).all())
    return counts, mine


async def api_sc_trial(request: web.Request) -> web.Response:
    from app.web import buyer_showcase
    async with SessionLocal() as session:
        sc, seller, user = await buyer_showcase(session, request)
        if sc is None:
            return error("not_found", 404)
        if sc.owner_id == user.id:
            return web.json_response({"member": True})
        if seller.is_suspended:
            return error("suspended", 403)
        m = await showcases.start_trial(session, sc, user.id)
        if isinstance(m, str):
            return error(m)
        bot = request.app["manager"].get(seller.bot_id)
        if bot is not None:
            t = T(user.language)
            try:
                await bot.send_message(user.id, t["sc_trial_started"].format(
                    title=html.escape(sc.title), days=sc.trial_days), disable_notification=True)
                if seller.welcome:
                    await bot.send_message(user.id, html.escape(seller.welcome), disable_notification=True)
            except Exception:
                pass
    return web.json_response({"member": True, "expires_at": m.expires_at.isoformat() + "Z"})


async def api_store_dm(request: web.Request) -> web.Response:
    """دکمه‌ی «پیام» در صفحه: ربات سازنده در چت خود فن می‌نویسد «پیامت را همین‌جا بنویس» و Mini App بسته می‌شود.
    (باز کردن چت همان رباتی که Mini App از آن باز شده در تلگرام کاری نمی‌کند.)"""
    bot_id = request.match_info["bot"]
    async with SessionLocal() as session:
        user = await get_user(session, request)
        seller = await session.scalar(select(Seller).where(Seller.bot_id == int(bot_id), Seller.is_active.is_(True))) \
            if is_id(bot_id, big=True) else None
        if seller is None:
            return error("not_found", 404)
        if seller.owner_id == user.id:
            return error("dm_self")
        reason = await creator.dm_block_reason(session, seller, user.id)
        if reason:
            return error(reason, 403)
        owner = await session.get(User, seller.owner_id)
    bot = request.app["manager"].get(seller.bot_id)
    if bot is None:
        return error("shop_offline", 503)
    chat = f"https://ble.ir/{seller.bot_username}"
    name = html.escape((owner.first_name if owner else "") or f"@{seller.bot_username}")
    try:
        await bot.send_message(user.id, T(user.language)["dm_prompt"].format(name=name))
    except Exception:   # هنوز ربات را استارت نکرده؛ با باز شدن چت، خودش Start می‌زند
        return web.json_response({"chat": chat, "sent": False})
    return web.json_response({"chat": chat, "sent": True})


async def api_store_adult(request: web.Request) -> web.Response:
    """تأیید ۱۸+ خریدار (یک بار؛ برای خرید محتوای حساس)."""
    async with SessionLocal() as session:
        user = await get_user(session, request)
        user.adult_ok = True
        await session.commit()
    return web.json_response({"adult_ok": True})


# --- سازنده: خبر «پست تازه» ---
async def api_product_notify(request: web.Request) -> web.Response:
    async with SessionLocal() as session:
        user = await get_user(session, request)
        found = await owned_content(session, user, request.match_info["id"])
        if found is None:
            return error("not_found", 404)
        seller, c = found
        if c.is_draft or not c.is_active:
            return error("not_published")
        if c.notified_at is not None:
            return error("already_notified")
        bot = request.app["manager"].get(seller.bot_id)
        if bot is None:
            return error("shop_offline", 503)
        c.notified_at = showcases.utcnow()
        await session.commit()
    n = await creator.notify_new_post(bot, seller, c, request.app.get("webapp_url") or _webapp_url(request))
    return web.json_response({"sent": n})


def _webapp_url(request: web.Request) -> str | None:
    manager = request.app["manager"]
    dp = getattr(manager, "dp", None)
    return dp.workflow_data.get("webapp_url") if dp is not None else None


def add_routes(app: web.Application) -> None:
    app.router.add_get("/api/creator", api_creator)
    app.router.add_patch("/api/creator", api_creator_update)
    app.router.add_get("/api/fans", api_fans)
    app.router.add_get("/api/explore", api_explore)
    app.router.add_post("/api/store/{bot}/tip", api_store_tip)
    app.router.add_post("/api/store/{bot}/like/{id}", api_store_like)
    app.router.add_post("/api/sc/{code}/trial", api_sc_trial)
    app.router.add_post("/api/store/{bot}/adult", api_store_adult)
    app.router.add_post("/api/store/{bot}/dm", api_store_dm)
    app.router.add_post("/api/products/{id}/notify", api_product_notify)


__all__ = ["add_routes", "likes_for", "guest_of_seller_bot"]
