"""محتوای صفحه‌های سایت. {START} = لینک ربات با برچسب منبع همان صفحه، {BOT} = یوزرنیم ربات اصلی،
{SUPPORT} = راه‌های تماس. متن‌ها صادق‌اند: هیچ عدد یا نظر ساختگی.
کلیدواژه‌های هدف (فارسی): فروش فایل در تلگرام، ربات آپلودر تلگرام، ساخت لینک فایل تلگرام، فروش با استارز،
خرید و نقد کردن استارز تلگرام، کانال VIP تلگرام، لینک بیو اینستاگرام برای فروش.
"""

CHECK = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>'
CROSS = '<svg class="ic no" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 7 10 10M17 7 7 17"/></svg>'


def cta_band(title: str, text: str, button: str) -> str:
    return f"""<section class="section"><div class="wrap"><div class="band">
  <div><h2 class="h2">{title}</h2><p>{text}</p></div>
  <a class="btn btn-light btn-lg" href="{{START}}" rel="noopener">{button}</a>
</div></div></section>"""


def page_head(kicker: str, h1: str, lead: str, button: str, note: str = "") -> str:
    return f"""<section class="hero hero-page"><div class="wrap narrow">
  <p class="kicker">{kicker}</p><h1>{h1}</h1><p class="lead">{lead}</p>
  <div class="hero-cta"><a class="btn btn-primary btn-lg" href="{{START}}" rel="noopener">{button}</a>{f'<span class="note">{note}</span>' if note else ''}</div>
</div></section>"""


HOME_FAQ = [
    ("UploadFly چیست؟", "یک ربات تلگرام برای ساختن لینک از هر فایل و فروش فایل با استارز تلگرام. فایل را برای ربات می‌فرستی و لینک می‌گیری؛ اگر بخواهی بفروشی، یک فروشگاه (ربات اختصاصی خودت) می‌سازی و پول فروش مستقیم به همان ربات می‌رود."),
    ("استفاده از UploadFly هزینه دارد؟", "نه. ساخت لینک، ساخت فروشگاه و فروش رایگان است و UploadFly از فروش تو سهمی برنمی‌دارد."),
    ("پول فروش کجا می‌رود؟", "مستقیم به موجودی ربات فروشگاهِ خودت. ربات با حساب تلگرام خودت ساخته می‌شود و فقط تو می‌توانی از آن برداشت کنی؛ UploadFly هیچ‌وقت پولی نگه نمی‌دارد."),
    ("خریدار ایرانی چطور پرداخت می‌کند؟", "با استارز تلگرام. در ایران سایت‌ها و ربات‌هایی هستند که استارز را با تومان و فقط با یوزرنیم تلگرام می‌فروشند. <a href=\"/telegram-stars/\">راهنمای کامل خرید استارز</a>"),
    ("فایل من کپی یا فوروارد نمی‌شود؟", "همه‌ی محتواها «محافظت‌شده» تحویل داده می‌شوند: دکمه‌ی فوروارد و ذخیره در تلگرام برای خریدار بسته است. (هیچ ابزاری جلوی فیلم‌برداری از صفحه با گوشی دیگر را نمی‌گیرد.)"),
]

