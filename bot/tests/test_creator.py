"""صفحه‌ی سازنده در چت: دونیت، پیام خصوصی و پیام پولی، مسدود کردن، پیام گروهی، خوش‌آمد،
بسته‌ی چندماهه، دوره‌ی آزمایشی، تأیید ۱۸+، واترمارک، دعوت سازنده، پست زمان‌بندی‌شده و فالوورها."""
import json
from datetime import timedelta

from sqlalchemy import func, select

from app import creator, showcases
from app.db import (Broadcast, Content, DmBlock, DmLink, Follower, Membership, Purchase, Seller, SessionLocal, Showcase,
                    Tip, User)
from tests.conftest import BUYER, MAIN_ID, OWNER, SHOP_ID, STRANGER, callback, message, photo_message, user
from tests.test_flows import make_product, pay


def reply_to(uid: int, target: int, text: str | None = None, photo: bool = False) -> dict:
    upd = photo_message(uid) if photo else message(uid, text)
    upd["message"]["reply_to_message"] = {"message_id": target, "date": 0,
                                          "chat": {"id": uid, "type": "private"}, "text": "x"}
    return upd


async def set_seller(**fields):
    async with SessionLocal() as s:
        seller = await s.scalar(select(Seller).where(Seller.bot_id == SHOP_ID))
        for k, v in fields.items():
            setattr(seller, k, v)
        await s.commit()


async def pre_checkout(env, payload, amount, buyer=BUYER):
    env.tg.clear()
    await env.feed(env.shop, {"pre_checkout_query": {"id": "q", "from": user(buyer), "currency": "XTR",
                                                     "total_amount": amount, "invoice_payload": payload}})
    return env.tg.sent(SHOP_ID, "AnswerPreCheckoutQuery")[-1]["ok"]


def payment(payload, amount, charge, **extra):
    return {"currency": "XTR", "total_amount": amount, "invoice_payload": payload,
            "telegram_payment_charge_id": charge, "provider_payment_charge_id": "p", **extra}


async def test_tip_flow(env):
    await env.feed(env.shop, message(BUYER, "/tip"))
    assert [b.get("callback_data") for b in env.tg.buttons(SHOP_ID)] == ["tip:10", "tip:50", "tip:100", "tip:500"]
    env.tg.clear()
    await env.feed(env.shop, callback(BUYER, "tip:50"))
    (inv,) = env.tg.sent(SHOP_ID, "SendInvoice")
    assert inv["payload"] == "t:50" and inv["prices"][0]["amount"] == 50
    assert await pre_checkout(env, "t:50", 50) is True
    assert await pre_checkout(env, "t:50", 49) is False                  # مبلغ دست‌کاری‌شده
    assert await pre_checkout(env, "t:99999", 99999) is False            # بیشتر از سقف
    assert await pre_checkout(env, "t:50", 50, buyer=OWNER) is False     # به خودش دونیت نمی‌دهد
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, successful_payment=payment("t:50", 50, "tip-1")))
    await env.feed(env.shop, message(BUYER, successful_payment=payment("t:50", 50, "tip-1")))  # تکراری تلگرام
    async with SessionLocal() as s:
        assert await s.scalar(select(func.count(Tip.id))) == 1
    to_owner = [m for m in env.tg.sent(SHOP_ID, "SendMessage") if m["chat_id"] == OWNER]
    assert len(to_owner) == 1 and "حمایت مالی تازه" in to_owner[0]["text"] and not to_owner[0].get("disable_notification")
    assert "فن شماره‌ی" in to_owner[0]["text"] and "Buyer" not in to_owner[0]["text"]   # ناشناس
    assert "ممنون" in env.tg.texts(SHOP_ID)
    # دونیت هم فن حساب می‌شود (پیام دادن مجاز)
    async with SessionLocal() as s:
        assert await creator.is_fan(s, SHOP_ID, BUYER)
    await env.feed(env.shop, message(OWNER, "/tip"))
    assert "حمایت مالی رو مشتری‌ها به تو می‌دن" in env.tg.texts(SHOP_ID)


async def dm_links(fan=None):
    async with SessionLocal() as s:
        q = select(DmLink).order_by(DmLink.id)
        if fan:
            q = q.where(DmLink.fan_id == fan)
        return (await s.scalars(q)).all()


