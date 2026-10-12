"""متن‌های چت «صفحه‌ی سازنده» (دونیت، پیام خصوصی، پیام پولی، پیام گروهی، ۱۸+) به ۵ زبان.
در texts.py روی TEXTS ادغام می‌شود؛ خوش‌آمد و راهنما هم برای جهت تازه (سازنده‌ها) بازنویسی شده‌اند."""

CREATOR_TEXTS = {
    "fa": {
        "welcome": "سلام {name} 👋\n\nبه <b>UploadFly</b> خوش اومدی؛ صفحه‌ی سازنده‌ی تو داخل تلگرام.\n\n"
                   "⭐ <b>بفروش و درآمد داشته باش:</b> اشتراک ماهانه، پست قفل‌دار، دونیت و پیام پولی. استارزها مستقیم به ربات خودت می‌رسه و ما هیچ سهمی برنمی‌داریم.\n"
                   "🔗 <b>لینک رایگان:</b> هر فایل، عکس، ویدیو یا متنی بفرستی، لینک می‌گیری.\n\n"
                   "برای ساخت صفحه‌ات دکمه‌ی زیر یا UploadFly کنار جای تایپ رو بزن.\n\n🌐 English: /lang",
        "help": "📌 <b>راهنما</b>\n\n"
                "<b>سازنده‌ها:</b> با یک ضربه ربات اختصاصی‌ات ساخته می‌شه. اونجا پست می‌ذاری (رایگان، فقط مشترکین، یا قفل‌دار)، "
                "اشتراک ماهانه و دوره‌ی آزمایشی تعریف می‌کنی، دونیت می‌گیری و با فن‌ها چت می‌کنی بدون اینکه اکانت شخصیت لو بره.\n\n"
                "<b>دستورها</b>\n"
                "/shop — صفحه و فروشگاه من\n"
                "/mylinks — لینک‌های رایگان من\n"
                "/lang — تغییر زبان\n"
                "/support — پشتیبانی\n\n"
                "⚠️ سلاح، مواد مخدر، قاچاق انسان، کلاهبرداری و هر محتوای جنسی مربوط به زیر ۱۸ سال ممنوعه و حساب رو مسدود می‌کنه.\n"
                "🔞 محتوای بزرگسال فقط در ربات شخصی سازنده، با علامت «حساس»، و هرگز در صفحه‌ی کشف.",
        "seller_welcome_owner": "سلام {name} 👋\n\nاین ربات صفحه‌ی خودته.\n"
                                "• هر محتوایی بفرستی، پست می‌شه (قیمت رو انتخاب می‌کنی).\n"
                                "• پیام فن‌ها همین‌جا می‌رسه؛ روی پیامشون «پاسخ» بزن تا جوابت بهشون برسه. عکس یا ویدیو بفرستی، می‌تونی قفلش کنی (پیام پولی).\n"
                                "• /broadcast : پیام گروهی به فن‌ها\n"
                                "• /balance : موجودی استارز",
        "seller_welcome_buyer": "سلام {name} 👋\n\nپست‌ها و اشتراک این سازنده رو توی صفحه‌اش ببین. "
                                "برای پیام دادن به سازنده همین‌جا بنویس. برای دونیت: /donate\n\n⚡️ ساخته‌شده با @{main}",
        "seller_help": "📌 <b>راهنما</b>\n\n"
                       "<b>سازنده:</b> محتوا بفرست تا پست بشه. به پیام فن‌ها «پاسخ» بده. با /broadcast به همه پیام بده.\n"
                       "<b>فن:</b> صفحه رو ببین، مشترک شو، برای سازنده پیام بنویس یا با /donate دونیت بده.\n\n"
                       "<b>دستورها</b>\n"
                       "/donate — دونیت\n"
                       "/mylinks — لینک‌های من\n"
                       "/balance — موجودی استارز و برداشت\n"
                       "/lang — تغییر زبان\n"
                       "/help — همین راهنما",
        "tip_title": "دونیت ⭐",
        "tip_desc": "دونیت مستقیم به سازنده (همه‌اش به ربات خود سازنده می‌رسه)",
        "tip_owner_self": "دونیت رو فن‌ها به تو می‌دن 🙂 لینک صفحه‌ات رو پخش کن.",
        "tip_choose": "⭐ چقدر دونیت می‌کنی؟ همه‌اش مستقیم به سازنده می‌رسه.",
        "tip_thanks": "💛 {amount} استارز دونیت کردی. ممنون! سازنده باخبر شد.",
        "tip_owner": "💛 <b>دونیت تازه:</b> {amount} ⭐ از {name}\nمستقیم به موجودی ربات خودت اضافه شد.",
        "dm_off": "سازنده فعلاً پیام دریافت نمی‌کنه.",
        "dm_fans_only": "پیام دادن به این سازنده فقط برای مشترک‌ها و خریدارهاست. صفحه‌اش رو ببین:",
        "dm_slow": "پیام‌هات زیاد شد؛ کمی بعد دوباره بنویس.",
        "dm_from": "💬 <b>پیام از {name}</b> · خرج کل: {spent} ⭐\nبرای جواب، روی پیامش «پاسخ» (Reply) بزن.",
        "btn_dm_block": "🚫 مسدود",
        "btn_dm_unblock": "✅ رفع مسدودی",
        "dm_failed": "پیامت نرسید؛ کمی بعد دوباره امتحان کن.",
        "dm_sent": "✅ پیامت برای سازنده فرستاده شد. جوابش همین‌جا میاد.",
        "dm_blocked": "این فن مسدود شد؛ دیگه پیامش بهت نمی‌رسه.",
        "dm_unblocked": "مسدودی برداشته شد.",
        "dm_reply_failed": "به این فن نرسید (شاید ربات رو بلاک کرده).",
        "btn_ppv_free": "🎁 رایگان بفرست",
        "btn_cancel": "✖️ لغو",
        "canceled": "لغو شد.",
        "ppv_choose": "این رو چطور بفرستم؟ رایگان، یا قفل‌دار با قیمت (پیام پولی):",
        "ppv_intro": "🔒 سازنده یک محتوای ویژه برات فرستاده:",
        "ppv_sent": "✅ فرستاده شد.",
        "bc_limit": "امروز به سقف پیام گروهی رسیدی ({n} بار در ۲۴ ساعت). فردا دوباره امتحان کن؛ این سقف جلوی گزارش اسپم شدن رباتت رو می‌گیره.",
        "bc_choose": "📣 <b>پیام گروهی</b>\nبه کی بفرستم؟",
        "seg_all": "همه‌ی فن‌ها و دنبال‌کننده‌ها ({n})",
        "seg_subscribers": "مشترک‌های فعال ({n})",
        "seg_expired": "اشتراک تمام‌شده‌ها ({n})",
        "seg_buyers": "خریدارها و دونیت‌کننده‌ها ({n})",
        "bc_empty": "در این گروه هنوز کسی نیست.",
        "bc_send_now": "حالا پیامت رو بفرست (متن، عکس، ویدیو یا فایل). به {n} نفر می‌رسه، بی‌صدا.\nلغو: /cancel",
        "bc_confirm": "این پیام برای {n} نفر فرستاده بشه؟",
        "btn_bc_send": "📣 ارسال به {n} نفر",
        "bc_ppv_choose": "برای {n} نفر: رایگان بفرستم یا قفل‌دار (پیام پولی)؟",
        "bc_started": "📣 ارسال به {n} نفر شروع شد. وقتی تموم شد خبرت می‌کنم.",
        "bc_done": "📣 پیام گروهی تموم شد: به {sent} نفر از {total} نفر رسید.",
        "btn_see_post": "👀 دیدن پست",
        "new_post": "🆕 <b>{name}</b> یک پست تازه گذاشت\n{title}",
        "scheduled_live": "🗓 پست زمان‌بندی‌شده‌ات منتشر شد: {title}",
        "sc_bundle_title": "اشتراک {months} ماهه",
        "adult_confirm": "🔞 این محتوا فقط برای بزرگسالانه. تأیید می‌کنی که ۱۸ سال یا بیشتر داری؟",
        "btn_adult_yes": "بله، ۱۸+ هستم",
        "fan_alias": "فن شماره‌ی {n}",
        "dm_prompt": "✍️ پیامت به <b>{name}</b> رو همین‌جا بنویس؛ متن، عکس، ویس یا هر چیزی.\nجوابش هم همین‌جا میاد. آیدی هیچ‌کدومتون معلوم نمی‌شه 🙂",
        "sc_trial_started": "🎁 دوره‌ی آزمایشی رایگان <b>{title}</b> شروع شد ({days} روز). هر وقت خواستی از صفحه‌اش مشترک شو تا قطع نشه.",
    },
    "en": {
        "welcome": "Hi {name} 👋\n\nWelcome to <b>UploadFly</b>, your creator page inside Telegram.\n\n"
                   "⭐ <b>Earn from fans:</b> monthly subscriptions, locked posts, donations and paid messages. Stars go straight to your own bot; we take no cut.\n"
                   "🔗 <b>Free links:</b> send any file, photo, video or text and get a link.\n\n"
                   "Tap the button below or UploadFly next to the text box to create your page.\n\n🌐 Language: /lang",
        "help": "📌 <b>Help</b>\n\n"
                "<b>Creators:</b> your own bot is created in one tap. Post there (free, subscribers only, or locked), "
                "set a monthly subscription and a free trial, receive donations and chat with fans without revealing your personal account.\n\n"
                "<b>Commands</b>\n"
                "/shop — my page and shop\n"
                "/mylinks — my free links\n"
                "/lang — language\n"
                "/support — support\n\n"
                "⚠️ Weapons, drugs, human trafficking, scams and any sexual content involving minors are forbidden and get the account banned.\n"
                "🔞 Adult content only in a creator's own bot, marked \"sensitive\", and never in Explore.",
        "seller_welcome_owner": "Hi {name} 👋\n\nThis bot is your page.\n"
                                "• Anything you send becomes a post (you choose the price).\n"
                                "• Fan messages arrive here; reply to a message to answer. Reply with a photo or video to lock it (paid message).\n"
                                "• /broadcast : message all fans\n"
                                "• /balance : Stars balance",
        "seller_welcome_buyer": "Hi {name} 👋\n\nSee this creator's posts and subscription on their page. "
                                "To message the creator, just write here. To donate: /donate\n\n⚡️ Made with @{main}",
        "seller_help": "📌 <b>Help</b>\n\n"
                       "<b>Creator:</b> send content to post it. Reply to fan messages. Message everyone with /broadcast.\n"
                       "<b>Fan:</b> open the page, subscribe, write to the creator or donate with /donate.\n\n"
                       "<b>Commands</b>\n"
                       "/donate — donate\n"
                       "/mylinks — my links\n"
                       "/balance — Stars balance and withdrawal\n"
                       "/lang — language\n"
                       "/help — this help",
        "tip_title": "Donate ⭐",
        "tip_desc": "A donation straight to the creator (all of it goes to the creator's own bot)",
        "tip_owner_self": "Fans donate to you 🙂 Share your page link.",
        "tip_choose": "⭐ How much would you like to donate? All of it goes to the creator.",
        "tip_thanks": "💛 You donated {amount} Stars. Thank you! The creator has been notified.",
        "tip_owner": "💛 <b>New donation:</b> {amount} ⭐ from {name}\nAdded straight to your own bot's balance.",
        "dm_off": "This creator isn't taking messages right now.",
        "dm_fans_only": "Only subscribers and buyers can message this creator. See their page:",
        "dm_slow": "That's a lot of messages; please write again a bit later.",
        "dm_from": "💬 <b>Message from {name}</b> · total spent: {spent} ⭐\nReply to their message to answer.",
        "btn_dm_block": "🚫 Block",
        "btn_dm_unblock": "✅ Unblock",
        "dm_failed": "Your message didn't go through; please try again later.",
        "dm_sent": "✅ Sent to the creator. Their reply will arrive here.",
        "dm_blocked": "This fan is blocked; their messages won't reach you.",
        "dm_unblocked": "Unblocked.",
        "dm_reply_failed": "Couldn't reach this fan (they may have blocked the bot).",
        "btn_ppv_free": "🎁 Send free",
        "btn_cancel": "✖️ Cancel",
        "canceled": "Canceled.",
        "ppv_choose": "How should I send this? Free, or locked with a price (paid message):",
        "ppv_intro": "🔒 The creator sent you something special:",
        "ppv_sent": "✅ Sent.",
        "bc_limit": "You've reached today's broadcast limit ({n} per 24 hours). Try again tomorrow; the limit keeps your bot from being reported as spam.",
        "bc_choose": "📣 <b>Broadcast</b>\nWho should get it?",
        "seg_all": "All fans and followers ({n})",
        "seg_subscribers": "Active subscribers ({n})",
        "seg_expired": "Expired subscribers ({n})",
        "seg_buyers": "Buyers and donors ({n})",
        "bc_empty": "Nobody is in this group yet.",
        "bc_send_now": "Now send your message (text, photo, video or file). It goes to {n} people, silently.\nCancel: /cancel",
        "bc_confirm": "Send this message to {n} people?",
        "btn_bc_send": "📣 Send to {n}",
        "bc_ppv_choose": "For {n} people: send it free or locked (paid message)?",
        "bc_started": "📣 Sending to {n} people. I'll tell you when it's done.",
        "bc_done": "📣 Broadcast finished: delivered to {sent} of {total} people.",
        "btn_see_post": "👀 See the post",
        "new_post": "🆕 <b>{name}</b> posted something new\n{title}",
        "scheduled_live": "🗓 Your scheduled post is live: {title}",
        "sc_bundle_title": "{months}-month subscription",
        "adult_confirm": "🔞 This content is for adults only. Do you confirm you are 18 or older?",
        "btn_adult_yes": "Yes, I'm 18+",
        "fan_alias": "Fan #{n}",
        "dm_prompt": "✍️ Write your message to <b>{name}</b> right here: text, photo, voice, anything.\nThe reply arrives here too.",
        "sc_trial_started": "🎁 Your free trial of <b>{title}</b> has started ({days} days). Subscribe on the page any time so it doesn't stop.",
    },
    "ru": {
        "welcome": "Привет, {name} 👋\n\nДобро пожаловать в <b>UploadFly</b> — вашу страницу автора в Telegram.\n\n"
                   "⭐ <b>Зарабатывайте на фанатах:</b> ежемесячная подписка, закрытые посты, донаты и платные сообщения. Stars идут прямо в вашего бота; мы не берём комиссию.\n"
                   "🔗 <b>Бесплатные ссылки:</b> отправьте файл, фото, видео или текст и получите ссылку.\n\n"
                   "Нажмите кнопку ниже или UploadFly рядом с полем ввода, чтобы создать страницу.\n\n🌐 Язык: /lang",
        "help": "📌 <b>Помощь</b>\n\n"
                "<b>Авторы:</b> ваш бот создаётся в одно касание. Публикуйте посты (бесплатно, для подписчиков или закрытые), "
                "настройте подписку и пробный период, получайте донаты и общайтесь с фанатами, не раскрывая личный аккаунт.\n\n"
                "<b>Команды</b>\n"
                "/shop — моя страница и магазин\n"
                "/mylinks — мои бесплатные ссылки\n"
                "/lang — язык\n"
                "/support — поддержка\n\n"
                "⚠️ Оружие, наркотики, торговля людьми, мошенничество и любой сексуальный контент с несовершеннолетними запрещены и ведут к блокировке.\n"
                "🔞 Контент для взрослых — только в личном боте автора, с пометкой «чувствительный» и никогда в разделе «Обзор».",
        "seller_welcome_owner": "Привет, {name} 👋\n\nЭтот бот — ваша страница.\n"
                                "• Всё, что вы отправите, станет постом (цену выбираете вы).\n"
                                "• Сообщения фанатов приходят сюда; ответьте на сообщение, чтобы написать фанату. Ответ фото или видео можно закрыть (платное сообщение).\n"
                                "• /broadcast : рассылка фанатам\n"
                                "• /balance : баланс Stars",
        "seller_welcome_buyer": "Привет, {name} 👋\n\nПосты и подписка этого автора — на его странице. "
                                "Чтобы написать автору, просто пишите сюда. Донат: /donate\n\n⚡️ Сделано с @{main}",
        "seller_help": "📌 <b>Помощь</b>\n\n"
                       "<b>Автор:</b> отправьте контент, чтобы опубликовать. Отвечайте на сообщения фанатов. Рассылка: /broadcast.\n"
                       "<b>Фанат:</b> откройте страницу, подпишитесь, напишите автору или задонатьте через /donate.\n\n"
                       "<b>Команды</b>\n"
                       "/donate — донат\n"
                       "/mylinks — мои ссылки\n"
                       "/balance — баланс Stars и вывод\n"
                       "/lang — язык\n"
                       "/help — помощь",
        "tip_title": "Донат ⭐",
        "tip_desc": "Донат напрямую автору (всё идёт в бота самого автора)",
        "tip_owner_self": "Донаты вам отправляют фанаты 🙂 Поделитесь ссылкой на страницу.",
        "tip_choose": "⭐ Сколько задонатить? Всё уйдёт автору.",
        "tip_thanks": "💛 Вы задонатили {amount} Stars. Спасибо! Автор получил уведомление.",
        "tip_owner": "💛 <b>Новый донат:</b> {amount} ⭐ от {name}\nЗачислено прямо на баланс вашего бота.",
        "dm_off": "Автор сейчас не принимает сообщения.",
        "dm_fans_only": "Писать этому автору могут только подписчики и покупатели. Его страница:",
        "dm_slow": "Слишком много сообщений; напишите чуть позже.",
        "dm_from": "💬 <b>Сообщение от {name}</b> · всего потрачено: {spent} ⭐\nЧтобы ответить, используйте «Ответить» на его сообщении.",
        "btn_dm_block": "🚫 Заблокировать",
        "btn_dm_unblock": "✅ Разблокировать",
        "dm_failed": "Сообщение не доставлено; попробуйте позже.",
        "dm_sent": "✅ Отправлено автору. Ответ придёт сюда.",
        "dm_blocked": "Фанат заблокирован; его сообщения больше не придут.",
        "dm_unblocked": "Разблокирован.",
        "dm_reply_failed": "Не удалось доставить фанату (возможно, он заблокировал бота).",
        "btn_ppv_free": "🎁 Отправить бесплатно",
        "btn_cancel": "✖️ Отмена",
        "canceled": "Отменено.",
        "ppv_choose": "Как отправить? Бесплатно или закрыто с ценой (платное сообщение):",
        "ppv_intro": "🔒 Автор отправил вам кое-что особенное:",
        "ppv_sent": "✅ Отправлено.",
        "bc_limit": "Лимит рассылок на сегодня исчерпан ({n} за 24 часа). Попробуйте завтра; лимит защищает бота от жалоб на спам.",
        "bc_choose": "📣 <b>Рассылка</b>\nКому отправить?",
        "seg_all": "Все фанаты и подписчики бота ({n})",
        "seg_subscribers": "Активные подписчики ({n})",
        "seg_expired": "Подписка закончилась ({n})",
        "seg_buyers": "Покупатели и донатеры ({n})",
        "bc_empty": "В этой группе пока никого нет.",
        "bc_send_now": "Теперь отправьте сообщение (текст, фото, видео или файл). Оно уйдёт {n} людям без звука.\nОтмена: /cancel",
        "bc_confirm": "Отправить это сообщение {n} людям?",
        "btn_bc_send": "📣 Отправить {n}",
        "bc_ppv_choose": "Для {n} человек: отправить бесплатно или закрыто (платное сообщение)?",
        "bc_started": "📣 Рассылка {n} людям началась. Сообщу, когда закончится.",
        "bc_done": "📣 Рассылка завершена: доставлено {sent} из {total}.",
        "btn_see_post": "👀 Открыть пост",
        "new_post": "🆕 <b>{name}</b> опубликовал новый пост\n{title}",
        "scheduled_live": "🗓 Запланированный пост опубликован: {title}",
        "sc_bundle_title": "Подписка на {months} мес.",
        "adult_confirm": "🔞 Этот контент только для взрослых. Подтверждаете, что вам 18 или больше?",
        "btn_adult_yes": "Да, мне 18+",
        "fan_alias": "Фанат №{n}",
        "dm_prompt": "✍️ Напишите сообщение для <b>{name}</b> прямо здесь: текст, фото, голосовое — что угодно.\nОтвет придёт сюда же.",
        "sc_trial_started": "🎁 Бесплатный пробный период <b>{title}</b> начался ({days} дн.). Оформите подписку на странице, чтобы доступ не прервался.",
    },
    "ar": {
        "welcome": "مرحبًا {name} 👋\n\nأهلًا بك في <b>UploadFly</b>، صفحتك كصانع محتوى داخل تيليجرام.\n\n"
                   "⭐ <b>اربح من معجبيك:</b> اشتراك شهري، منشورات مقفلة، تبرّعات ورسائل مدفوعة. تذهب النجوم مباشرة إلى بوتك الخاص ولا نأخذ أي عمولة.\n"
                   "🔗 <b>روابط مجانية:</b> أرسل أي ملف أو صورة أو فيديو أو نص واحصل على رابط.\n\n"
                   "اضغط الزر أدناه أو UploadFly بجانب مربع الكتابة لإنشاء صفحتك.\n\n🌐 اللغة: /lang",
        "help": "📌 <b>المساعدة</b>\n\n"
                "<b>صنّاع المحتوى:</b> يُنشأ بوتك الخاص بلمسة واحدة. انشر فيه (مجانًا، للمشتركين فقط، أو مقفلًا)، "
                "وحدّد اشتراكًا شهريًا وفترة تجربة، واستقبل التبرّعات وتحدث مع معجبيك دون كشف حسابك الشخصي.\n\n"
                "<b>الأوامر</b>\n"
                "/shop — صفحتي ومتجري\n"
                "/mylinks — روابطي المجانية\n"
                "/lang — اللغة\n"
                "/support — الدعم\n\n"
                "⚠️ الأسلحة والمخدرات والاتجار بالبشر والاحتيال وأي محتوى جنسي يخص القاصرين ممنوعة وتؤدي إلى حظر الحساب.\n"
                "🔞 محتوى البالغين فقط في بوت الصانع الخاص، بعلامة «حساس»، ولا يظهر أبدًا في الاستكشاف.",
        "seller_welcome_owner": "مرحبًا {name} 👋\n\nهذا البوت هو صفحتك.\n"
                                "• كل ما ترسله يصبح منشورًا (أنت تختار السعر).\n"
                                "• تصلك رسائل المعجبين هنا؛ استخدم «رد» على الرسالة للإجابة. يمكنك قفل صورة أو فيديو في الرد (رسالة مدفوعة).\n"
                                "• /broadcast : رسالة جماعية للمعجبين\n"
                                "• /balance : رصيد النجوم",
        "seller_welcome_buyer": "مرحبًا {name} 👋\n\nشاهد منشورات هذا الصانع واشتراكه في صفحته. "
                                "لمراسلة الصانع اكتب هنا مباشرة. للتبرّع: /donate\n\n⚡️ صُنع باستخدام @{main}",
        "seller_help": "📌 <b>المساعدة</b>\n\n"
                       "<b>الصانع:</b> أرسل المحتوى لنشره. رد على رسائل المعجبين. راسل الجميع عبر /broadcast.\n"
                       "<b>المعجب:</b> افتح الصفحة، اشترك، راسل الصانع أو تبرّع عبر /donate.\n\n"
                       "<b>الأوامر</b>\n"
                       "/donate — تبرّع\n"
                       "/mylinks — روابطي\n"
                       "/balance — رصيد النجوم والسحب\n"
                       "/lang — اللغة\n"
                       "/help — المساعدة",
        "tip_title": "تبرّع ⭐",
        "tip_desc": "تبرّع مباشر للصانع (كلها تذهب إلى بوت الصانع نفسه)",
        "tip_owner_self": "المعجبون هم من يتبرّعون لك 🙂 شارك رابط صفحتك.",
        "tip_choose": "⭐ كم تريد أن تتبرّع؟ كلها تذهب للصانع.",
        "tip_thanks": "💛 تبرّعت بـ {amount} نجمة. شكرًا لك! تم إبلاغ الصانع.",
        "tip_owner": "💛 <b>تبرّع جديد:</b> {amount} ⭐ من {name}\nأُضيفت مباشرة إلى رصيد بوتك.",
        "dm_off": "هذا الصانع لا يستقبل الرسائل حاليًا.",
        "dm_fans_only": "مراسلة هذا الصانع متاحة للمشتركين والمشترين فقط. شاهد صفحته:",
        "dm_slow": "رسائل كثيرة؛ اكتب مرة أخرى بعد قليل.",
        "dm_from": "💬 <b>رسالة من {name}</b> · إجمالي الإنفاق: {spent} ⭐\nللرد استخدم «رد» على رسالته.",
        "btn_dm_block": "🚫 حظر",
        "btn_dm_unblock": "✅ إلغاء الحظر",
        "dm_failed": "لم تصل رسالتك؛ حاول لاحقًا.",
        "dm_sent": "✅ أُرسلت إلى الصانع. سيصلك الرد هنا.",
        "dm_blocked": "تم حظر هذا المعجب؛ لن تصلك رسائله.",
        "dm_unblocked": "تم إلغاء الحظر.",
        "dm_reply_failed": "تعذّر الوصول إلى هذا المعجب (ربما حظر البوت).",
        "btn_ppv_free": "🎁 إرسال مجانًا",
        "btn_cancel": "✖️ إلغاء",
        "canceled": "تم الإلغاء.",
        "ppv_choose": "كيف أرسل هذا؟ مجانًا أم مقفلًا بسعر (رسالة مدفوعة):",
        "ppv_intro": "🔒 أرسل لك الصانع شيئًا مميزًا:",
        "ppv_sent": "✅ تم الإرسال.",
        "bc_limit": "وصلت إلى حد الرسائل الجماعية اليوم ({n} خلال 24 ساعة). حاول غدًا؛ هذا الحد يحمي بوتك من بلاغات الإزعاج.",
        "bc_choose": "📣 <b>رسالة جماعية</b>\nلمن أرسلها؟",
        "seg_all": "كل المعجبين والمتابعين ({n})",
        "seg_subscribers": "المشتركون النشطون ({n})",
        "seg_expired": "انتهى اشتراكهم ({n})",
        "seg_buyers": "المشترون والمتبرّعون ({n})",
        "bc_empty": "لا يوجد أحد في هذه المجموعة بعد.",
        "bc_send_now": "أرسل رسالتك الآن (نص أو صورة أو فيديو أو ملف). ستصل إلى {n} شخصًا بدون صوت.\nإلغاء: /cancel",
        "bc_confirm": "إرسال هذه الرسالة إلى {n} شخصًا؟",
        "btn_bc_send": "📣 إرسال إلى {n}",
        "bc_ppv_choose": "إلى {n} شخصًا: أرسلها مجانًا أم مقفلة (رسالة مدفوعة)؟",
        "bc_started": "📣 بدأ الإرسال إلى {n} شخصًا. سأخبرك عند الانتهاء.",
        "bc_done": "📣 انتهت الرسالة الجماعية: وصلت إلى {sent} من {total}.",
        "btn_see_post": "👀 مشاهدة المنشور",
        "new_post": "🆕 نشر <b>{name}</b> منشورًا جديدًا\n{title}",
        "scheduled_live": "🗓 تم نشر منشورك المجدول: {title}",
        "sc_bundle_title": "اشتراك {months} أشهر",
        "adult_confirm": "🔞 هذا المحتوى للبالغين فقط. هل تؤكد أن عمرك 18 عامًا أو أكثر؟",
        "btn_adult_yes": "نعم، عمري 18+",
        "fan_alias": "المعجب رقم {n}",
        "dm_prompt": "✍️ اكتب رسالتك إلى <b>{name}</b> هنا مباشرة: نص أو صورة أو رسالة صوتية أو أي شيء.\nوسيصلك الرد هنا أيضًا.",
        "sc_trial_started": "🎁 بدأت تجربتك المجانية لـ <b>{title}</b> ({days} أيام). اشترك من الصفحة في أي وقت حتى لا تنقطع.",
    },
    "zh": {
        "welcome": "你好 {name} 👋\n\n欢迎来到 <b>UploadFly</b>，你在 Telegram 里的创作者主页。\n\n"
                   "⭐ <b>从粉丝获得收入：</b>月度订阅、付费帖子、打赏和付费私信。Stars 直接进入你自己的机器人，我们不抽成。\n"
                   "🔗 <b>免费链接：</b>发送任何文件、照片、视频或文字即可获得链接。\n\n"
                   "点击下方按钮或输入框旁的 UploadFly 创建你的主页。\n\n🌐 语言：/lang",
        "help": "📌 <b>帮助</b>\n\n"
                "<b>创作者：</b>一键创建你自己的机器人。在那里发帖（免费、仅订阅者或付费解锁），"
                "设置月度订阅和免费试用，接收打赏，与粉丝聊天而不暴露你的个人账号。\n\n"
                "<b>命令</b>\n"
                "/shop — 我的主页和店铺\n"
                "/mylinks — 我的免费链接\n"
                "/lang — 语言\n"
                "/support — 客服\n\n"
                "⚠️ 武器、毒品、人口贩卖、诈骗以及任何涉及未成年人的色情内容均被禁止，并会导致封号。\n"
                "🔞 成人内容只能在创作者自己的机器人中发布，并标记为“敏感”，且永远不会出现在发现页。",
        "seller_welcome_owner": "你好 {name} 👋\n\n这个机器人就是你的主页。\n"
                                "• 你发送的任何内容都会成为帖子（价格由你决定）。\n"
                                "• 粉丝的消息会发到这里；对消息点“回复”即可回答。用照片或视频回复时可以加锁（付费私信）。\n"
                                "• /broadcast ：群发给粉丝\n"
                                "• /balance ：Stars 余额",
        "seller_welcome_buyer": "你好 {name} 👋\n\n在主页查看这位创作者的帖子和订阅。"
                                "想给创作者发消息，直接在这里写。打赏：/donate\n\n⚡️ 由 @{main} 制作",
        "seller_help": "📌 <b>帮助</b>\n\n"
                       "<b>创作者：</b>发送内容即可发帖。回复粉丝消息。用 /broadcast 群发。\n"
                       "<b>粉丝：</b>打开主页、订阅、给创作者写消息，或用 /donate 打赏。\n\n"
                       "<b>命令</b>\n"
                       "/donate — 打赏\n"
                       "/mylinks — 我的链接\n"
                       "/balance — Stars 余额和提现\n"
                       "/lang — 语言\n"
                       "/help — 帮助",
        "tip_title": "打赏 ⭐",
        "tip_desc": "直接打赏给创作者（全部进入创作者自己的机器人）",
        "tip_owner_self": "打赏是粉丝给你的 🙂 分享你的主页链接吧。",
        "tip_choose": "⭐ 你想打赏多少？全部归创作者。",
        "tip_thanks": "💛 你打赏了 {amount} Stars，谢谢！已通知创作者。",
        "tip_owner": "💛 <b>新打赏：</b>{amount} ⭐，来自 {name}\n已直接计入你的机器人余额。",
        "dm_off": "这位创作者目前不接收消息。",
        "dm_fans_only": "只有订阅者和买家可以给这位创作者发消息。看看他的主页：",
        "dm_slow": "消息太多了，请稍后再写。",
        "dm_from": "💬 <b>来自 {name} 的消息</b> · 累计消费：{spent} ⭐\n对他的消息点“回复”即可回答。",
        "btn_dm_block": "🚫 屏蔽",
        "btn_dm_unblock": "✅ 取消屏蔽",
        "dm_failed": "消息未送达，请稍后再试。",
        "dm_sent": "✅ 已发送给创作者。回复会出现在这里。",
        "dm_blocked": "已屏蔽该粉丝，你将不再收到他的消息。",
        "dm_unblocked": "已取消屏蔽。",
        "dm_reply_failed": "无法送达该粉丝（他可能屏蔽了机器人）。",
        "btn_ppv_free": "🎁 免费发送",
        "btn_cancel": "✖️ 取消",
        "canceled": "已取消。",
        "ppv_choose": "怎么发送？免费，还是加锁定价（付费私信）：",
        "ppv_intro": "🔒 创作者给你发了一份特别内容：",
        "ppv_sent": "✅ 已发送。",
        "bc_limit": "今天的群发次数已用完（24 小时内 {n} 次）。请明天再试；这个限制可以防止你的机器人被举报为垃圾信息。",
        "bc_choose": "📣 <b>群发</b>\n发给谁？",
        "seg_all": "所有粉丝和关注者（{n}）",
        "seg_subscribers": "有效订阅者（{n}）",
        "seg_expired": "订阅已结束（{n}）",
        "seg_buyers": "买家和打赏者（{n}）",
        "bc_empty": "这个分组里还没有人。",
        "bc_send_now": "现在发送你的消息（文字、照片、视频或文件）。将静音发送给 {n} 人。\n取消：/cancel",
        "bc_confirm": "把这条消息发给 {n} 人？",
        "btn_bc_send": "📣 发送给 {n} 人",
        "bc_ppv_choose": "发给 {n} 人：免费发送还是加锁（付费私信）？",
        "bc_started": "📣 已开始发送给 {n} 人，完成后通知你。",
        "bc_done": "📣 群发完成：{total} 人中送达 {sent} 人。",
        "btn_see_post": "👀 查看帖子",
        "new_post": "🆕 <b>{name}</b> 发布了新帖子\n{title}",
        "scheduled_live": "🗓 你的定时帖子已发布：{title}",
        "sc_bundle_title": "{months} 个月订阅",
        "adult_confirm": "🔞 此内容仅限成年人。你确认已年满 18 岁吗？",
        "btn_adult_yes": "是的，我已满 18 岁",
        "fan_alias": "粉丝 #{n}",
        "dm_prompt": "✍️ 直接在这里给 <b>{name}</b> 写消息：文字、照片、语音都可以。\n回复也会出现在这里。",
        "sc_trial_started": "🎁 <b>{title}</b> 的免费试用已开始（{days} 天）。随时可在主页订阅，避免中断。",
    },
}