HOME = f"""<section class="hero"><div class="wrap hero-in">
  <div class="hero-text">
    <p class="kicker">ربات آپلودر و فروش فایل در تلگرام</p>
    <h1>فایل بفرست، لینک بگیر. <span class="hl">بفروش؛ پولش مستقیم مال خودت.</span></h1>
    <p class="lead">هر فایل، عکس، ویدیو، موزیک یا متن را برای ربات بفرست و همان لحظه لینک بگیر. برای فروش، با یک ضربه فروشگاه خودت را بساز و با <strong>استارز تلگرام</strong> بفروش؛ تحویل خودکار، فایل محافظت‌شده، بدون کارت‌به‌کارت.</p>
    <div class="hero-cta"><a class="btn btn-primary btn-lg" href="{{START}}" rel="noopener">شروع رایگان در تلگرام</a><a class="btn btn-ghost btn-lg" href="/sell/">فروش فایل چطور است؟</a></div>
    <ul class="ticks"><li>{CHECK}رایگان، بدون سهم از فروش</li><li>{CHECK}پول مستقیم به ربات خودت</li><li>{CHECK}۵ زبان</li></ul>
  </div>
  <div class="flow" aria-hidden="true">
    <div class="flow-card"><span class="k k-doc">PDF</span><div><b>دوره-فتوشاپ.pdf</b><small>۱۲ مگابایت · ۸۴ صفحه</small></div></div>
    <div class="flow-arrow"></div>
    <div class="flow-card"><span class="k k-link">🔗</span><div><b>لینک ساخته شد</b><small class="ltr">t.me/{{BOT}}?start=…</small></div></div>
    <div class="flow-arrow"></div>
    <div class="flow-card sale"><span class="k k-star">★</span><div><b>فروش تازه: ۵۰ استارز</b><small>مستقیم به ربات فروشگاه تو</small></div></div>
  </div>
</div></section>

<section class="section"><div class="wrap">
  <h2 class="h2 center">در سه قدم</h2>
  <ol class="steps">
    <li><span class="n">۱</span><h3>بفرست</h3><p>فایل را در تلگرام برای ربات بفرست یا از هر کانالی فوروارد کن؛ تا ۲ گیگابایت.</p></li>
    <li><span class="n">۲</span><h3>لینک بگیر</h3><p>لینک رایگان برای اشتراک‌گذاری، یا قیمت به استارز برای فروش. پیش‌نمایش را خود سیستم می‌سازد.</p></li>
    <li><span class="n">۳</span><h3>پخش کن</h3><p>لینک را در کانال، گروه یا بیو اینستاگرام بگذار. تحویل و پرداخت خودکار است.</p></li>
  </ol>
</div></section>

<section class="section globe-sec"><div class="wrap">
  <div class="globe-head"><p class="kicker">فروش بدون مرز</p><h2 class="h2">بازار تو: کل زمین</h2><p class="lead">استارز پول مشترک همه‌ی کاربران تلگرام است. خریدار از هر کشوری با چند ضربه پرداخت می‌کند و پولش مستقیم به ربات فروشگاه خودت می‌رسد. کره را با موس یا انگشت بچرخان.</p></div>
  <div class="globe" data-globe data-hub="35.7,51.4" tabindex="0" role="img" aria-label="کره‌ی زمین؛ فروش از کشورهای مختلف به یک فروشگاه در ایران"><canvas></canvas><p class="globe-hint" aria-hidden="true">بکش تا بچرخد</p></div>
  <div class="globe-cells"><div class="globe-cell"><svg class="cell-ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3Z"/></svg><h3>خریدار از هر جای دنیا</h3><p>هر کسی که تلگرام دارد می‌تواند با استارز بخرد؛ بدون کارت بانکی ایرانی و بدون درگاه پرداخت.</p></div><div class="globe-cell"><svg class="cell-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h9M8.5 3v2M6 5c.6 3.3 2.6 6 6 7.6M11 5c-.8 3.6-3 6.6-6.5 8.4M13 21l4-9 4 9M14.4 18h5.2"/></svg><h3>به زبان خود خریدار</h3><p>ربات و مینی‌اپ به ۵ زبان کار می‌کنند: فارسی، انگلیسی، روسی، عربی و چینی.</p></div><div class="globe-cell"><svg class="cell-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7.5A2.5 2.5 0 0 1 6.5 5H18v3M4 7.5V17a2 2 0 0 0 2 2h14V8H6.5A2.5 2.5 0 0 1 4 7.5Z"/><circle cx="16" cy="13.5" r="1.2"/></svg><h3>پول مستقیم به ربات تو</h3><p>هر فروش، از هر کشوری، همان لحظه به موجودی ربات فروشگاهت اضافه می‌شود و برداشتش با خودت است.</p></div></div>
</div></section>

<section class="section alt"><div class="wrap split">
  <div>
    <p class="kicker">برای فروشنده‌ها</p>
    <h2 class="h2">کارت‌به‌کارت، رسید گرفتن و فرستادن دستی تمام.</h2>
    <p>فروشگاهت یک ربات تلگرام اختصاصی است که با یک ضربه ساخته می‌شود و مالکش خودت هستی. خریدار پرداخت می‌کند، فایل خودکار و محافظت‌شده تحویل داده می‌شود و تو فقط پیام «فروش تازه» می‌گیری.</p>
    <a class="link-more" href="/sell/">همه‌چیز درباره‌ی فروش فایل ←</a>
  </div>
  <div class="table-card" role="region" aria-label="مقایسه">
    <table class="compare">
      <thead><tr><th></th><th>کارت‌به‌کارت</th><th>UploadFly</th></tr></thead>
      <tbody>
        <tr><th>تحویل فایل</th><td>دستی، بعد از چک رسید</td><td>{CHECK}خودکار، همان لحظه</td></tr>
        <tr><th>فوروارد و پخش فایل</th><td>{CROSS}آزاد</td><td>{CHECK}بسته (محافظت‌شده)</td></tr>
        <tr><th>بازپرداخت</th><td>دعوا و پیام</td><td>{CHECK}دکمه‌ای، قبل از دیدن</td></tr>
        <tr><th>فروش به خارج از ایران</th><td>{CROSS}سخت</td><td>{CHECK}با استارز</td></tr>
        <tr><th>شب‌ها و وقتی خوابی</th><td>{CROSS}فروش متوقف</td><td>{CHECK}۲۴ ساعته</td></tr>
      </tbody>
    </table>
  </div>
</div></section>

<section class="section"><div class="wrap">
  <h2 class="h2 center">برای چه کسانی؟</h2>
  <ul class="uses">
    <li><b>مدرس‌ها</b><span>دوره‌ی ویدیویی، جزوه، نمونه سؤال</span></li>
    <li><b>طراح‌ها</b><span>قالب، پریست لایت‌روم، فونت، موکاپ</span></li>
    <li><b>موسیقی و پادکست</b><span>آهنگ، بیت، اپیزود ویژه</span></li>
    <li><b>عکاس‌ها</b><span>آلبوم، فایل با کیفیت اصلی</span></li>
    <li><b>ادمین کانال‌ها</b><span>محتوای VIP با اشتراک ماهانه</span></li>
    <li><b>همه</b><span>اشتراک امن فایل با دوست و همکار، رایگان</span></li>
  </ul>
</div></section>

<section class="section alt"><div class="wrap feature-rows">
  <article class="feature"><h3>ویترین برای بیو اینستاگرام</h3><p>یک صفحه‌ی زیبا مثل Linktree برای همه‌ی محصولاتت، با ۴ تم، بنر و لوگو؛ ورود رایگان، یک‌بار یا اشتراک ماهانه. <a href="/showcase/">درباره‌ی ویترین</a></p></article>
  <article class="feature"><h3>پیش‌نمایش که فروشنده نمی‌تواند دستکاری کند</h3><p>عکس تار، چند فریم از ویدیو، صفحه‌ی اول PDF یا چند ثانیه از صدا؛ مشخصات واقعی فایل از خود تلگرام خوانده می‌شود، نه ادعای فروشنده.</p></article>
  <article class="feature"><h3>خریدار خیالش راحت است</h3><p>تا قبل از باز کردن محتوا، بازپرداخت کامل با یک دکمه؛ گزارش مشکل و امتیاز فقط از خریدار واقعی.</p></article>
  <article class="feature"><h3>پولت پیش خودت</h3><p>استارزها در ربات خودت جمع می‌شوند و فقط تو برداشتشان می‌کنی؛ حتی اگر UploadFly نباشد. <a href="/telegram-stars/">برداشت و تبدیل به تومان</a></p></article>
</div></section>
""" + cta_band("همین حالا امتحان کن", "رایگان است و یک دقیقه طول می‌کشد. فقط تلگرام لازم داری.", "شروع در تلگرام")