async def test_dm_only_fans_then_relay_and_reply(env):
    await env.feed(env.shop, message(STRANGER, "سلام"))
    assert "فقط برای مشترک" in env.tg.texts(SHOP_ID) and not env.tg.sent(SHOP_ID, "CopyMessage")
    c = await make_product(env, price=10)
    await pay(env, c)
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, "سلام، کی پست جدید می‌ذاری؟"))
    header = [m for m in env.tg.sent(SHOP_ID, "SendMessage") if m["chat_id"] == OWNER]
    assert len(header) == 1 and "پیام از" in header[0]["text"] and "10" in header[0]["text"]   # خرج کل
    # ناشناس: نه اسم، نه یوزرنیم، نه آیدی فن؛ فقط شماره‌ی فن
    assert "فن شماره‌ی 2" in header[0]["text"] and "buyer" not in header[0]["text"].lower() and str(BUYER) not in header[0]["text"]
    (copy,) = env.tg.sent(SHOP_ID, "CopyMessage")
    assert copy["chat_id"] == OWNER and copy["from_chat_id"] == BUYER
    assert "فرستاده شد" in env.tg.texts(SHOP_ID)
    # پیام دوم پشت سر هم: بدون سربرگ تازه
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, "راستی"))
    assert not [m for m in env.tg.sent(SHOP_ID, "SendMessage") if m["chat_id"] == OWNER]
    links = await dm_links(BUYER)
    assert len(links) == 3                                               # سربرگ + دو پیام
    # جواب سازنده با «پاسخ» به هر کدام → به فن، محافظت‌شده؛ اکانت سازنده لو نمی‌رود (copy، نه forward)
    env.tg.clear()
    await env.feed(env.shop, reply_to(OWNER, links[-1].owner_message_id, "فردا 🙂"))
    (back,) = env.tg.sent(SHOP_ID, "CopyMessage")
    assert back["chat_id"] == BUYER and back["protect_content"] is True and not env.tg.sent(SHOP_ID, "ForwardMessage")
    assert not env.tg.sent(SHOP_ID, "SetMessageReaction")                 # ری‌اکشن روی پیام سازنده نه
    async with SessionLocal() as s:   # جواب سازنده آپلود (پست) حساب نمی‌شود
        assert await s.scalar(select(func.count(Content.id))) == 1
    # پاسخ به پیامی که از فن نیست → آپلود عادی
    env.tg.clear()
    await env.feed(env.shop, reply_to(OWNER, 999999, "یک متن"))
    assert not env.tg.sent(SHOP_ID, "CopyMessage")
    async with SessionLocal() as s:
        assert await s.scalar(select(func.count(Content.id))) == 2


async def test_dm_modes_and_block(env):
    await set_seller(dm_mode="all")
    await env.feed(env.shop, message(STRANGER, "hi"))
    assert env.tg.sent(SHOP_ID, "CopyMessage")
    await set_seller(dm_mode="off")
    env.tg.clear()
    await env.feed(env.shop, message(STRANGER, "hi"))
    assert "پیام دریافت نمی‌کنه" in env.tg.texts(SHOP_ID) and not env.tg.sent(SHOP_ID, "CopyMessage")
    await set_seller(dm_mode="all")
    await env.feed(env.shop, callback(STRANGER, f"dmblock:{STRANGER}"))   # فقط صاحب ربات
    async with SessionLocal() as s:
        assert await s.scalar(select(DmBlock.id)) is None
    await env.feed(env.shop, callback(OWNER, f"dmblock:{STRANGER}"))
    env.tg.clear()
    await env.feed(env.shop, message(STRANGER, "hi again"))
    assert not env.tg.sent(SHOP_ID, "CopyMessage")
    await env.feed(env.shop, callback(OWNER, f"dmblock:{STRANGER}"))      # رفع مسدودی
    env.tg.clear()
    await env.feed(env.shop, message(STRANGER, "hi"))
    assert env.tg.sent(SHOP_ID, "CopyMessage")


