import os
import time
from datetime import datetime

from sqlalchemy import (BigInteger, Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint,
                        func)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings

# PostgreSQL: هر اتصال به وقت UTC (کد ما همه‌جا زمان UTC بدون منطقه مقایسه می‌کند؛ اگر سرور دیتابیس روی
# وقت دیگری باشد، مرز «همین الان» چند ساعت جابه‌جا می‌شد و فروش‌های تازه در آمار دیده نمی‌شدند)
_connect_args = {}
if settings.database_url.startswith("postgresql+asyncpg"):
    _connect_args = {"server_settings": {"timezone": "UTC"}}
    # asyncpg زمانِ بدون منطقه را به وقت محلی سیستم‌عامل می‌خواند؛ برنامه همه‌جا UTC بدون منطقه به کار می‌برد.
    # روی سیستمی که ساعتش UTC نیست (مثلاً مک با وقت تهران) مقایسه‌ها ۳٫۵ ساعت جابه‌جا می‌شد (تست پیدا کرد)
    os.environ["TZ"] = "UTC"
    time.tzset()
engine = create_async_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)  # Telegram user id
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(128))
    language: Mapped[str] = mapped_column(String(8), default="fa")
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    # اختلاف ساعت محلی با UTC به دقیقه (از Mini App)؛ برای «فروش امروز» به وقت خود کاربر
    tz_offset: Mapped[int | None] = mapped_column(Integer)
    # از کجا آمده (اولین تماس): برچسب لینک تبلیغ src_<tag>، یا link (لینک رایگان)، shop (ویترین/ربات فروشنده)،
    # direct (بدون لینک)، made (پانویس «ساخته‌شده با UploadFly»). برای فهمیدن این‌که کدام تبلیغ جواب می‌دهد
    source: Mapped[str | None] = mapped_column(String(32), index=True)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, index=True)  # سازنده‌ای که او را دعوت کرده (ref_<id>)
    adult_ok: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # تأیید ۱۸+ برای محتوای حساس
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Content(Base):
    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    # file_id در تلگرام مخصوص هر ربات است، پس ثبت می‌کنیم محتوا در کدام ربات آپلود شده
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)

    kind: Mapped[str] = mapped_column(String(16))
    # شناسه‌های تلگرام طول تضمین‌شده ندارند؛ Text تا PostgreSQL هیچ‌وقت ردشان نکند (SQLite طول را بررسی نمی‌کند)
    file_id: Mapped[str | None] = mapped_column(Text)
    file_unique_id: Mapped[str | None] = mapped_column(String(64), index=True)  # برای لیست سیاه
    text: Mapped[str | None] = mapped_column(Text)  # متن پیام یا کپشن (HTML)
    # اطلاعات نمایشی که فروشنده می‌نویسد (برای ویترین و Explore آینده). دسته از فهرست ثابت CATEGORIES است
    title: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(24), index=True)

    # مشخصاتی که از خود تلگرام می‌آید، نه از ادعای فروشنده
    file_name: Mapped[str | None] = mapped_column(String(256))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    duration: Mapped[int | None] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    thumb_file_id: Mapped[str | None] = mapped_column(Text)  # تصویر کوچک خود تلگرام؛ برای فایل‌های بالای ۲۰MB
    # پیش‌نمایش ساخته‌شده توسط سیستم (JSON): {"photos": [file_id...], "voice": file_id, "text": "...", "pages": n}
    preview: Mapped[str | None] = mapped_column(Text)

    price_stars: Mapped[int] = mapped_column(Integer, default=0)  # 0 = رایگان
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)  # UTC؛ در این زمان خودکار آرشیو می‌شود
    # محتوای حساس (۱۸+ یا در معرض ریپورت): بعد از دیده شدن خودکار پاک می‌شود و خریدار با لینک دوباره می‌بیند
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # فروشنده اجازه داده خریدار کپی/ذخیره/فوروارد کند (مثلاً متن پرامپت). محتوای حساس همیشه محافظت‌شده است
    allow_save: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # خاموش: در ویترین (و Explore آینده) نیست، ولی لینک خودش کار می‌کند (فروش جداگانه)
    in_store: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    # پیش‌نویس = در ربات فروشنده آپلود شده ولی هنوز منتشر نشده. منتشرشده + is_active=False یعنی بایگانی
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    publish_at: Mapped[datetime | None] = mapped_column(DateTime)   # UTC؛ پیش‌نویسی که در این زمان خودکار منتشر می‌شود
    notified_at: Mapped[datetime | None] = mapped_column(DateTime)  # خبر «پست تازه» به فن‌ها فرستاده شده
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Seller(Base):
    """ربات شخصی فروشنده که به UploadFly وصل شده. استارزِ فروش مستقیم به موجودی همین ربات می‌رود."""
    __tablename__ = "sellers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    bot_username: Mapped[str] = mapped_column(String(64))
    token_enc: Mapped[str] = mapped_column(Text)  # توکن رمزنگاری‌شده؛ هرگز متن خام ذخیره نمی‌شود
    # توکن کیف پول بله‌ی همین بازو (رمزنگاری‌شده)؛ بدون آن فروش پولی ممکن نیست. پول مستقیم به همین کیف پول می‌رود
    wallet_enc: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # تعلیق خودکار به‌خاطر بازپرداخت زیاد: فروش جدید ممکن نیست، خریدارهای قبلی هنوز به محتوایشان دسترسی دارند
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # ظاهر فروشگاه: لوگو (برای همه‌ی ویترین‌ها) + تم و بنر ویترین اصلی؛ شناسه‌ها به جدول images
    logo: Mapped[str | None] = mapped_column(String(24))
    theme: Mapped[str | None] = mapped_column(String(16))
    cover: Mapped[str | None] = mapped_column(String(24))
    style: Mapped[str | None] = mapped_column(Text)   # JSON: looks.STYLE_DEFAULT (ویترین اصلی)
    background: Mapped[str | None] = mapped_column(String(24))  # عکس پس‌زمینه‌ی ویترین اصلی (Image.id)
    links: Mapped[str | None] = mapped_column(Text)   # JSON: لینک شبکه‌های اجتماعی فروشگاه (looks.clean_links)
    # صفحه‌ی سازنده
    bio: Mapped[str | None] = mapped_column(Text)                    # معرفی کوتاه زیر اسم
    category: Mapped[str | None] = mapped_column(String(24))         # creator.CREATOR_CATEGORIES (صفحه‌ی کشف)
    listed: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")  # در صفحه‌ی کشف دیده شود
    dm_mode: Mapped[str] = mapped_column(String(8), default="fans", server_default="fans")  # all | fans | off
    welcome: Mapped[str | None] = mapped_column(Text)                # پیام خوش‌آمد خودکار به مشترک تازه
    watermark: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # یوزرنیم خریدار روی عکس
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Image(Base):
    """عکسی که فروشنده برای لوگو یا بنر ویترین آپلود کرده؛ دوباره ساخته‌شده (JPEG بدون متادیتا).
    شناسه‌ی تصادفی تا نتوان عکس‌ها را با شمردن پیدا کرد."""
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String(24), primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_id: Mapped[int] = mapped_column(Integer, ForeignKey("contents.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    # شناسه‌ی پرداخت تلگرام؛ برای بازپرداخت خودکار در مرحله‌ی ۳ لازم است
    charge_id: Mapped[str] = mapped_column(Text, unique=True)  # واقعی‌ها حدود ۱۴۰ کاراکترند
    refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime)  # UTC بدون منطقه‌ی زمانی
    # بازپرداخت فقط تا قبل از باز کردن محتوا ممکن است؛ بعد از آن فقط «گزارش کلاهبرداری»
    opened_at: Mapped[datetime | None] = mapped_column(DateTime)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime)
    report_reason: Mapped[str | None] = mapped_column(String(16))  # REPORT_REASONS در payments
    # شناسه‌ی پیام‌هایی که محتوا در چت خریدار با آن‌ها فرستاده شده؛ با بازپرداخت پاک می‌شوند
    message_ids: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Showcase(Base):
    """ویترین اضافه‌ی یک فروشگاه (ویترین اصلی همان Content.in_store است و همیشه رایگان).
    access: free = همه می‌بینند | once = یک‌بار پرداخت، دسترسی همیشگی | monthly = اشتراک ۳۰ روزه‌ی تلگرام"""
    __tablename__ = "showcases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # لینک: t.me/<ربات>?start=sc_<code>
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    access: Mapped[str] = mapped_column(String(10), default="free")
    price: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # False = حذف‌شده
    # خصوصی: در فهرست «ویترین‌های دیگر این فروشگاه» نیست؛ فقط با لینک خودش
    private: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # آرشیو: عضو تازه نمی‌پذیرد و برای غیرعضوها بسته است؛ اعضای قبلی دسترسی‌شان را نگه می‌دارند
    archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)  # UTC؛ در این زمان خودکار آرشیو می‌شود
    theme: Mapped[str | None] = mapped_column(String(16))   # یکی از THEMES در app/looks.py
    cover: Mapped[str | None] = mapped_column(String(24))   # بنر (Image.id)
    style: Mapped[str | None] = mapped_column(Text)          # JSON: looks.STYLE_DEFAULT
    background: Mapped[str | None] = mapped_column(String(24))  # عکس پس‌زمینه (Image.id)
    trial_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # اشتراک ماهانه: روز آزمایشی رایگان
    bundles: Mapped[str | None] = mapped_column(Text)  # JSON {"3": تخفیف٪, "6": ..., "12": ...}: چند ماه یک‌جا
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShowcaseItem(Base):
    """محتوای داخل ویترین. member_free: برای اعضای ویترین پولی رایگان است؛ وگرنه قیمت خودش را دارد."""
    __tablename__ = "showcase_items"
    __table_args__ = (UniqueConstraint("showcase_id", "content_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    showcase_id: Mapped[int] = mapped_column(Integer, ForeignKey("showcases.id"), index=True)
    content_id: Mapped[int] = mapped_column(Integer, ForeignKey("contents.id"), index=True)
    member_free: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    """ورود پولی به یک ویترین. فعال = بازپرداخت‌نشده و (بدون انقضا یا هنوز منقضی‌نشده)."""
    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    showcase_id: Mapped[int] = mapped_column(Integer, ForeignKey("showcases.id"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int] = mapped_column(Integer)
    charge_id: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)  # UTC بدون منطقه؛ فقط اشتراک ماهانه
    canceled: Mapped[bool] = mapped_column(Boolean, default=False)  # تمدید خودکار لغو شده (ماهانه)
    refunded: Mapped[bool] = mapped_column(Boolean, default=False)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime)  # اولین محتوای باز شده؛ بعد از آن بازپرداخت نه
    # اشتراک ماهانه: شناسه‌ی پرداخت اول (برای لغو/فعال کردن تمدید) و اینکه یادآوری‌ها فرستاده شده‌اند
    sub_charge_id: Mapped[str | None] = mapped_column(Text)
    reminded: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    end_notified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Review(Base):
    """امتیاز ۱ تا ۵ از خریدار واقعی (فقط کسی که خریده و محتوا را باز کرده). هر خریدار یک امتیاز برای هر محتوا."""
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("content_id", "buyer_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_id: Mapped[int] = mapped_column(Integer, ForeignKey("contents.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    stars: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Follower(Base):
    """کسی که ربات یک سازنده را باز کرده (دنبال‌کننده‌ی رایگان). برای پیام گروهی و آمار."""
    __tablename__ = "followers"
    __table_args__ = (UniqueConstraint("bot_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Tip(Base):
    """دونیت فن به سازنده (استارز مستقیم به ربات سازنده). content_id: دونیت روی یک پست."""
    __tablename__ = "tips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    content_id: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer)
    charge_id: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DmLink(Base):
    """پیام فن که برای سازنده فرستاده شد: سازنده با «پاسخ» به همین پیام جواب می‌دهد و ربات به فن می‌رساند.
    اکانت شخصی سازنده هیچ‌وقت به فن نشان داده نمی‌شود."""
    __tablename__ = "dm_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    owner_message_id: Mapped[int] = mapped_column(BigInteger, index=True)
    fan_id: Mapped[int] = mapped_column(BigInteger, index=True)
    # همان پیام در چت فن (برای Reply دوطرفه، مثل ربات‌های چت ناشناس)؛ سربرگ «پیام از…» ندارد
    fan_message_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DmBlock(Base):
    """فنی که سازنده مسدودش کرده: پیامش دیگر به سازنده نمی‌رسد."""
    __tablename__ = "dm_blocks"
    __table_args__ = (UniqueConstraint("bot_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)


class Like(Base):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("content_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_id: Mapped[int] = mapped_column(Integer, ForeignKey("contents.id"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Broadcast(Base):
    """پیام گروهی سازنده به فن‌ها (برای سقف روزانه و گزارش)."""
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    segment: Mapped[str] = mapped_column(String(16))
    content_id: Mapped[int | None] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer, default=0)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Blacklist(Base):
    """فایل مسدود (با file_unique_id که بین همه‌ی ربات‌ها یکسان است): دوباره در هیچ رباتی آپلود نمی‌شود."""
    __tablename__ = "blacklist"

    file_unique_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    reason: Mapped[str] = mapped_column(String(32))  # reports | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeleteJob(Base):
    """پیامی که باید در زمان مشخص پاک شود. در دیتابیس است تا با ری‌استارت ربات فراموش نشود."""
    __tablename__ = "delete_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bot_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    delete_at: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC بدون منطقه‌ی زمانی


def is_id(value, big: bool = False) -> bool:
    """شناسه‌ای که از بیرون (آدرس، دکمه، بدنه) آمده: فقط رقم انگلیسی و در محدوده‌ی ستون دیتابیس.
    عدد خیلی بزرگ در PostgreSQL خطای ۵۰۰ می‌داد. big=True برای شناسه‌ی ربات‌ها (BigInteger)."""
    text = str(value)
    return text.isascii() and text.isdigit() and int(text) < (2 ** 63 if big else 2 ** 31)


def cb_id(data: str | None) -> int:
    """شناسه‌ی داخل دکمه‌ی چت («open:12»)؛ دکمه‌ی دست‌کاری‌شده = 0 (که در دیتابیس پیدا نمی‌شود)."""
    part = ((data or "").split(":") + [""])[1]
    return int(part) if is_id(part) else 0


# ستون‌هایی که بعد از ساخت اولیه‌ی جدول اضافه شده‌اند (تا وقتی Alembic اضافه شود)
_ADDED_COLUMNS = {
    "contents": {"is_sensitive": "BOOLEAN NOT NULL DEFAULT false", "allow_save": "BOOLEAN NOT NULL DEFAULT false",
                 "thumb_file_id": "TEXT", "preview": "TEXT", "is_draft": "BOOLEAN NOT NULL DEFAULT false",
                 "title": "VARCHAR(80)", "description": "TEXT", "category": "VARCHAR(24)",
                 "in_store": "BOOLEAN NOT NULL DEFAULT true", "expires_at": "TIMESTAMP",
                 "publish_at": "TIMESTAMP", "notified_at": "TIMESTAMP"},
    "showcases": {"private": "BOOLEAN NOT NULL DEFAULT false", "archived": "BOOLEAN NOT NULL DEFAULT false",
                  "expires_at": "TIMESTAMP", "theme": "VARCHAR(16)", "cover": "VARCHAR(24)", "style": "TEXT",
                  "background": "VARCHAR(24)", "trial_days": "INTEGER NOT NULL DEFAULT 0", "bundles": "TEXT"},
    "users": {"tz_offset": "INTEGER", "source": "VARCHAR(32)", "referrer_id": "BIGINT",
              "adult_ok": "BOOLEAN NOT NULL DEFAULT false"},
    "sellers": {"is_suspended": "BOOLEAN NOT NULL DEFAULT false", "wallet_enc": "TEXT", "logo": "VARCHAR(24)", "theme": "VARCHAR(16)",
                "cover": "VARCHAR(24)", "style": "TEXT", "links": "TEXT",
                "background": "VARCHAR(24)", "bio": "TEXT", "category": "VARCHAR(24)",
                "listed": "BOOLEAN NOT NULL DEFAULT true", "dm_mode": "VARCHAR(8) NOT NULL DEFAULT 'fans'",
                "welcome": "TEXT", "watermark": "BOOLEAN NOT NULL DEFAULT false"},
    "purchases": {"refunded_at": "TIMESTAMP", "message_ids": "TEXT NOT NULL DEFAULT ''",
                  "opened_at": "TIMESTAMP", "reported_at": "TIMESTAMP",
                  "report_reason": "VARCHAR(16)"},
    "dm_links": {"fan_message_id": "BIGINT"},
    "memberships": {"sub_charge_id": "TEXT", "reminded": "BOOLEAN NOT NULL DEFAULT false",
                    "end_notified": "BOOLEAN NOT NULL DEFAULT false"},
}


def _add_missing_columns(conn) -> None:
    from sqlalchemy import inspect, text
    insp = inspect(conn)
    for table, cols in _ADDED_COLUMNS.items():
        existing = {c["name"] for c in insp.get_columns(table)}
        for name, ddl in cols.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