SELL_FAQ = [
    ("آموزش فروش در تلگرام: از کجا شروع کنم؟", "۱. در ربات UploadFly فروشگاهت را بساز (یک ضربه). ۲. اولین فایل را بفرست و قیمتش را به استارز بگذار. ۳. لینک فروش را در کانال، گروه یا بیو اینستاگرامت بگذار. یک ویترین هم بساز تا همه‌ی محصولاتت یک‌جا دیده شوند."),
    ("برای فروش فایل در تلگرام باید کانال داشته باشم؟", "نه. لینک هر محصول را هر جا بگذاری کار می‌کند: کانال، گروه، بیو اینستاگرام، واتس‌اپ یا سایت."),
    ("UploadFly چقدر از فروش برمی‌دارد؟", "هیچ. کل مبلغ به ربات فروشگاه تو می‌رسد. فقط هنگام برداشت، تلگرام نرخ تبدیل استارز به TON را اعمال می‌کند."),
    ("حداقل برداشت چقدر است؟", "قانون تلگرام: هر فروش ۲۱ روز بعد قابل برداشت می‌شود و حداقل برداشت معمولاً ۱۰۰۰ استارز است. تا آن موقع استارزها سر جایشان در ربات تو می‌مانند."),
    ("چرا فروشنده‌ی تازه سقف قیمت دارد؟", "برای امنیت خریدارها. با هر فروش موفق، سقف قیمت بالاتر می‌رود."),
    ("محتوای بزرگسالان مجاز است؟", "فقط در ربات فروشگاه و با علامت «حساس» که بعد از زمان نمایش خودکار پاک می‌شود. فروش سلاح، مواد، کلاهبرداری و هر محتوای جنسی مربوط به کودکان ممنوع است و حساب برای همیشه مسدود می‌شود."),
]

SELL = page_head("فروش فایل در تلگرام", "فروش فایل در تلگرام، خودکار و بدون کارت‌به‌کارت",
                 "دوره، جزوه، قالب، موزیک یا هر فایل دیگری را با استارز تلگرام بفروش. خریدار پرداخت می‌کند و فایل خودکار و محافظت‌شده تحویل می‌گیرد؛ پول مستقیم به ربات خودت می‌رسد.",
                 "ساخت فروشگاه رایگان", "بدون سهم از فروش") + f"""
<section class="section"><div class="wrap narrow prose">
  <h2>ربات فروشگاهی تلگرام، مال خودت</h2>
  <p>در UploadFly هر فروشنده یک ربات تلگرام اختصاصی دارد که با یک ضربه از داخل مینی‌اپ ساخته می‌شود. ربات با حساب تلگرام خودت ثبت می‌شود؛ یعنی <strong>مالکش تویی</strong> و پرداخت‌های استارز مستقیم به موجودی همان ربات می‌رود. ما واسطه‌ی پول نیستیم.</p>
  <h2>محصول گذاشتن در یک دقیقه</h2>
  <ol>
    <li>در ربات فروشگاهت فایل را بفرست (یا از کانال فوروارد کن).</li>
    <li>قیمت را به استارز انتخاب کن و اگر لازم است «حساس» یا «قابل ذخیره» را تنظیم کن.</li>
    <li>پیش‌نمایش را خود سیستم می‌سازد و لینک فروش آماده است.</li>
  </ol>
  <h2>چه فایل‌هایی را می‌شود فروخت؟</h2>
  <p>هر فایل دیجیتالی تا ۲ گیگابایت: فایل PDF، جزوه و کتاب الکترونیکی؛ دوره‌ی آموزشی ویدیویی؛ فایل لایه‌باز، گرافیکی و موکاپ؛ پریست، قالب و فونت؛ فایل اکسل و قالب‌های کاری؛ موزیک، بیت و پادکست؛ عکس با کیفیت اصلی. متن و پیام پولی هم می‌شود فروخت.</p>
  <h2>چرا خریدارها اعتماد می‌کنند</h2>
  <ul class="checklist">
    <li>{CHECK}<span><b>مشخصات واقعی:</b> حجم، مدت، تعداد صفحه و نوع فایل از خود تلگرام خوانده می‌شود.</span></li>
    <li>{CHECK}<span><b>پیش‌نمایش سیستمی:</b> فروشنده نمی‌تواند پیش‌نمایش گول‌زننده بگذارد.</span></li>
    <li>{CHECK}<span><b>بازپرداخت:</b> تا قبل از باز کردن محتوا و تا ۲۴ ساعت، با یک دکمه.</span></li>
    <li>{CHECK}<span><b>امتیاز واقعی:</b> فقط کسی که خریده و باز کرده امتیاز می‌دهد.</span></li>
  </ul>
  <h2>اشتراک ماهانه و کانال VIP</h2>
  <p>به‌جای «کانال VIP با کارت‌به‌کارت»، یک <a href="/showcase/">ویترین با اشتراک ماهانه</a> بساز. تلگرام هر ماه خودکار تمدید می‌کند، یادآوری می‌فرستد و عضو هر وقت بخواهد تمدید را خاموش می‌کند.</p>
  <h2>فروش به خارج از ایران</h2>
  <p>خریدارهای خارج از ایران استارز را مستقیم در تلگرام می‌خرند. یعنی بدون حساب بانکی خارجی می‌توانی به مخاطب فارسی‌زبان یا خارجی در هر کشوری بفروشی.</p>
</div></section>
""" + cta_band("فروشگاهت را همین الان بساز", "ساخت فروشگاه رایگان است و پول هر فروش مستقیم به ربات خودت می‌رود.", "ساخت فروشگاه")