async def test_paid_message_in_dm(env):
    await set_seller(dm_mode="all")
    await env.feed(env.shop, message(BUYER, "عکس ویژه داری؟"))
    link = (await dm_links(BUYER))[-1]
    env.tg.clear()
    await env.feed(env.shop, reply_to(OWNER, link.owner_message_id, photo=True))
    buttons = [b.get("callback_data") for b in env.tg.buttons(SHOP_ID)]
    async with SessionLocal() as s:
        draft = await s.scalar(select(Content).order_by(Content.id.desc()))
    assert draft.is_draft and not draft.in_store and f"ppv:{draft.id}:{BUYER}:25" in buttons
    assert f"ppv:{draft.id}:{BUYER}:250" not in buttons                     # سقف فروشنده‌ی تازه ۱۰۰
    env.tg.clear()
    await env.feed(env.shop, callback(BUYER, f"ppv:{draft.id}:{BUYER}:25"))   # فقط سازنده
    assert not env.tg.sent(SHOP_ID, "SendInvoice")
    await env.feed(env.shop, callback(OWNER, f"ppv:{draft.id}:{BUYER}:25"))
    inv = [i for i in env.tg.sent(SHOP_ID, "SendInvoice") if i["chat_id"] == BUYER]
    assert len(inv) == 1 and inv[0]["payload"] == f"c:{draft.id}" and inv[0]["prices"][0]["amount"] == 25
    async with SessionLocal() as s:
        c = await s.get(Content, draft.id)
    assert c.is_active and not c.is_draft and not c.in_store and c.price_stars == 25   # در ویترین نیست
    # رایگان: مستقیم و محافظت‌شده
    env.tg.clear()
    await env.feed(env.shop, reply_to(OWNER, link.owner_message_id, photo=True))
    async with SessionLocal() as s:
        draft = await s.scalar(select(Content).order_by(Content.id.desc()))
    await env.feed(env.shop, callback(OWNER, f"ppv:{draft.id}:{BUYER}:0"))
    photos = [p for p in env.tg.sent(SHOP_ID, "SendPhoto") if p["chat_id"] == BUYER]
    assert photos and photos[-1]["protect_content"] is True
    # لغو: پیش‌نویس پاک می‌شود
    await env.feed(env.shop, reply_to(OWNER, link.owner_message_id, photo=True))
    async with SessionLocal() as s:
        draft = await s.scalar(select(Content).order_by(Content.id.desc()))
    await env.feed(env.shop, callback(OWNER, f"ppv:{draft.id}:{BUYER}:x"))
    async with SessionLocal() as s:
        assert await s.get(Content, draft.id) is None


async def test_broadcast_text_and_daily_limit(env):
    for uid in (BUYER, STRANGER):           # دو نفر ربات را باز کرده‌اند (فالوور)
        await env.feed(env.shop, message(uid, "/start"))
    async with SessionLocal() as s:
        assert {f.user_id for f in (await s.scalars(select(Follower))).all()} == {BUYER, STRANGER}
    await env.feed(env.shop, message(BUYER, "/broadcast"))
    assert "فقط برای صاحب" in env.tg.texts(SHOP_ID)
    env.tg.clear()
    await env.feed(env.shop, message(OWNER, "/broadcast"))
    labels = [b["text"] for b in env.tg.buttons(SHOP_ID)]
    assert any("(2)" in x for x in labels) and any("مشترک‌های فعال (0)" in x for x in labels)
    await env.feed(env.shop, callback(OWNER, "bc:subscribers"))
    assert "هنوز کسی نیست" in str(env.tg.sent(SHOP_ID, "EditMessageText")[-1])
    await env.feed(env.shop, callback(OWNER, "bc:all"))
    msg = message(OWNER, "تخفیف آخر هفته!")
    await env.feed(env.shop, msg)
    async with SessionLocal() as s:          # پیام گروهی آپلود (پست) نیست
        assert await s.scalar(select(func.count(Content.id))) == 0
    (confirm,) = [b for b in env.tg.buttons(SHOP_ID) if b.get("callback_data", "").startswith("bcgo:") and b["callback_data"] != "bcgo:x"]
    env.tg.clear()
    await env.feed(env.shop, callback(OWNER, confirm["callback_data"]))
    await creator.drain()
    copies = env.tg.sent(SHOP_ID, "CopyMessage")
    assert {c["chat_id"] for c in copies} == {BUYER, STRANGER}
    assert all(c["disable_notification"] and c["protect_content"] for c in copies)       # بی‌صدا
    assert "به 2 نفر از 2 نفر" in env.tg.texts(SHOP_ID)
    async with SessionLocal() as s:
        row = await s.scalar(select(Broadcast))
        assert (row.total, row.sent, row.segment) == (2, 2, "all")
        for _ in range(2):
            s.add(Broadcast(bot_id=SHOP_ID, segment="all", total=0))
        await s.commit()
    env.tg.clear()
    await env.feed(env.shop, message(OWNER, "/broadcast"))
    assert "سقف پیام گروهی" in env.tg.texts(SHOP_ID)


