import html
import json
import re
from pathlib import Path

TEXTS = {
    "fa": {
        "welcome": "سلام {name} 👋\n\nبه <b>UploadFly</b> خوش اومدی.\n"
                   "هر چیزی رو برام بفرست (فایل، عکس، ویدیو، موزیک، ویس یا حتی متن) تا برات یک لینک اختصاصی بسازم.\n\n"
                   "هر کس روی لینک بزنه، محتوا رو دریافت می‌کنه.\n\n"
                   "🌐 English: /lang",
        "paysupport": "🛟 <b>پشتیبانی پرداخت</b>\n\nاین فروشگاه مال {shop} است و استارزی که می‌پردازید مستقیم به ربات خود فروشنده می‌رود، نه UploadFly.\n\n• <b>هنوز محتوا را باز نکرده‌اید؟</b> تا ۲۴ ساعت بعد از خرید، دکمه‌ی «بازپرداخت» زیر پیام خرید پولتان را کامل برمی‌گرداند.\n• <b>محتوا خراب است یا با توضیحش نمی‌خواند؟</b> دکمه‌ی «گزارش مشکل» زیر محتوا را بزنید؛ مدیران UploadFly بررسی می‌کنند.\n• <b>اشتراک ماهانه:</b> تمدید خودکار را هر وقت بخواهید از صفحه‌ی ویترین خاموش کنید.{contact}\n\nشرایط استفاده: /terms",
        "paysupport_contact": "\n• <b>سؤال دیگری دارید؟</b> به فروشنده پیام دهید: @{user}",
        "paysupport_main": "🛟 <b>پشتیبانی پرداخت</b>\n\nخرید در ربات خود هر فروشگاه انجام می‌شود و استارز مستقیم به همان ربات می‌رود. برای بازپرداخت یا مشکل خرید، به ربات همان فروشگاه بروید و آن‌جا /paysupport را بفرستید.\n\nشرایط استفاده: /terms",
        "terms": "📜 <b>شرایط استفاده‌ی UploadFly</b>\n\n۱. UploadFly ابزار ساخت لینک و فروشگاه است. هر فروشگاه ربات خود فروشنده است و مسئولیت محتوایش با خود اوست.\n۲. پرداخت با Telegram Stars و مستقیم به ربات فروشنده است؛ UploadFly پولی دریافت یا نگه‌داری نمی‌کند.\n۳. بازپرداخت فقط پیش از باز کردن محتوا و تا ۲۴ ساعت بعد از خرید، حداکثر ۳ بار در ۳۰ روز. ورودی ویترین هم تا وقتی محتوایی از آن باز نشده. اشتراک ماهانه هر وقت لغو شود، تا پایان دوره فعال می‌ماند.\n۴. ممنوع: سلاح، مواد مخدر، قاچاق انسان، کلاهبرداری و <b>هر محتوای جنسی مربوط به کودکان</b> (مسدود شدن دائمی). محتوای بزرگسالان فقط در ربات فروشنده و با علامت «حساس».\n۵. محتوای خریده‌شده محافظت‌شده و فقط برای استفاده‌ی شخصی شماست.\n۶. مدیران می‌توانند محتوای ناقض قوانین را حذف و فروشگاه یا کاربر را مسدود کنند.\n۷. قوانین Telegram Stars هم برقرار است: telegram.org/tos/stars",
        "stars_guide": "⭐ <b>استارز از کجا بخرم؟</b>\n\nاستارز پول رسمی تلگرام است و وقتی می‌خری، مستقیم به فروشنده می‌رسد.\n\n1. <b>با تومان:</b> سایت‌ها و ربات‌های فروش استارز فقط یوزرنیم تلگرامت ({user}) را می‌خواهند و استارز را به حسابت واریز می‌کنند. قیمت‌ها را مقایسه کن و از فروشنده‌ی معتبر بخر.\n2. <b>داخل تلگرام:</b> تنظیمات ← استارزهای من ← خرید (با کارت بین‌المللی یا اپل/گوگل).\n\n⚠️ هیچ‌وقت کد ورود یا رمز تلگرامت را به کسی نده.\n\nبعد از خرید، دوباره دکمه‌ی پرداخت را بزن.",
        "stars_offer_hint": "⭐ استارز نداری؟ /stars",
        "stars_no_user": "(اول در تنظیمات تلگرام یک یوزرنیم بساز)",
        "paysupport_escalate": "\n\n🎧 به نتیجه نرسیدی؟ در @{main} دستور /support را بزن.",
        "support_text": "🎧 <b>پشتیبانی UploadFly</b>\n\nجواب بیشتر سؤال‌ها در «سؤالات متداول» هست. اگر پیدا نکردی، مستقیم به پشتیبانی پیام بده.{email}\n\nکد کاربری تو: <code>{id}</code> (این را برای پشتیبانی بفرست تا سریع‌تر کمکت کنیم)",
        "support_email_line": "\n✉️ ایمیل: {email}",
        "btn_support_faq": "❓ سؤالات متداول",
        "btn_support_chat": "💬 چت با پشتیبانی",
        "help": "📌 <b>راهنما</b>\n\n"
                "هر فایل، عکس، ویدیو، موزیک یا متنی بفرستی، یک لینک می‌گیری.\n\n"
                "<b>دستورها</b>\n"
                "/mylinks — لینک‌های من\n"
                "/shop — فروشگاه من (فروش با استارز)\n"
                "/lang — تغییر زبان\n"
                "/help — همین راهنما\n\n"
                "📱 مدیریت محصولات، آمار و ویترین از دکمه‌ی «UploadFly» کنار جای تایپ.\n\n"
                "⚠️ سلاح، مواد مخدر، قاچاق انسان، کلاهبرداری و هر محتوای جنسی مربوط به زیر ۱۸ سال ممنوعه و حساب رو مسدود می‌کنه.\n"
                "🔞 محتوای بزرگسال فقط در ربات فروشگاه شخصی و با علامت «حساس و زودگذر».",
        "link_created": "✅ <b>لینک ساخته شد</b>\n\n{specs}\n\n🔗 <code>{link}</code>",
        "unsupported": "این نوع پیام فعلاً پشتیبانی نمی‌شه. فایل، عکس، ویدیو، موزیک، ویس یا متن بفرست.",
        "not_found": "❌ این لینک وجود نداره یا غیرفعال شده.",
        "unknown_command": "این دستور رو نمی‌شناسم. /help رو بزن.",
        "mylinks_empty": "هنوز هیچ لینکی نساختی. یک فایل یا متن برام بفرست.",
        "mylinks_header": "🗂 <b>لینک‌های اخیر تو</b>\n",
        "views": "بازدید",
        "btn_copy": "📋 کپی لینک",
        "btn_share": "📤 اشتراک‌گذاری",
        "kinds": {"text": "متن", "photo": "عکس", "video": "ویدیو", "animation": "گیف",
                  "document": "فایل", "audio": "موزیک", "voice": "ویس", "video_note": "ویدیوی دایره‌ای"},
        "spec_type": "نوع", "spec_size": "حجم", "spec_duration": "مدت",
        "spec_resolution": "ابعاد", "spec_name": "نام فایل", "spec_words": "تعداد کلمه", "spec_pages": "تعداد صفحه",
        "preview_caption_buyer": "👀 پیش‌نمایش خودکار (ساخته‌شده توسط سیستم، نه فروشنده)",
        "preview_caption_seller": "👀 این پیش‌نمایشیه که خریدار قبل از خرید می‌بینه. سیستم خودکار ساخته و قابل تغییر نیست.",
        "preview_building": "⏳ در حال ساخت پیش‌نمایش خودکار...",
        "preview_text": "👀 <b>شروع متن:</b>\n<blockquote>{snippet}</blockquote>",
        "preview_thumb_only": "ℹ️ فایل بزرگ‌تر از ۲۰ مگابایته، پس فقط تصویر کوچکِ خود تلگرام به‌عنوان پیش‌نمایش نشون داده می‌شه.",
        "lang_choose": "🌐 زبان را انتخاب کن / Choose your language:",
        "lang_set": "✅ زبان ربات فارسی شد.",
        "time_h": "{h} ساعت", "time_m": "{m} دقیقه", "time_join": " و ",
        "btn_refund": "↩️ بازپرداخت",
        "btn_open": "👁 نمایش محتوا",
        "received": "✅ <b>دریافت شد</b>\n\n{specs}\n\nقیمت و ویژگی‌های محصول رو تنظیم کن تا منتشر بشه 👇",
        "btn_setup_product": "⚙️ تنظیم و انتشار محصول",
        "btn_price_in_chat": "💬 قیمت‌گذاری سریع همین‌جا",
        "paid_pending": "✅ پرداخت انجام شد.\n\n"
                        "👁 برای دیدن محتوا «نمایش» رو بزن.\n"
                        "↩️ اگه منصرف شدی، تا ۲۴ ساعت و <b>قبل از نمایش</b> می‌تونی استارزت رو کامل پس بگیری. "
                        "بعد از نمایش، بازپرداخت ممکن نیست.",
        "paid_opened": "✅ پرداخت انجام شد. محتوا:",
        "refund_opened": "محتوا رو دیدی، پس بازپرداخت ممکن نیست. اگه با توضیحات فرق داشت، «گزارش مشکل» رو بزن.",
        "report_offer": "اگه محتوا با مشخصات یا توضیحات فروشنده فرق داشت یا مشکلی داشت، گزارش بده تا بررسی بشه.",
        "btn_report": "🚩 گزارش مشکل",
        "report_choose": "🚩 مشکل چی بود؟",
        "reason_mismatch": "با توضیحات فرق داشت",
        "reason_broken": "فایل خراب یا ناقص بود",
        "reason_forbidden": "محتوای ممنوع",
        "reason_other": "مشکل دیگه",
        "report_already": "این خرید رو قبلاً گزارش دادی.",
        "report_expired": "مهلت گزارش (۷ روز بعد از دیدن) تموم شده.",
        "report_done": "🚩 گزارشت ثبت شد و بررسی می‌شه. ممنون که به امن موندن UploadFly کمک کردی.",
        "report_seller": "🚩 یک خریدار یکی از فروش‌هات رو گزارش کرد ({reason}). گزارش‌ها توسط UploadFly بررسی می‌شن.",
        "btn_save_off": "📋 اجازه‌ی کپی و ذخیره: خاموش",
        "btn_save_on": "📋 اجازه‌ی کپی و ذخیره: روشن ✅",
        "save_label": "📋 خریدار می‌تونه کپی و ذخیره کنه",
        "save_not_sensitive": "محتوای حساس همیشه محافظت‌شده‌ست و قابل کپی نیست.",
        "offer_protected": "🔒 بعد از خرید فقط قابل دیدنه (کپی، ذخیره و فوروارد ممکن نیست).",
        "offer_saveable": "📋 بعد از خرید قابل کپی و ذخیره‌ست.",
        "refund_already": "این خرید قبلاً بازپرداخت شده.",
        "refund_expired": "مهلت ۲۴ ساعته‌ی بازپرداخت تموم شده.",
        "refund_limit": "به سقف بازپرداخت رسیدی (۳ بار در ماه).",
        "refund_failed": "بازپرداخت انجام نشد. چند دقیقه بعد دوباره امتحان کن.",
        "refund_done": "✅ {amount} ⭐ به حسابت برگشت. محتوا از چت حذف شد.",
        "refund_seller": "↩️ یک خریدار {amount} ⭐ رو بازپرداخت گرفت.",
        "shop_suspended_buyer": "⛔️ فروش این فروشگاه فعلاً متوقف شده.",
        "shop_suspended_owner": "⛔️ فروشگاه @{bot} به‌خاطر نقض قوانین UploadFly تعلیق شد.\nفروش جدید ممکن نیست، ولی خریدارهای قبلی هنوز به محتوای خریده‌شده دسترسی دارن.",
        "shop_unsuspended": "✅ تعلیق فروشگاه @{bot} برداشته شد و دوباره می‌تونی بفروشی.",
        "shop_suspended_line": "⛔️ <b>این فروشگاه به‌خاطر نقض قوانین تعلیق شده.</b>",
        "btn_open_shop": "🏪 فروشگاه من (فروش با استارز)",
        "shop_none": "🏪 <b>فروشگاه من</b>\n\n"
                     "هنوز فروشگاه نداری. با فروشگاه می‌تونی فایل‌هات رو با استارز بفروشی و پولش مستقیم به خودت برسه.\n\n"
                     "ساختش ۲ دقیقه طول می‌کشه 👇",
        "btn_create_shop": "➕ ساخت فروشگاه",
        "shop_home": "🏪 <b>فروشگاه من</b> — @{bot}\n\n"
                     "💰 موجودی: <b>{balance} ⭐</b>\n"
                     "📅 فروش امروز: {today_n} عدد ({today_sum} ⭐)\n"
                     "🛒 کل فروش: {total_n} عدد ({total_sum} ⭐)\n"
                     "🔗 لینک‌های فعال: {links}\n\n"
                     "برای فروش محتوای جدید، روی «آپلود» بزن و فایل رو توی فروشگاهت بفرست.",
        "btn_upload": "📤 آپلود محتوای جدید برای فروش",
        "btn_sales": "🛒 فروش‌ها",
        "btn_links": "🔗 لینک‌های فروش",
        "btn_withdraw": "💸 برداشت پول",
        "btn_refresh": "🔄 به‌روزرسانی",
        "btn_disconnect": "⛔️ قطع اتصال فروشگاه",
        "btn_disconnect_yes": "بله، قطع کن",
        "btn_back": "« برگشت",
        "sales_empty": "هنوز فروشی نداشتی. لینک‌های فروشت رو در کانال‌ها و گروه‌هات به اشتراک بذار.",
        "sales_header": "🛒 <b>آخرین فروش‌ها</b>\n",
        "refunded": "برگشت داده شد",
        "shop_links_empty": "هنوز لینک فروشی نساختی. یه فایل توی @{bot} بفرست.",
        "withdraw_not_yet": "💸 <b>برداشت پول</b>\n\n"
                            "موجودی فعلی: <b>{balance} ⭐</b>\n"
                            "تلگرام از <b>{min} ⭐</b> به بالا اجازه‌ی برداشت می‌ده. {left} ⭐ دیگه مونده.\n\n"
                            "نگران نباش، استارزت امنه و در موجودی فروشگاهت جمع می‌شه. "
                            "وقتی به حداقل رسیدی، همین‌جا قدم‌به‌قدم راهنمات می‌کنیم.",
        "sc_free": "🆓 ویترین رایگان",
        "sc_once": "🔑 ورود یک‌باره: {price} ⭐ (دسترسی همیشگی)",
        "sc_monthly": "🔁 اشتراک ماهانه: {price} ⭐",
        "btn_open_showcase": "🛍 مشاهده‌ی ویترین",
        "sc_closed_refunded": "ویترین «{title}» دیگه فعال نیست، برای همین {price}⭐ پرداختت برگشت داده شد و تمدیدش هم خاموش شد.",
        "sc_joined": "🎉 به ویترین «{title}» خوش اومدی! حالا همه‌ی محتواهای ویژه‌ی اعضا برات بازه.",
        "sc_renewed": "🔁 اشتراک ویترین «{title}» برای یک ماه دیگر تمدید شد.",
        "sc_new_member": "🎉 عضو تازه در ویترین «{title}»: {price} ⭐\nمستقیم به موجودی همین ربات (مال خودت) اضافه شد.",
        "sc_member_renewed": "🔁 یک عضو اشتراک «{title}» را تمدید کرد: {price} ⭐",
        "sc_invoice_desc": "دسترسی به محتواهای ویترین «{title}»",
        "sc_invoice_label": "ورود به ویترین",
        "sc_refund_opened": "یکی از محتواهای این ویترین را باز کرده‌ای، پس بازپرداخت ورودی ممکن نیست.",
        "rate_hint": "⭐ از این محتوا راضی بودی؟ با یک ضربه امتیاز بده (به بقیه‌ی خریدارها کمک می‌کند):",
        "rate_thanks": "ممنون! امتیازت ثبت شد ({n} ⭐)",
        "rate_not_allowed": "فقط بعد از خرید و دیدن محتوا می‌شود امتیاز داد.",
        "sc_sub_renews": "🔁 اشتراک «{title}» در {date} با {price} ⭐ خودکار تمدید می‌شود. اگر موجودی استارزت کم است، شارژش کن تا قطع نشود.",
        "sc_sub_ending": "⏳ اشتراک «{title}» تا {date} فعال است و تمدید نمی‌شود. برای ادامه، دوباره عضو شو.",
        "sc_sub_ended": "⌛️ اشتراک «{title}» تمام شد. هر وقت خواستی دوباره عضو شو.",
        "btn_rejoin": "🔁 عضویت دوباره",
        "premium_gift_text": "🎉 از درآمد فروشگاهت در UploadFly",
        "withdraw_steps": "💸 <b>برداشت پول در ۳ قدم</b>\n\n"
                          "۱. یک کیف پول TON بساز (مثلاً اپ Tonkeeper). برداشت تلگرام فقط به صورت TON انجام می‌شه.\n"
                          "۲. در اپ تلگرام پروفایل @{bot} رو باز کن ← Edit ← Balance ← Withdraw.\n"
                          "۳. در سایت Fragment که باز می‌شه، کیف پولت رو وصل کن و برداشت رو تأیید کن.\n\n"
                          "ℹ️ حداقل برداشت {min} ⭐ است و هر فروش حدود ۲۱ روز بعد قابل برداشت می‌شه (قانون تلگرام). "
                          "تبدیل TON به پول نقد رو در صرافی دلخواهت انجام بده.",
        "disconnect_confirm": "⚠️ مطمئنی؟ با قطع اتصال، لینک‌های فروش @{bot} دیگه کار نمی‌کنن تا دوباره وصلش کنی. "
                              "موجودی استارزت سر جاشه و از بین نمی‌ره.",
        # --- اتصال ربات فروشنده ---
        "connect_howto": "💰 <b>فروش با استارز</b>\n\n"
                         "استارزِ فروش مستقیم به <b>ربات خودت</b> می‌ره، نه به UploadFly.\n\n"
                         "۱. به @BotFather برو و /newbot بزن.\n"
                         "۲. یک اسم و یک یوزرنیم (که به bot ختم بشه) بده.\n"
                         "۳. توکنی که بهت می‌ده رو کپی کن و همین‌جا بفرست.\n\n"
                         "🔒 پیامت فوراً پاک می‌شه و توکن رمزنگاری‌شده ذخیره می‌شه.\n"
                         "⚠️ این ربات نباید جای دیگه‌ای اجرا بشه.\n\n"
                         "برای لغو: /cancel",
        "connect_quick": "🏪 <b>ساخت فروشگاه</b>\n\n"
                         "دکمه‌ی زیر رو بزن؛ خود تلگرام ربات فروشگاهت رو می‌سازه. فقط یه اسم بنویس و <b>Create</b> رو بزن.\n\n"
                         "👤 مالک ربات خودتی و استارزِ فروش مستقیم به خودت می‌رسه.\n\n"
                         "<i>از قبل ربات داری؟ توکنش رو از @BotFather کپی کن و همین‌جا بفرست.</i>",
        "btn_create_bot": "⚡️ ساخت فروشگاه با یک ضربه",
        "already_has_shop": "تو از قبل یک فروشگاه فعال داری. ربات @{bot} ساخته شد ولی وصل نشد؛ "
                            "اگه می‌خوای این یکی فروشگاهت باشه، اول فروشگاه فعلی رو از «🏪 فروشگاه من» قطع کن و دوباره بساز.",
        "managed_connected": "🎉 <b>فروشگاه @{bot} ساخته و وصل شد!</b>\n\n"
                             "حالا اولین محصولت رو توی @{bot} بفرست (یا از کانالت فوروارد کن). "
                             "قیمت و ویژگی‌هاش رو توی Mini App تنظیم می‌کنی.",
        "btn_upload_first": "📤 آپلود اولین محصول",
        "btn_open_store": "🛍 ویترین فروشگاه",
        "link_elsewhere": "🔗 این لینک مال @{bot} است. برای باز کردنش دکمه‌ی زیر رو بزن.",
        "btn_open_link": "باز کردن لینک ↗️",
        "price_cap_hint": "سقف قیمت فعلی فروشگاهت {cap} ⭐ است و با فروش‌های موفق بالاتر می‌ره.",
        "file_blacklisted": "⛔️ این فایل به‌خاطر تخلف قبلاً مسدود شده و قابل آپلود نیست.",
        "takedown_admin": "⛔️ یکی از محصولاتت به‌خاطر نقض قوانین UploadFly حذف و مسدود شد.",
        "admin_forbidden_report": "🚨 <b>گزارش محتوای ممنوع</b>\nفروشگاه: @{bot} (مالک {owner})\nمحصول: {link}\n\nبررسی کن؛ برای حذف: /takedown {link}",
        "sell_hint": "💡 این یه لینک <b>رایگانه</b>. برای <b>فروش</b>، فایل رو توی فروشگاهت (@{bot}) بفرست.",
        "btn_sell_in_shop": "💰 فروش این فایل در فروشگاهم",
        "upload_prompt": "📤 <b>فایلی که می‌خوای بفروشی رو همین‌جا بفرست</b>\n\n"
                         "عکس، ویدیو، موزیک، PDF، هر فایلی تا ۲ گیگ، یا حتی یه متن. می‌تونی از کانالت هم فوروارد کنی.\n"
                         "بعدش قیمت و ویژگی‌هاش رو توی Mini App تنظیم می‌کنی.",
        "btn_more_from_shop": "🛍 محصولات دیگه‌ی این فروشگاه",
        "btn_pay": "پرداخت {price} ⭐",
        "seller_says": "📝 <b>توضیح فروشنده:</b>\n{text}",
        "btn_open_dashboard": "📊 داشبورد فروشگاه",
        "shop_short_description": "🛍 فروشگاه فایل با استارز — ساخته‌شده با @{main}",
        "shop_description": "🛍 به این فروشگاه خوش اومدی!\n\n"
                            "روی لینک محصولی که بهت دادن بزن تا پیش‌نمایش، مشخصات و قیمتش رو ببینی و با استارز بخری. "
                            "تا قبل از دیدن محتوا، بازپرداخت کامل ممکنه.\n\n⚡️ ساخته‌شده با @{main}",
        "cancelled": "لغو شد.",
        "bad_token": "❌ این توکن معتبر نیست. دوباره از @BotFather کپی کن و بفرست، یا /cancel بزن.",
        "bot_taken": "❌ این ربات قبلاً توسط کاربر دیگه‌ای وصل شده.",
        "connected": "✅ ربات @{bot} وصل شد!\n\n"
                     "حالا برو توی @{bot}، /start بزن و محتوایی که می‌خوای بفروشی رو همون‌جا آپلود کن.\n"
                     "استارزِ فروش به موجودی همون ربات می‌ره و از طریق @BotFather (بخش Balance) برداشت می‌کنی.",
        "already_connected": "ربات @{bot} الان وصله. برای قطع اتصال: /disconnect",
        "not_connected": "هیچ رباتی وصل نیست. برای وصل کردن: /connect",
        "disconnected": "ربات @{bot} قطع شد. لینک‌های فروشش دیگه کار نمی‌کنن تا دوباره /connect کنی.",
        "seller_revoked": "⚠️ توکن ربات @{bot} عوض شده یا ربات حذف شده، پس اتصالش قطع شد. برای وصل کردن دوباره: /connect",
        # --- ربات فروشنده ---
        "seller_welcome_owner": "سلام {name} 👋\n\nاین فروشگاه خودته.\n"
                                "هر محتوایی بفرستی، قیمتش رو انتخاب می‌کنی و لینک فروش می‌گیری.\n"
                                "/mylinks : لینک‌های تو\n"
                                "/balance : موجودی استارز",
        "seller_welcome_buyer": "سلام {name} 👋\n\nهمه‌ی محصولات این فروشگاه رو توی ویترین ببین، یا روی لینکی که بهت دادن بزن.\n\n"
                                "⚡️ ساخته‌شده با @{main}",
        "seller_help": "📌 <b>راهنما</b>\n\n"
                       "محتوا بفرست، قیمت رو انتخاب کن، لینک فروش بگیر. خریدار با استارز پرداخت می‌کنه و محتوا رو بدون امکان فوروارد می‌گیره.\n\n"
                       "<b>دستورها</b>\n"
                       "/mylinks — لینک‌های من\n"
                       "/balance — موجودی استارز و برداشت\n"
                       "/lang — تغییر زبان\n"
                       "/help — همین راهنما",
        "seller_only_owner": "فقط صاحب این ربات می‌تونه محتوا آپلود کنه. برای دریافت محتوا روی لینکش بزن.",
        "owner_only": "این بخش فقط برای صاحب این ربات است.",
        "auto_delete_notice": "⏳ این محتوا {time} دیگه خودکار پاک می‌شه. هر وقت خواستی دوباره روی همون لینک بزن (بدون پرداخت دوباره).",
        "btn_sensitive_off": "⏳ حساس و زودگذر: خاموش",
        "btn_sensitive_on": "⏳ حساس و زودگذر: روشن ✅",
        "sensitive_label": "⏳ حساس و زودگذر (بعد از دیده شدن خودکار پاک می‌شه)",
        "choose_price": "{specs}\n\n💰 قیمت این محتوا رو انتخاب کن:\n"
                        "⏳ «حساس و زودگذر» یعنی بعد از دیده شدن خودکار پاک بشه؛ برای محتوای خصوصی، اسپویلر، "
                        "محرمانه یا بزرگسال. محتوای بزرگسالِ بدون این علامت باعث مسدود شدن می‌شه.",
        "ask_price": "قیمت رو به عدد بفرست (۱ تا {max} استارز):",
        "btn_free": "🎁 رایگان",
        "btn_custom_price": "✏️ قیمت دلخواه",
        "price": "قیمت",
        "price_free": "رایگان",
        # --- خرید ---
        "offer": "🔒 <b>محتوای پولی</b>\n\n{specs}\n\n💰 قیمت: {price} ⭐\n"
                 "مشخصات بالا رو خود سیستم از فایل خونده، نه فروشنده.",
        "invoice_title": "خرید {kind}",
        "invoice_label": "قیمت",
        "pay_unavailable": "این محتوا دیگه برای فروش نیست یا قیمتش عوض شده.",
        "paid": "✅ پرداخت انجام شد. محتوا:",
        "powered_by": "⚡️ تو هم می‌خوای فایل بفروشی؟ @{main}",
        "sold": "💰 فروش جدید! {kind} به قیمت {price} ⭐\nمستقیم به موجودی همین ربات (مال خودت) اضافه شد.",
        "first_sale": "🎉 <b>اولین فروشت!</b> {kind} به قیمت {price} ⭐\n\nاین استارزها مستقیم در موجودی همین ربات نشستند؛ ربات مال خودِ توست و UploadFly به آن دسترسی ندارد.\n\n👀 <b>خودت در تلگرام ببین:</b> پروفایل همین ربات را باز کن ← Edit (مداد) ← Balance.\nطبق قانون تلگرام، هر فروش حدود ۲۱ روز بعد قابل برداشت می‌شود و برداشت از ۱۰۰۰ ⭐ شروع می‌شود.",
        "balance": "💰 <b>موجودی ربات:</b> {stars} ⭐\n"
                   "🛒 فروش‌ها: {sales} عدد، جمعاً {total} ⭐\n\n"
                   "<b>برداشت:</b> استارز فقط از طریق Fragment و به صورت TON (ارز دیجیتال) برداشت می‌شه. "
                   "در اپ تلگرام پروفایل همین ربات رو باز کن ← Edit ← Balance. "
                   "استارز معمولاً بعد از ۲۱ روز قابل برداشت می‌شه و حداقل مبلغ برداشت داره.",
    },
    "en": {
        "welcome": "Hi {name} 👋\n\nWelcome to <b>UploadFly</b>.\n"
                   "Send me anything (file, photo, video, music, voice or even text) and I'll create a unique link for it.\n\n"
                   "Anyone who opens the link receives the content.\n\n"
                   "🌐 فارسی: /lang",
        "paysupport": "🛟 <b>Payment support</b>\n\nThis shop belongs to {shop}. The Stars you pay go straight to the seller's own bot, not to UploadFly.\n\n• <b>Haven't opened the content yet?</b> Within 24 hours of buying, the “Refund” button under the purchase message returns all your Stars.\n• <b>Content broken or not as described?</b> Tap “Report a problem” under the content; UploadFly admins will review it.\n• <b>Monthly membership:</b> turn off auto-renewal any time on the showcase page.{contact}\n\nTerms: /terms",
        "paysupport_contact": "\n• <b>Other questions?</b> Message the seller: @{user}",
        "paysupport_main": "🛟 <b>Payment support</b>\n\nPurchases happen inside each shop's own bot and the Stars go straight to that bot. For a refund or a problem with a purchase, open that shop's bot and send /paysupport there.\n\nTerms: /terms",
        "terms": "📜 <b>UploadFly terms</b>\n\n1. UploadFly is a tool for links and shops. Each shop is the seller's own bot, and the seller is responsible for its content.\n2. Payments are in Telegram Stars and go straight to the seller's bot; UploadFly never receives or holds money.\n3. Refunds only before opening the content and within 24 hours of buying, at most 3 times in 30 days. Showcase entry: until any of its content is opened. A cancelled monthly membership stays active until the period ends.\n4. Forbidden: weapons, drugs, human trafficking, scams and <b>any sexual content involving minors</b> (permanent ban). Adult content only in seller bots and marked “sensitive”.\n5. Purchased content is protected and for your personal use only.\n6. Admins may remove content that breaks these rules and suspend shops or users.\n7. Telegram's Stars terms also apply: telegram.org/tos/stars",
        "stars_guide": "⭐ <b>Where to get Stars?</b>\n\nStars are Telegram's official currency, and they go straight to the seller.\n\n1. <b>Inside Telegram:</b> Settings → My Stars → Buy.\n2. <b>Resellers:</b> some sites sell Stars for local currency and only need your username ({user}). Pick one with real reviews.\n\n⚠️ Never share your Telegram login code or password.\n\nAfter buying, tap the pay button again.",
        "stars_offer_hint": "⭐ No Stars? /stars",
        "stars_no_user": "(set a username in Telegram settings first)",
        "paysupport_escalate": "\n\n🎧 Still stuck? Send /support to @{main}.",
        "support_text": "🎧 <b>UploadFly support</b>\n\nMost answers are in the FAQ. If yours isn't there, message support directly.{email}\n\nYour user ID: <code>{id}</code> (send it to support so we can help faster)",
        "support_email_line": "\n✉️ Email: {email}",
        "btn_support_faq": "❓ FAQ",
        "btn_support_chat": "💬 Chat with support",
        "help": "📌 <b>Help</b>\n\n"
                "Send any file, photo, video, music or text and you get a link.\n\n"
                "<b>Commands</b>\n"
                "/mylinks — my links\n"
                "/shop — my shop (sell for Stars)\n"
                "/lang — change language\n"
                "/help — this help\n\n"
                "📱 Manage products, stats and your shop window from the UploadFly button next to the message box.\n\n"
                "⚠️ Weapons, drugs, human trafficking, scams and any sexual content involving minors are forbidden and get your account banned.\n"
                "🔞 Adult content only in a personal shop bot, marked \"Sensitive & disappearing\".",
        "link_created": "✅ <b>Link created</b>\n\n{specs}\n\n🔗 <code>{link}</code>",
        "unsupported": "This message type isn't supported yet. Send a file, photo, video, music, voice or text.",
        "not_found": "❌ This link doesn't exist or has been disabled.",
        "unknown_command": "Unknown command. Try /help.",
        "mylinks_empty": "You haven't created any links yet. Send me a file or text.",
        "mylinks_header": "🗂 <b>Your recent links</b>\n",
        "views": "views",
        "btn_copy": "📋 Copy link",
        "btn_share": "📤 Share",
        "kinds": {"text": "Text", "photo": "Photo", "video": "Video", "animation": "GIF",
                  "document": "File", "audio": "Music", "voice": "Voice", "video_note": "Video note"},
        "spec_type": "Type", "spec_size": "Size", "spec_duration": "Duration",
        "spec_resolution": "Resolution", "spec_name": "File name", "spec_words": "Words", "spec_pages": "Pages",
        "preview_caption_buyer": "👀 Automatic preview (made by the system, not the seller)",
        "preview_caption_seller": "👀 This is the preview buyers see before buying. It's made automatically and can't be changed.",
        "preview_building": "⏳ Building the automatic preview...",
        "preview_text": "👀 <b>Beginning of the text:</b>\n<blockquote>{snippet}</blockquote>",
        "preview_thumb_only": "ℹ️ The file is larger than 20 MB, so only Telegram's small thumbnail is shown as a preview.",
        "lang_choose": "🌐 Choose your language / زبان را انتخاب کن:",
        "lang_set": "✅ Language set to English.",
        "time_h": "{h} h", "time_m": "{m} min", "time_join": " ",
        "btn_refund": "↩️ Refund",
        "btn_open": "👁 Show content",
        "received": "✅ <b>Received</b>\n\n{specs}\n\nSet the price and options to publish it 👇",
        "btn_setup_product": "⚙️ Set up & publish",
        "btn_price_in_chat": "💬 Quick pricing here",
        "paid_pending": "✅ Payment received.\n\n"
                        "👁 Tap \"Show\" to see the content.\n"
                        "↩️ Changed your mind? Within 24 hours and <b>before showing</b> it, you can get your Stars back in full. "
                        "After showing, no refund is possible.",
        "paid_opened": "✅ Payment received. Your content:",
        "refund_opened": "You've already seen the content, so no refund. If it didn't match the description, tap \"Report a problem\".",
        "report_offer": "If the content didn't match the seller's specs or description, or had a problem, report it for review.",
        "btn_report": "🚩 Report a problem",
        "report_choose": "🚩 What was wrong?",
        "reason_mismatch": "Didn't match the description",
        "reason_broken": "Broken or incomplete file",
        "reason_forbidden": "Forbidden content",
        "reason_other": "Something else",
        "report_already": "You've already reported this purchase.",
        "report_expired": "The report window (7 days after viewing) has ended.",
        "report_done": "🚩 Report received and will be reviewed. Thanks for helping keep UploadFly safe.",
        "report_seller": "🚩 A buyer reported one of your sales ({reason}). Reports are reviewed by UploadFly.",
        "btn_save_off": "📋 Allow copy & save: off",
        "btn_save_on": "📋 Allow copy & save: on ✅",
        "save_label": "📋 Buyers can copy and save it",
        "save_not_sensitive": "Sensitive content is always protected and can't be copied.",
        "offer_protected": "🔒 View only after purchase (no copy, save or forward).",
        "offer_saveable": "📋 Can be copied and saved after purchase.",
        "refund_already": "This purchase was already refunded.",
        "refund_expired": "The 24-hour refund window has ended.",
        "refund_limit": "You've reached the refund limit (3 per month).",
        "refund_failed": "The refund didn't go through. Try again in a few minutes.",
        "refund_done": "✅ {amount} ⭐ returned to you. The content was removed from the chat.",
        "refund_seller": "↩️ A buyer was refunded {amount} ⭐.",
        "shop_suspended_buyer": "⛔️ This shop's sales are paused for now.",
        "shop_suspended_owner": "⛔️ Shop @{bot} was suspended for breaking UploadFly's rules.\nNo new sales are possible, but previous buyers keep access to what they bought.",
        "shop_unsuspended": "✅ Shop @{bot} is no longer suspended; you can sell again.",
        "shop_suspended_line": "⛔️ <b>This shop is suspended for breaking the rules.</b>",
        "btn_open_shop": "🏪 My shop (sell for Stars)",
        "shop_none": "🏪 <b>My shop</b>\n\n"
                     "You don't have a shop yet. With a shop you can sell your files for Stars, paid straight to you.\n\n"
                     "It takes 2 minutes 👇",
        "btn_create_shop": "➕ Create shop",
        "shop_home": "🏪 <b>My shop</b> — @{bot}\n\n"
                     "💰 Balance: <b>{balance} ⭐</b>\n"
                     "📅 Sales today: {today_n} ({today_sum} ⭐)\n"
                     "🛒 All sales: {total_n} ({total_sum} ⭐)\n"
                     "🔗 Active links: {links}\n\n"
                     "To sell something new, tap \"Upload\" and send the file in your shop.",
        "btn_upload": "📤 Upload new content to sell",
        "btn_sales": "🛒 Sales",
        "btn_links": "🔗 Sales links",
        "btn_withdraw": "💸 Withdraw",
        "btn_refresh": "🔄 Refresh",
        "btn_disconnect": "⛔️ Disconnect shop",
        "btn_disconnect_yes": "Yes, disconnect",
        "btn_back": "« Back",
        "sales_empty": "No sales yet. Share your sales links in your channels and groups.",
        "sales_header": "🛒 <b>Latest sales</b>\n",
        "refunded": "refunded",
        "shop_links_empty": "No sales links yet. Send a file in @{bot}.",
        "withdraw_not_yet": "💸 <b>Withdraw</b>\n\n"
                            "Current balance: <b>{balance} ⭐</b>\n"
                            "Telegram allows withdrawals from <b>{min} ⭐</b>. {left} ⭐ to go.\n\n"
                            "Your Stars are safe and keep adding up in your shop's balance. "
                            "Once you reach the minimum, we'll guide you step by step right here.",
        "sc_free": "🆓 Free showcase",
        "sc_once": "🔑 One-time entry: {price} ⭐ (lifetime access)",
        "sc_monthly": "🔁 Monthly subscription: {price} ⭐",
        "btn_open_showcase": "🛍 Open showcase",
        "sc_closed_refunded": "The showcase “{title}” is no longer active, so your {price}⭐ payment was refunded and its renewal turned off.",
        "sc_joined": "🎉 Welcome to “{title}”! All member content is now unlocked for you.",
        "sc_renewed": "🔁 Your “{title}” subscription was renewed for another month.",
        "sc_new_member": "🎉 New member in “{title}”: {price} ⭐\nAdded straight to this bot's balance (yours).",
        "sc_member_renewed": "🔁 A member renewed “{title}”: {price} ⭐",
        "sc_invoice_desc": "Access to the “{title}” showcase",
        "sc_invoice_label": "Showcase access",
        "sc_refund_opened": "You've opened content from this showcase, so the entry can't be refunded.",
        "rate_hint": "⭐ Happy with it? Rate it in one tap (it helps other buyers):",
        "rate_thanks": "Thanks! Your rating was saved ({n} ⭐)",
        "rate_not_allowed": "You can rate only after buying and viewing the content.",
        "sc_sub_renews": "🔁 Your “{title}” subscription renews on {date} for {price} ⭐. Top up your Stars if needed so it doesn't stop.",
        "sc_sub_ending": "⏳ Your “{title}” subscription is active until {date} and won't renew. Join again to keep access.",
        "sc_sub_ended": "⌛️ Your “{title}” subscription has ended. Join again any time.",
        "btn_rejoin": "🔁 Join again",
        "premium_gift_text": "🎉 From your UploadFly shop earnings",
        "withdraw_steps": "💸 <b>Withdraw in 3 steps</b>\n\n"
                          "1. Create a TON wallet (e.g. the Tonkeeper app). Telegram pays out only in TON.\n"
                          "2. In the Telegram app open @{bot}'s profile → Edit → Balance → Withdraw.\n"
                          "3. On the Fragment page that opens, connect your wallet and confirm.\n\n"
                          "ℹ️ Minimum is {min} ⭐ and each sale becomes withdrawable about 21 days later (Telegram rule). "
                          "Convert TON to cash at an exchange of your choice.",
        "disconnect_confirm": "⚠️ Are you sure? @{bot}'s sales links stop working until you reconnect. "
                              "Your Stars balance stays where it is.",
        # --- seller bot connection ---
        "connect_howto": "💰 <b>Sell for Stars</b>\n\n"
                         "Sales go straight to <b>your own bot</b>, not to UploadFly.\n\n"
                         "1. Open @BotFather and send /newbot.\n"
                         "2. Pick a name and a username (ending in bot).\n"
                         "3. Copy the token it gives you and send it here.\n\n"
                         "🔒 Your message is deleted right away and the token is stored encrypted.\n"
                         "⚠️ This bot must not run anywhere else.\n\n"
                         "To cancel: /cancel",
        "connect_quick": "🏪 <b>Create your shop</b>\n\n"
                         "Tap the button below and Telegram creates your shop bot. Just type a name and tap <b>Create</b>.\n\n"
                         "👤 You own the bot, and sales Stars go straight to you.\n\n"
                         "<i>Already have a bot? Copy its token from @BotFather and send it here.</i>",
        "btn_create_bot": "⚡️ Create shop in one tap",
        "already_has_shop": "You already have an active shop. @{bot} was created but not connected; "
                            "to use it as your shop, disconnect the current one in \"🏪 My shop\" and create again.",
        "managed_connected": "🎉 <b>Shop @{bot} is created and connected!</b>\n\n"
                             "Now send your first product to @{bot} (or forward it from your channel). "
                             "You set its price and options in the Mini App.",
        "btn_upload_first": "📤 Upload your first product",
        "btn_open_store": "🛍 Shop window",
        "link_elsewhere": "🔗 This link belongs to @{bot}. Tap the button below to open it.",
        "btn_open_link": "Open link ↗️",
        "price_cap_hint": "Your shop's current price cap is {cap} ⭐ and rises with successful sales.",
        "file_blacklisted": "⛔️ This file was blocked for a violation and can't be uploaded.",
        "takedown_admin": "⛔️ One of your products was removed and blocked for breaking UploadFly's rules.",
        "admin_forbidden_report": "🚨 <b>Forbidden content report</b>\nShop: @{bot} (owner {owner})\nProduct: {link}\n\nReview it; to remove: /takedown {link}",
        "sell_hint": "💡 This is a <b>free</b> link. To <b>sell</b> it, send the file to your shop (@{bot}).",
        "btn_sell_in_shop": "💰 Sell this file in my shop",
        "upload_prompt": "📤 <b>Send the file you want to sell right here</b>\n\n"
                         "Photo, video, music, PDF, any file up to 2 GB, or even text. You can also forward it from your channel.\n"
                         "Then you set its price and options in the Mini App.",
        "btn_more_from_shop": "🛍 More from this shop",
        "btn_pay": "Pay {price} ⭐",
        "seller_says": "📝 <b>Seller's description:</b>\n{text}",
        "btn_open_dashboard": "📊 Shop dashboard",
        "shop_short_description": "🛍 File shop with Stars — made with @{main}",
        "shop_description": "🛍 Welcome to this shop!\n\n"
                            "Open the product link you were given to see its preview, specs and price, and buy with Stars. "
                            "Full refund is possible until you view the content.\n\n⚡️ Made with @{main}",
        "cancelled": "Cancelled.",
        "bad_token": "❌ This token isn't valid. Copy it again from @BotFather and send it, or /cancel.",
        "bot_taken": "❌ This bot is already connected by another user.",
        "connected": "✅ @{bot} is connected!\n\n"
                     "Now open @{bot}, press /start and upload what you want to sell there.\n"
                     "Stars go to that bot's balance; withdraw them via @BotFather (Balance).",
        "already_connected": "@{bot} is already connected. To disconnect: /disconnect",
        "not_connected": "No bot is connected. To connect one: /connect",
        "disconnected": "@{bot} disconnected. Its paid links stop working until you /connect again.",
        "seller_revoked": "⚠️ The token of @{bot} was changed or the bot was deleted, so it was disconnected. To reconnect: /connect",
        # --- seller bot ---
        "seller_welcome_owner": "Hi {name} 👋\n\nThis is your shop.\n"
                                "Send any content, pick a price and get a sales link.\n"
                                "/mylinks : your links\n"
                                "/balance : Stars balance",
        "seller_welcome_buyer": "Hi {name} 👋\n\nBrowse all products in the shop window, or open the link you were given.\n\n"
                                "⚡️ Made with @{main}",
        "seller_help": "📌 <b>Help</b>\n\n"
                       "Send content, pick a price, get a sales link. Buyers pay with Stars and get the content without forwarding.\n\n"
                       "<b>Commands</b>\n"
                       "/mylinks — my links\n"
                       "/balance — Stars balance and withdrawal\n"
                       "/lang — change language\n"
                       "/help — this help",
        "seller_only_owner": "Only this bot's owner can upload content. Open a link to get content.",
        "owner_only": "This section is only for the owner of this bot.",
        "auto_delete_notice": "⏳ This content will be deleted automatically in {time}. Open the same link again any time (no extra payment).",
        "btn_sensitive_off": "⏳ Sensitive & disappearing: off",
        "btn_sensitive_on": "⏳ Sensitive & disappearing: on ✅",
        "sensitive_label": "⏳ Sensitive & disappearing (auto-deleted after viewing)",
        "choose_price": "{specs}\n\n💰 Choose a price for this content:\n"
                        "⏳ \"Sensitive & disappearing\" deletes it after viewing; for private, spoiler, "
                        "confidential or adult content. Unmarked adult content gets you banned.",
        "ask_price": "Send the price as a number (1 to {max} Stars):",
        "btn_free": "🎁 Free",
        "btn_custom_price": "✏️ Custom price",
        "price": "Price",
        "price_free": "Free",
        # --- purchase ---
        "offer": "🔒 <b>Paid content</b>\n\n{specs}\n\n💰 Price: {price} ⭐\n"
                 "The specs above were read from the file by the system, not claimed by the seller.",
        "invoice_title": "Buy {kind}",
        "invoice_label": "Price",
        "pay_unavailable": "This content is no longer for sale or its price changed.",
        "paid": "✅ Payment received. Your content:",
        "powered_by": "⚡️ Want to sell your own files? @{main}",
        "sold": "💰 New sale! {kind} for {price} ⭐\nAdded straight to this bot's balance (yours).",
        "first_sale": "🎉 <b>Your first sale!</b> {kind} for {price} ⭐\n\nThese Stars landed directly in this bot's balance; the bot is yours and UploadFly has no access to it.\n\n👀 <b>Check it yourself in Telegram:</b> open this bot's profile → Edit (pencil) → Balance.\nUnder Telegram's rules, each sale becomes withdrawable about 21 days later, and withdrawals start at 1000 ⭐.",
        "balance": "💰 <b>Bot balance:</b> {stars} ⭐\n"
                   "🛒 Sales: {sales}, total {total} ⭐\n\n"
                   "<b>Withdraw:</b> Stars are withdrawn only via Fragment, as TON (crypto). "
                   "In the Telegram app open this bot's profile → Edit → Balance. "
                   "Stars usually become withdrawable after 21 days and there is a minimum amount.",
    },
}