LINK_FAQ = [
    ("آپلودر تلگرام چیست؟", "رباتی که فایل را نگه می‌دارد و برایش لینک می‌سازد؛ هر کس روی لینک بزند، فایل را داخل تلگرام می‌گیرد. UploadFly یک ربات آپلودر رایگان است که فایل را محافظت‌شده تحویل می‌دهد و آمار بازدید هم دارد."),
    ("می‌توانم ربات آپلودر اختصاصی خودم را بسازم؟", "بله، رایگان و بدون کدنویسی. وقتی در UploadFly فروشگاه می‌سازی، یک ربات تلگرام به اسم خودت با یک ضربه ساخته می‌شود که مالکش تویی. همان ربات فایل‌هایت را می‌گیرد و برای هر کدام لینک فروش می‌سازد."),
    ("حداکثر حجم فایل چقدر است؟", "تا ۲ گیگابایت، همان سقف خود تلگرام."),
    ("لینک تا کی کار می‌کند؟", "تا وقتی خودت غیرفعالش نکنی. در مینی‌اپ ← فایل‌ها ← لینک‌های رایگان می‌توانی هر لینک را خاموش کنی."),
    ("کسی که لینک را باز می‌کند می‌تواند فایل را فوروارد کند؟", "نه؛ محتوا محافظت‌شده تحویل داده می‌شود. برای دیدن دوباره، دوباره روی لینک می‌زند."),
    ("تعداد بازدید لینکم را می‌بینم؟", "بله، با دستور /mylinks یا در مینی‌اپ."),
]

LINK = page_head("رایگان، تا ۲ گیگابایت", "ربات آپلودر تلگرام: ساخت لینک برای هر فایل",
                 "فایل، عکس، ویدیو، موزیک، ویس یا متن را برای ربات بفرست و یک لینک کوتاه بگیر. هر کس لینک را باز کند، فایل را در تلگرام می‌بیند؛ بدون فوروارد شدن و بدون پخش بی‌اجازه.",
                 "ساخت لینک رایگان") + f"""
<section class="section"><div class="wrap narrow prose">
  <h2>چه چیزهایی را می‌شود لینک کرد؟</h2>
  <ul class="kinds"><li>عکس</li><li>ویدیو</li><li>فایل و PDF</li><li>موزیک</li><li>ویس</li><li>ویدیوی دایره‌ای</li><li>گیف</li><li>متن</li></ul>
  <h2>به چه دردی می‌خورد؟</h2>
  <ul class="checklist">
    <li>{CHECK}<span>فرستادن یک فایل به چند نفر با یک لینک، بدون فوروارد پشت‌سرهم.</span></li>
    <li>{CHECK}<span>گذاشتن فایل در کانال یا گروه بدون اینکه پخش آزاد شود.</span></li>
    <li>{CHECK}<span>دیدن تعداد بازدید هر لینک.</span></li>
    <li>{CHECK}<span>خاموش کردن لینک هر وقت خواستی.</span></li>
  </ul>
  <p>اگر خواستی همان فایل را بفروشی، <a href="/sell/">فروشگاه بساز</a>؛ لینک‌های پولی از ربات فروشگاه خودت ساخته می‌شوند.</p>
</div></section>
""" + cta_band("اولین لینکت را بساز", "یک فایل برای ربات بفرست؛ همین.", "باز کردن ربات")