async def test_broadcast_paid_photo_to_buyers(env):
    c = await make_product(env, price=10)
    await pay(env, c)
    await env.feed(env.shop, message(STRANGER, "/start"))
    await env.feed(env.shop, message(OWNER, "/broadcast"))
    await env.feed(env.shop, callback(OWNER, "bc:buyers"))
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        draft = await s.scalar(select(Content).order_by(Content.id.desc()))
    assert draft.is_draft
    assert f"ppv:{draft.id}:b:50" in [b.get("callback_data") for b in env.tg.buttons(SHOP_ID)]
    env.tg.clear()
    await env.feed(env.shop, callback(OWNER, f"ppv:{draft.id}:b:50"))
    await creator.drain()
    invoices = env.tg.sent(SHOP_ID, "SendInvoice")
    assert [i["chat_id"] for i in invoices] == [BUYER] and invoices[0]["payload"] == f"c:{draft.id}"


async def monthly(price=30, **extra) -> int:
    async with SessionLocal() as s:
        sc = Showcase(code=f"m{price}", bot_id=SHOP_ID, owner_id=OWNER, title="VIP", access="monthly", price=price, **extra)
        s.add(sc)
        await s.commit()
        return sc.id


async def test_welcome_message_only_on_first_join(env):
    await set_seller(welcome="خوش اومدی به جمع VIP <3")
    sid = await monthly()
    exp = int((showcases.utcnow() + timedelta(days=30)).timestamp())
    await env.feed(env.shop, message(BUYER, successful_payment=payment(
        f"s:{sid}", 30, "sub-1", subscription_expiration_date=exp, is_recurring=True, is_first_recurring=True)))
    welcome = [m for m in env.tg.sent(SHOP_ID, "SendMessage") if "جمع VIP &lt;3" in m["text"]]
    assert len(welcome) == 1 and welcome[0]["chat_id"] == BUYER and welcome[0]["disable_notification"]
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, successful_payment=payment(
        f"s:{sid}", 30, "sub-2", subscription_expiration_date=exp + 30 * 86400, is_recurring=True)))
    assert "جمع VIP" not in env.tg.texts(SHOP_ID)                         # تمدید: خوش‌آمد دوباره نه


async def test_bundle_months_with_discount(env):
    sid = await monthly(price=30, bundles=json.dumps({"3": 10, "12": 50}))
    async with SessionLocal() as s:
        sc = await s.get(Showcase, sid)
    assert showcases.bundle_options(sc) == [{"months": 3, "off": 10, "price": 81}, {"months": 12, "off": 50, "price": 180}]
    args = showcases.invoice_args(sc, "fa", months=3)
    assert args["payload"] == f"s:{sid}:3" and "subscription_period" not in args and args["prices"][0].amount == 81
    assert await pre_checkout(env, f"s:{sid}:3", 81) is True
    assert await pre_checkout(env, f"s:{sid}:3", 30) is False
    assert await pre_checkout(env, f"s:{sid}:6", 150) is False             # بسته‌ی تعریف‌نشده
    await env.feed(env.shop, message(BUYER, successful_payment=payment(f"s:{sid}:3", 81, "b-1")))
    async with SessionLocal() as s:
        m = await s.scalar(select(Membership))
    assert m.amount == 81 and m.sub_charge_id is None
    assert timedelta(days=89) < m.expires_at - showcases.utcnow() <= timedelta(days=90)
    # بسته‌ی دوم از پایان قبلی ادامه می‌دهد
    assert await pre_checkout(env, f"s:{sid}:3", 81) is True
    await env.feed(env.shop, message(BUYER, successful_payment=payment(f"s:{sid}:3", 81, "b-2")))
    async with SessionLocal() as s:
        last = await s.scalar(select(Membership).order_by(Membership.id.desc()))
    assert timedelta(days=179) < last.expires_at - showcases.utcnow() <= timedelta(days=180)
    assert showcases.clean_bundles({"3": 60}) is False and showcases.clean_bundles({"5": 10}) is False
    assert showcases.clean_bundles({"6": 20}) == '{"6": 20}' and showcases.clean_bundles({}) is None