# روسی، عربی و چینی: هر زبان یک فایل در app/i18n (فارسی و انگلیسی همین بالا)
for _file in sorted((Path(__file__).parent / "i18n").glob("*.json")):
    TEXTS[_file.stem] = json.loads(_file.read_text(encoding="utf-8"))

# متن‌های صفحه‌ی سازنده (دونیت، پیام خصوصی، پیام گروهی…) و خوش‌آمد/راهنمای تازه
from app.texts_creator import CREATOR_TEXTS  # noqa: E402
for _lang, _texts in CREATOR_TEXTS.items():
    TEXTS.setdefault(_lang, {}).update(_texts)

# اگر کلیدی در ترجمه‌ای جا افتاده باشد، متن انگلیسی نشان داده می‌شود (نه خطا)
_MERGED = {lang: {**TEXTS["en"], **texts} for lang, texts in TEXTS.items()}


def T(lang: str) -> dict:
    return _MERGED.get(lang, _MERGED["en"])


# زبان‌های Mini App (متن‌های ربات فعلاً فقط fa/en؛ بقیه انگلیسی می‌بینند تا ترجمه شوند)
LANGUAGES = ("fa", "en", "ru", "ar", "zh")


# منوی دستورها (دکمه‌ی «/» در تلگرام) به هر ۵ زبان
COMMANDS = {
    "fa": {"donate": "دونیت به سازنده", "support": "پشتیبانی", "paysupport": "پشتیبانی پرداخت", "mylinks": "لینک‌های من", "shop": "فروشگاه من", "balance": "موجودی استارز", "lang": "زبان", "help": "راهنما"},
    "en": {"donate": "Donate to the creator", "support": "Support", "paysupport": "Payment support", "mylinks": "My links", "shop": "My shop", "balance": "Stars balance", "lang": "Language", "help": "Help"},
    "ru": {"donate": "Донат автору", "support": "Поддержка", "paysupport": "Поддержка оплаты", "mylinks": "Мои ссылки", "shop": "Мой магазин", "balance": "Баланс Stars", "lang": "Язык", "help": "Помощь"},
    "ar": {"donate": "تبرّع للصانع", "support": "الدعم", "paysupport": "دعم الدفع", "mylinks": "روابطي", "shop": "متجري", "balance": "رصيد Stars", "lang": "اللغة", "help": "المساعدة"},
    "zh": {"donate": "打赏创作者", "support": "客服", "paysupport": "支付支持", "mylinks": "我的链接", "shop": "我的店铺", "balance": "Stars 余额", "lang": "语言", "help": "帮助"},
}
MAIN_COMMANDS = ("mylinks", "shop", "support", "lang", "help")
SELLER_COMMANDS = ("donate", "mylinks", "balance", "lang", "help", "paysupport")
# زبان تلگرام → منوی پیش‌فرض. انگلیسی عمداً نیست: تلگرام انگلیسی ایرانی‌ها منوی فارسی (پیش‌فرض) می‌گیرد
MENU_LANG_CODES = {"ru": "ru", "uk": "ru", "be": "ru", "kk": "ru", "ar": "ar", "zh": "zh"}