SHOWCASE_FAQ = [
    ("چطور در تلگرام کانال VIP پولی بسازم؟", "یک ویترین با «اشتراک ماهانه» بساز و پست‌های ویژه‌ات را در آن بگذار. عضوها با استارز می‌پردازند، تلگرام هر ماه خودکار تمدید می‌کند و پول مستقیم به ربات خودت می‌رسد؛ بدون کارت‌به‌کارت و بدون اضافه کردن دستی اعضا."),
    ("ویترین با لینک یک محصول چه فرقی دارد؟", "لینک محصول یک فایل را می‌فروشد؛ ویترین صفحه‌ی همه‌ی محصولات توست، با ظاهر دلخواه، مناسب برای بیو اینستاگرام."),
    ("می‌توانم ویترین خصوصی داشته باشم؟", "بله. ویترین خصوصی فقط با لینک خودش باز می‌شود و در هیچ فهرستی دیده نمی‌شود."),
    ("اشتراک ماهانه چطور تمدید می‌شود؟", "خود تلگرام هر ۳۰ روز تمدید می‌کند. سه روز قبل یادآوری می‌آید و عضو هر وقت بخواهد تمدید را خاموش می‌کند."),
]

SHOWCASE = page_head("ویترین و لینک بیو اینستاگرام", "یک صفحه برای همه‌ی محصولاتت؛ مخصوص بیو اینستاگرام",
                     "ویترین مثل Linktree است، ولی داخل تلگرام و با پرداخت استارز: محصولاتت را کنار هم نشان بده، ورود را رایگان، یک‌بار یا ماهانه کن و لینکش را در بیو بگذار.",
                     "ساخت ویترین") + f"""
<section class="section"><div class="wrap narrow prose">
  <h2>سه نوع ورود</h2>
  <div class="mini-cards">
    <div><b>رایگان</b><p>همه می‌بینند؛ هر محصول قیمت خودش را دارد.</p></div>
    <div><b>یک‌بار پرداخت</b><p>یک بار می‌پردازند و برای همیشه عضو می‌شوند.</p></div>
    <div><b>اشتراک ماهانه</b><p>تمدید خودکار تلگرام؛ مثل کانال VIP ولی بدون زحمت.</p></div>
  </div>
  <h2>ظاهرش را خودت بچین</h2>
  <ul class="checklist">
    <li>{CHECK}<span>۴ تم (ملایم، غروب، شفق، شب طلایی) و ۷ رنگ</span></li>
    <li>{CHECK}<span>بنر، لوگو و عکس پس‌زمینه</span></li>
    <li>{CHECK}<span>چیدمان پست، شبکه‌ای، اینستاگرامی یا لیست</span></li>
    <li>{CHECK}<span>لینک اینستاگرام، کانال، یوتیوب و سایت</span></li>
    <li>{CHECK}<span>کارت استوری اینستاگرام با QR، با یک ضربه</span></li>
  </ul>
</div></section>
""" + cta_band("ویترینت را بساز و لینکش را در بیو بگذار", "ساخت ویترین رایگان است.", "شروع در تلگرام")

STARS_FAQ = [
    ("استارز تلگرام چیست؟", "پول رسمی داخل تلگرام برای پرداخت به ربات‌ها و کانال‌ها. در UploadFly خریدار با استارز می‌پردازد و استارز مستقیم به ربات فروشنده می‌رسد."),
    ("خرید استارز با تومان امن است؟", "اگر فروشنده فقط یوزرنیم تلگرامت را بخواهد، بله. هیچ‌وقت کد ورود یا رمز تلگرامت را به هیچ سایت یا آدمی نده. قیمت‌ها را مقایسه کن و از فروشنده‌ای با نظرات واقعی بخر."),
    ("استارز خریده‌شده را می‌شود دوباره فروخت؟", "نه. طبق قوانین تلگرام فقط استارزی که از فروش درآمده قابل برداشت است؛ استارز خریده‌شده فقط خرج می‌شود."),
    ("برداشت استارز احراز هویت می‌خواهد؟", "ممکن است Fragment در بعضی موارد احراز هویت بخواهد. بار اول با مقدار کم امتحان کن."),
]