async def test_free_trial_once_then_subscribe(env):
    sid = await monthly(price=30, trial_days=7)
    async with SessionLocal() as s:
        sc = await s.get(Showcase, sid)
        m = await showcases.start_trial(s, sc, BUYER)
        assert isinstance(m, Membership) and m.amount == 0 and showcases.is_trial(m)
        assert await showcases.active_membership(s, sid, BUYER)
        assert await showcases.start_trial(s, sc, BUYER) == "sc_trial_used"
    # وسط دوره‌ی آزمایشی می‌تواند مشترک شود
    assert await pre_checkout(env, f"s:{sid}", 30) is True
    async with SessionLocal() as s:
        no_trial = Showcase(code="nt", bot_id=SHOP_ID, owner_id=OWNER, title="x", access="once", price=5, trial_days=7)
        s.add(no_trial)
        await s.commit()
        assert await showcases.start_trial(s, no_trial, BUYER) == "sc_no_trial"


async def test_sensitive_content_has_no_age_gate_on_bale(env):
    """در بله محتوای بزرگسال کلاً ممنوع است؛ «حساس» فقط یعنی زودگذر، پس پرسش ۱۸+ نداریم."""
    c = await make_product(env, price=10, sensitive=True)
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))
    assert "۱۸" not in env.tg.texts(SHOP_ID) and env.tg.sent(SHOP_ID, "SendInvoice")
    env.tg.clear()
    await env.feed(env.shop, message(BUYER, f"/start {c.code}"))          # دیگر نمی‌پرسد
    assert env.tg.sent(SHOP_ID, "SendInvoice")


async def test_watermark_on_bought_photo(env):
    await set_seller(watermark=True)
    c = await make_product(env, price=10)
    p = await pay(env, c)
    env.tg.clear()
    await env.feed(env.shop, callback(BUYER, f"open:{p.id}"))
    (photo,) = [x for x in env.tg.sent(SHOP_ID, "SendPhoto") if x["chat_id"] == BUYER]
    assert not isinstance(photo["photo"], str) and photo["protect_content"] is True   # فایل تازه با واترمارک
    raw = creator.watermark_photo(__import__("tests.conftest", fromlist=["_JPEG"])._JPEG, "@buyer")
    assert raw[:2] == b"\xff\xd8"


async def test_creator_referral(env):
    await env.feed(env.main, message(777, f"/start ref_{OWNER}"))
    await env.feed(env.main, message(778, "/start ref_778"))              # خودش را دعوت نمی‌کند
    async with SessionLocal() as s:
        u, self_ref = await s.get(User, 777), await s.get(User, 778)
    assert (u.source, u.referrer_id) == ("ref", OWNER) and self_ref.referrer_id is None
    assert "خوش اومدی" in "".join(m["text"] for m in env.tg.sent(MAIN_ID, "SendMessage"))


async def test_scheduled_post_goes_live(env):
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        c = await s.scalar(select(Content))
        c.price_stars, c.publish_at = 10, showcases.utcnow() - timedelta(minutes=1)
        await s.commit()
    env.tg.clear()
    assert await creator.publish_due(env.manager) == 1
    async with SessionLocal() as s:
        c = await s.scalar(select(Content))
    assert c.is_active and not c.is_draft and c.publish_at is None
    assert "منتشر شد" in env.tg.texts(SHOP_ID)
    assert await creator.publish_due(env.manager) == 0


async def test_fans_view_and_earnings(env):
    c = await make_product(env, price=10)
    await pay(env, c)
    await env.feed(env.shop, message(BUYER, successful_payment=payment("t:50", 50, "tip-x")))
    await env.feed(env.shop, message(STRANGER, "/start"))
    async with SessionLocal() as s:
        seller = await s.scalar(select(Seller))
        view = await creator.fans_view(s, seller)
        money = await creator.earnings(s, SHOP_ID)
    assert [(f["id"], f["spent"], f["status"]) for f in view["fans"]] == [(BUYER, 60, "buyer")]
    assert view["counts"]["all"] == 2 and view["followers"] == 2
    assert (money["sales"], money["tips"], money["subs"]) == (10, 50, 0) and money["month"]["tips"] == 50
    async with SessionLocal() as s:
        assert await s.scalar(select(func.count(Purchase.id))) == 1