def detect_language(code: str | None) -> str:
    """زبان کاربر تازه از زبان تلگرامش. پیش‌فرض فارسی (بیشتر کاربران ایرانی تلگرام انگلیسی دارند)."""
    code = (code or "").lower()
    if code.startswith(("ru", "uk", "be", "kk")):
        return "ru"
    if code.startswith("ar"):
        return "ar"
    if code.startswith("zh"):
        return "zh"
    return "fa"


def human_size(n: int | None) -> str | None:
    if not n:
        return None
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def human_duration(s: int | None) -> str | None:
    if not s:
        return None
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def human_wait(seconds: int, lang: str) -> str:
    minutes = max(1, -(-seconds // 60))  # گرد کردن به بالا
    h, m = divmod(minutes, 60)
    t = T(lang)
    parts = ([t["time_h"].format(h=h)] if h else []) + ([t["time_m"].format(m=m)] if m or not h else [])
    return t["time_join"].join(parts)


def format_specs(c, lang: str) -> str:
    """مشخصات تأییدشده‌ی سیستم (از خود فایل، نه ادعای کاربر)."""
    t = T(lang)
    lines = [f"📦 {t['spec_type']}: {t['kinds'].get(c.kind, c.kind)}"]
    if c.file_name:
        lines.append(f"📄 {t['spec_name']}: {html.escape(c.file_name)}")
    if size := human_size(c.file_size):
        lines.append(f"💾 {t['spec_size']}: {size}")
    if dur := human_duration(c.duration):
        lines.append(f"⏱ {t['spec_duration']}: {dur}")
    if c.width and c.height:
        lines.append(f"🖼 {t['spec_resolution']}: {c.width}×{c.height}")
    if c.kind == "text" and c.text:
        words = len(html.unescape(re.sub(r"<[^>]+>", "", c.text)).split())
        lines.append(f"📝 {t['spec_words']}: {words}")
    if pages := (json.loads(c.preview).get("pages") if getattr(c, "preview", None) else None):
        lines.append(f"📑 {t['spec_pages']}: {pages}")
    return "\n".join(lines)