STARS = page_head("راهنمای استارز تلگرام", "خرید استارز تلگرام و تبدیل آن به تومان",
                  "استارز چیست، خریدار ایرانی چطور استارز بخرد و فروشنده چطور درآمد استارزی را برداشت و به تومان تبدیل کند.",
                  "شروع در تلگرام") + f"""
<section class="section"><div class="wrap narrow prose">
  <h2>استارز تلگرام چیست و به چه دردی می‌خورد؟</h2>
  <p>استارز (Telegram Stars) پول داخل تلگرام است. با آن به ربات‌ها و کانال‌ها پول می‌دهی: خرید فایل و دوره، عضویت در کانال VIP، حمایت از سازنده‌ها. برای فروشنده، استارز راهی است که از هر کشوری بدون کارت بانکی پول بگیرد و بعد آن را نقد کند.</p>
  <h2>برای خریدار: استارز از کجا بخرم؟</h2>
  <ol>
    <li><b>با تومان (ایران):</b> سایت‌ها و ربات‌هایی هستند که استارز را با پرداخت ریالی می‌فروشند و فقط <b>یوزرنیم تلگرامت</b> را می‌خواهند؛ بعد از پرداخت، استارز به حسابت واریز می‌شود.</li>
    <li><b>داخل خود تلگرام:</b> تنظیمات ← My Stars ← خرید، با کارت بین‌المللی یا پرداخت اپل و گوگل.</li>
  </ol>
  <div class="warn"><b>هشدار امنیتی:</b> هیچ‌وقت کد ورود (Login code) یا رمز تلگرامت را به کسی نده. فروشنده‌ی واقعی استارز فقط یوزرنیم می‌خواهد.</div>
  <p>یوزرنیم نداری؟ در تلگرام: تنظیمات ← Username یکی بساز.</p>
  <h2>برای فروشنده: نقد کردن استارز و تبدیل به تومان</h2>
  <ol>
    <li>هر فروش <b>۲۱ روز</b> بعد قابل برداشت می‌شود و حداقل برداشت معمولاً <b>۱۰۰۰ استارز</b> است (قانون تلگرام).</li>
    <li>در تلگرام، پروفایل ربات فروشگاهت را باز کن: <span class="ltr">Edit → Balance → Withdraw</span>.</li>
    <li>در <b>Fragment</b> استارز به <b>TON</b> (ارز دیجیتال تلگرام) تبدیل و به کیف پولی مثل Tonkeeper واریز می‌شود.</li>
    <li>TON را در یک صرافی ارز دیجیتال که TON دارد به تومان بفروش.</li>
  </ol>
  <p>تا وقتی به ۱۰۰۰ استارز نرسیده‌ای، استارزها در ربات خودت می‌مانند و جایی نمی‌روند. UploadFly هیچ‌وقت پولی نگه نمی‌دارد.</p>
</div></section>
""" + cta_band("آماده‌ی فروش با استارز هستی؟", "فروشگاهت را بساز؛ پول هر فروش مستقیم مال خودت است.", "ساخت فروشگاه")

FAQ_ALL = HOME_FAQ + SELL_FAQ[:3] + LINK_FAQ[:2] + STARS_FAQ[:2] + [
    ("چطور با پشتیبانی تماس بگیرم؟", "در ربات دستور /support را بزن یا در مینی‌اپ ← پروفایل ← پشتیبانی. جواب بیشتر سؤال‌ها همان‌جاست و اگر نبود، مستقیم به پشتیبانی پیام می‌دهی."),
]

FAQ = page_head("سؤال‌های رایج", "سؤال‌های رایج درباره‌ی UploadFly", "پاسخ کوتاه به رایج‌ترین سؤال‌ها درباره‌ی لینک، فروش، پرداخت و امنیت.",
                "شروع در تلگرام") + """<section class="section"><div class="wrap narrow"><p class="center muted">جوابت نبود؟ {SUPPORT}</p></div></section>"""

TERMS = page_head("شرایط استفاده", "شرایط استفاده‌ی UploadFly", "خلاصه‌ی قوانینی که با استفاده از ربات می‌پذیری.", "باز کردن ربات") + """
<section class="section"><div class="wrap narrow prose">
  <ol>
    <li>UploadFly ابزار ساخت لینک و فروشگاه است. هر فروشگاه ربات خود فروشنده است و مسئولیت محتوایش با خود اوست.</li>
    <li>پرداخت با Telegram Stars و مستقیم به ربات فروشنده است؛ UploadFly پولی دریافت یا نگه‌داری نمی‌کند.</li>
    <li>بازپرداخت فقط پیش از باز کردن محتوا و تا ۲۴ ساعت بعد از خرید، حداکثر ۳ بار در ۳۰ روز. ورودی ویترین هم تا وقتی محتوایی از آن باز نشده. اشتراک ماهانه هر وقت لغو شود، تا پایان دوره فعال می‌ماند.</li>
    <li>ممنوع: سلاح، مواد مخدر، قاچاق انسان، کلاهبرداری و <b>هر محتوای جنسی مربوط به کودکان</b> (مسدود شدن دائمی). محتوای بزرگسالان فقط در ربات فروشنده و با علامت «حساس».</li>
    <li>محتوای خریده‌شده محافظت‌شده و فقط برای استفاده‌ی شخصی است.</li>
    <li>مدیران می‌توانند محتوای ناقض قوانین را حذف و فروشگاه یا کاربر را مسدود کنند.</li>
    <li>قوانین Telegram Stars هم برقرار است: <a href="https://telegram.org/tos/stars" rel="noopener">telegram.org/tos/stars</a></li>
  </ol>
  <p>متن کامل و به‌روز در ربات با دستور /terms.</p>
</div></section>"""

PRIVACY = page_head("حریم خصوصی", "حریم خصوصی", "چه اطلاعاتی نگه می‌داریم و چرا.", "باز کردن ربات") + """
<section class="section"><div class="wrap narrow prose">
  <ul>
    <li><b>اطلاعات تلگرام:</b> شناسه‌ی عددی، اسم، یوزرنیم و زبانت؛ برای کار کردن ربات.</li>
    <li><b>فایل‌ها:</b> خود فایل روی سرورهای تلگرام می‌ماند؛ ما فقط شناسه‌ی فایل و مشخصاتش (نوع، حجم، مدت) را نگه می‌داریم.</li>
    <li><b>پرداخت‌ها:</b> شناسه‌ی پرداخت تلگرام برای تحویل و بازپرداخت. اطلاعات کارت و حساب بانکی هیچ‌وقت به ما نمی‌رسد.</li>
    <li><b>توکن ربات فروشنده:</b> رمزنگاری‌شده نگه داشته می‌شود.</li>
    <li><b>منبع آشنایی:</b> اینکه از چه لینکی وارد ربات شدی (مثلاً همین سایت)، برای فهمیدن اینکه کدام معرفی مفید بوده.</li>
  </ul>
  <p>اطلاعاتت را به کسی نمی‌فروشیم. سؤالی داری؟ {SUPPORT}</p>
</div></section>"""