async def test_chat_threads_both_ways_like_anonymous_chat(env):
    """فن پیام می‌دهد → سازنده Reply می‌زند (Reply روی پیام فن می‌رسد) → فن روی جواب Reply می‌زند (Reply روی پیام سازنده)."""
    await set_seller(dm_mode="all")
    first = message(BUYER, "سلام، یه سؤال داشتم")
    await env.feed(env.shop, first)
    fan_msg_id = first["message"]["message_id"]
    async with SessionLocal() as s:
        link = await s.scalar(select(DmLink).where(DmLink.fan_message_id == fan_msg_id))
    assert link and link.fan_id == BUYER
    # سازنده وسط کار دیگری بوده (مثلاً منتظر قیمت)؛ Reply باز هم جواب حساب می‌شود
    await env.feed(env.shop, photo_message(OWNER))
    async with SessionLocal() as s:
        draft = await s.scalar(select(Content).order_by(Content.id.desc()))
    await env.feed(env.shop, callback(OWNER, f"price:{draft.id}:custom"))
    env.tg.clear()
    answer = reply_to(OWNER, link.owner_message_id, "سلام! بپرس")
    await env.feed(env.shop, answer)
    (back,) = env.tg.sent(SHOP_ID, "CopyMessage")
    assert back["chat_id"] == BUYER and back["reply_parameters"]["message_id"] == fan_msg_id
    async with SessionLocal() as s:
        mine = await s.scalar(select(DmLink).where(DmLink.owner_message_id == answer["message"]["message_id"]))
    assert mine.fan_id == BUYER and mine.fan_message_id
    # فن روی جواب سازنده Reply می‌زند → برای سازنده Reply روی پیام خودش
    env.tg.clear()
    await env.feed(env.shop, reply_to(BUYER, mine.fan_message_id, "مرسی 🙏"))
    (fwd,) = env.tg.sent(SHOP_ID, "CopyMessage")
    assert fwd["chat_id"] == OWNER and fwd["reply_parameters"]["message_id"] == answer["message"]["message_id"]
    # سازنده دوباره روی جواب خودش Reply می‌زند → باز هم به همان فن
    env.tg.clear()
    await env.feed(env.shop, reply_to(OWNER, answer["message"]["message_id"], "خواهش 🙂"))
    assert env.tg.sent(SHOP_ID, "CopyMessage")[0]["chat_id"] == BUYER


async def test_broadcast_stops_and_says_so_when_bale_refuses(env, monkeypatch):
    """بله برای پیام‌های بازو سقف تعاملی دارد: اگر ارسال‌ها پشت سر هم رد شد، ادامه نمی‌دهیم و راستش را می‌گوییم."""
    from aiogram.exceptions import TelegramRetryAfter
    from aiogram.methods import CopyMessage
    for uid in (BUYER, STRANGER):
        await env.feed(env.shop, message(uid, "/start"))
    await env.feed(env.shop, message(OWNER, "/broadcast"))
    await env.feed(env.shop, callback(OWNER, "bc:all"))
    await env.feed(env.shop, message(OWNER, "خبر تازه"))
    (confirm,) = [b for b in env.tg.buttons(SHOP_ID) if b.get("callback_data", "").startswith("bcgo:") and b["callback_data"] != "bcgo:x"]

    async def refused(self, chat_id, from_chat_id, message_id, **kw):
        raise TelegramRetryAfter(method=CopyMessage(chat_id=chat_id, from_chat_id=from_chat_id, message_id=message_id),
                                 message="Too Many Requests", retry_after=30)
    monkeypatch.setattr(type(env.shop), "copy_message", refused)
    env.tg.clear()
    await env.feed(env.shop, callback(OWNER, confirm["callback_data"]))
    await creator.drain()
    text = env.tg.texts(SHOP_ID)
    assert "نیمه‌کاره" in text and "به 0 نفر از 2 نفر" in text
    async with SessionLocal() as s:
        assert (await s.scalar(select(Broadcast))).sent == 0