EN = f"""<section class="hero"><div class="wrap hero-in">
  <div class="hero-text">
    <p class="kicker">Telegram file links and selling</p>
    <h1>Send a file, get a link. <span class="hl">Sell it, and the money is yours.</span></h1>
    <p class="lead">Send any file, photo, video, music or text to the bot and get a link instantly. To sell, create your own shop bot in one tap and sell with <strong>Telegram Stars</strong>: automatic, protected delivery, and every Star goes straight to your bot.</p>
    <div class="hero-cta"><a class="btn btn-primary btn-lg" href="{{START}}" rel="noopener">Open in Telegram</a></div>
    <ul class="ticks"><li>{CHECK}Free, no commission</li><li>{CHECK}Paid straight to your own bot</li><li>{CHECK}5 languages</li></ul>
  </div>
  <div class="flow" aria-hidden="true">
    <div class="flow-card"><span class="k k-doc">PDF</span><div><b>course.pdf</b><small>12 MB · 84 pages</small></div></div>
    <div class="flow-arrow"></div>
    <div class="flow-card"><span class="k k-link">🔗</span><div><b>Link ready</b><small>t.me/{{BOT}}?start=…</small></div></div>
    <div class="flow-arrow"></div>
    <div class="flow-card sale"><span class="k k-star">★</span><div><b>New sale: 50 Stars</b><small>Straight to your shop bot</small></div></div>
  </div>
</div></section>
<section class="section" id="links"><div class="wrap">
  <ol class="steps">
    <li><span class="n">1</span><h3>Send</h3><p>Send or forward any file up to 2 GB to the bot.</p></li>
    <li><span class="n">2</span><h3>Get a link</h3><p>A free link to share, or a Stars price to sell. Previews are made by the system.</p></li>
    <li><span class="n">3</span><h3>Share</h3><p>Post it in a channel, group or your Instagram bio. Payment and delivery are automatic.</p></li>
  </ol>
</div></section>
<section class="section globe-sec"><div class="wrap">
  <div class="globe-head"><p class="kicker">Sell without borders</p><h2 class="h2">Your market: Earth</h2><p class="lead">Stars are the shared money of every Telegram user. Buyers in any country pay in a few taps, and the Stars go straight to your own shop bot. Drag the globe to spin it.</p></div>
  <div class="globe" data-globe tabindex="0" role="img" aria-label="Globe with sales flying between countries"><canvas></canvas><p class="globe-hint" aria-hidden="true">Drag to spin</p></div>
  <div class="globe-cells"><div class="globe-cell"><svg class="cell-ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3Z"/></svg><h3>Buyers anywhere</h3><p>Anyone with Telegram can pay with Stars: no bank card or payment gateway needed.</p></div><div class="globe-cell"><svg class="cell-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h9M8.5 3v2M6 5c.6 3.3 2.6 6 6 7.6M11 5c-.8 3.6-3 6.6-6.5 8.4M13 21l4-9 4 9M14.4 18h5.2"/></svg><h3>In their language</h3><p>The bot and Mini App speak 5 languages: Persian, English, Russian, Arabic and Chinese.</p></div><div class="globe-cell"><svg class="cell-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7.5A2.5 2.5 0 0 1 6.5 5H18v3M4 7.5V17a2 2 0 0 0 2 2h14V8H6.5A2.5 2.5 0 0 1 4 7.5Z"/><circle cx="16" cy="13.5" r="1.2"/></svg><h3>Paid to your own bot</h3><p>Every sale, from any country, lands in your shop bot's balance right away.</p></div></div>
</div></section>

<section class="section alt" id="sell"><div class="wrap feature-rows">
  <article class="feature"><h3>Your shop is your own bot</h3><p>Created in one tap and owned by you. Buyers pay your bot directly; we never hold your money.</p></article>
  <article class="feature"><h3>Protected content</h3><p>Buyers can't forward or save what they bought. Real file specs and system-made previews build trust.</p></article>
  <article class="feature"><h3>Showcases and memberships</h3><p>A Linktree-style page for your bio: free, one-time entry or a monthly membership renewed by Telegram.</p></article>
  <article class="feature"><h3>Fair for buyers</h3><p>One-tap refunds before opening the content, problem reports and ratings from real buyers only.</p></article>
</div></section>
""" + cta_band("Try it now", "It's free and takes a minute. All you need is Telegram.", "Open in Telegram")

EN_FAQ = [
    ("Is UploadFly free?", "Yes. Links, shops and sales are free, and UploadFly takes no commission."),
    ("Where does the money go?", "Straight into your own shop bot's balance. Only you can withdraw it, through Telegram and Fragment."),
    ("Can buyers forward my files?", "No. All content is delivered protected: Telegram's forward and save buttons are disabled."),
]

NOT_FOUND = """<section class="hero hero-page"><div class="wrap narrow center">
  <p class="kicker">۴۰۴</p><h1>این صفحه پیدا نشد</h1><p class="lead">شاید آدرس اشتباه است. از صفحه‌ی اصلی شروع کن.</p>
  <div class="hero-cta center"><a class="btn btn-primary btn-lg" href="/">صفحه‌ی اصلی</a><a class="btn btn-ghost btn-lg" href="{START}" rel="noopener">باز کردن ربات</a></div>
</div></section>"""

PAGES = [
    {"key": "home", "lang": "fa", "slug": "/", "tag": "home", "priority": "1.0", "faq": HOME_FAQ, "body": HOME,
     "title": "UploadFly | ربات آپلودر و فروش فایل در تلگرام با استارز",
     "description": "هر فایل را برای ربات بفرست و لینک بگیر. فروشگاه رایگان بساز و فایل، دوره و محتوای VIP را با استارز تلگرام بفروش؛ تحویل خودکار و پول مستقیم به ربات خودت."},
    {"key": "home", "lang": "en", "slug": "/en/", "tag": "en", "priority": "0.8", "faq": EN_FAQ, "body": EN,
     "title": "UploadFly | Telegram file links and selling with Stars",
     "description": "Send any file to the bot and get a link. Create a free shop and sell files, courses and memberships with Telegram Stars, paid straight to your own bot."},
    {"key": "sell", "lang": "fa", "slug": "/sell/", "tag": "sell", "priority": "0.9", "faq": SELL_FAQ, "body": SELL, "crumb": "فروش فایل",
     "title": "فروش فایل در تلگرام با استارز، بدون کارت‌به‌کارت | UploadFly",
     "description": "دوره، جزوه، قالب و هر فایلی را در تلگرام بفروش: تحویل خودکار و محافظت‌شده، بازپرداخت دکمه‌ای و پول مستقیم به ربات فروشگاه خودت. رایگان و بدون سهم از فروش."},
    {"key": "link", "lang": "fa", "slug": "/free-link/", "tag": "link", "priority": "0.8", "faq": LINK_FAQ, "body": LINK, "crumb": "ساخت لینک فایل",
     "title": "ربات آپلودر تلگرام رایگان: ساخت لینک فایل | UploadFly",
     "description": "ربات آپلودر رایگان تلگرام: برای هر فایل، عکس، ویدیو یا موزیک لینک بساز؛ محافظت‌شده، بدون فوروارد و با آمار بازدید. تا ۲ گیگابایت."},
    {"key": "showcase", "lang": "fa", "slug": "/showcase/", "tag": "showcase", "priority": "0.8", "faq": SHOWCASE_FAQ, "body": SHOWCASE,
     "crumb": "ویترین", "title": "لینک بیو اینستاگرام و کانال VIP در تلگرام | UploadFly",
     "description": "ویترین UploadFly: یک صفحه برای همه‌ی محصولاتت مثل Linktree، برای لینک بیو اینستاگرام؛ یا کانال VIP با اشتراک ماهانه‌ی استارز و تمدید خودکار."},
    {"key": "stars", "lang": "fa", "slug": "/telegram-stars/", "tag": "stars", "priority": "0.8", "faq": STARS_FAQ, "body": STARS,
     "crumb": "راهنمای استارز", "title": "خرید استارز تلگرام با تومان و تبدیل به پول | راهنمای کامل",
     "description": "استارز تلگرام چیست، چطور با تومان استارز بخریم و فروشنده چطور درآمد استارزی را از Fragment برداشت و به تومان تبدیل کند. همراه با نکات امنیتی."},
    {"key": "faq", "lang": "fa", "slug": "/faq/", "tag": "faq", "priority": "0.6", "faq": FAQ_ALL, "body": FAQ, "crumb": "سؤال‌های رایج",
     "title": "سؤال‌های رایج UploadFly | لینک، فروش و استارز",
     "description": "پاسخ رایج‌ترین سؤال‌ها درباره‌ی ساخت لینک، فروش فایل، پرداخت با استارز، بازپرداخت و امنیت در UploadFly."},
    {"key": "terms", "lang": "fa", "slug": "/terms/", "tag": "terms", "priority": "0.3", "body": TERMS, "crumb": "شرایط استفاده",
     "title": "شرایط استفاده | UploadFly", "description": "قوانین استفاده از ربات UploadFly: پرداخت، بازپرداخت، محتوای ممنوع و مسئولیت فروشنده."},
    {"key": "privacy", "lang": "fa", "slug": "/privacy/", "tag": "privacy", "priority": "0.3", "body": PRIVACY, "crumb": "حریم خصوصی",
     "title": "حریم خصوصی | UploadFly", "description": "UploadFly چه اطلاعاتی نگه می‌دارد، چرا و چطور از آن محافظت می‌کند."},
    {"key": "404", "lang": "fa", "slug": "/404.html", "tag": "404", "noindex": True, "body": NOT_FOUND,
     "title": "صفحه پیدا نشد | UploadFly", "description": "این صفحه وجود ندارد."},
]
