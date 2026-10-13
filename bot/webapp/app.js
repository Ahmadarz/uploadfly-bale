// UploadFly Mini App — خانه + محصولات + ویرایشگر محصول
const tg = window.Telegram && window.Telegram.WebApp;
const params = new URLSearchParams(location.search);
const VIA_BOT = params.get("bot") || "";      // وقتی از دکمه‌ی ربات فروشنده باز شده
const OPEN_PRODUCT = params.get("p");         // باز کردن مستقیم یک محصول
let STORE = params.get("store");              // ویترین یک فروشگاه (برای خریدار)
let SC = params.get("sc");                    // یکی از ویترین‌های اضافه‌ی همان فروشگاه
let storeFromHome = false;                    // ویترین از داخل داشبورد فروشنده باز شده (دکمه‌ی برگشت)

// زبان‌ها؛ متن هر زبان در webapp/i18n/<lang>.json است (یک فایل برای هر زبان)
const LANGS = {
  fa: { name: "فارسی", dir: "rtl", locale: "fa-IR" },   // نسخه‌ی بله فقط فارسی است
};
const ASSET_V = (document.querySelector('script[src*="/static/app.js"]')?.src.match(/v=(\d+)/) || [])[1] || "0";
const dicts = {};

let lang = "fa";
let me = null;
// t("sales", 3) → «۳ فروش»: مقدارها به ترتیب جای {n}، {b}، … می‌نشینند
// t("premium_confirm", { s: 1000, n: 3 }) → با نام؛ امن وقتی ترتیب جای خالی‌ها در زبان‌ها فرق دارد
const num = (n) => (typeof n === "number" ? n.toLocaleString("en-US") : n);
const toman = (n) => `${num(Number(n) || 0)} تومان`;
// خانه‌های کوچک آمار: مبلغ میلیونی کوتاه می‌شود («12.5» و زیرش «میلیون تومان») تا در خانه جا شود
function shortSum(id, n) {
  n = Number(n) || 0;
  const [div, unit] = n >= 1e9 ? [1e9, "unit_billion"] : n >= 1e6 ? [1e6, "unit_million"] : [1, "unit_toman"];
  $(id).textContent = div === 1 ? num(n) : String(Math.floor(n / (div / 100)) / 100);
  $(id).nextElementSibling.textContent = t(unit);
}
const t = (key, ...args) => {
  let v = dicts[lang]?.[key] ?? dicts.en?.[key] ?? key;
  if (typeof v === "string" && args.length === 1 && args[0] && typeof args[0] === "object") {
    return v.replace(/\{(\w+)\}/g, (m, name) => (name in args[0] ? num(args[0][name]) : m));
  }
  if (typeof v === "string" && args.length) {
    [...new Set([...v.matchAll(/\{(\w+)\}/g)].map((m) => m[1]))].forEach((name, i) => { v = v.split(`{${name}}`).join(num(args[i])); });
  }
  return v;
};
async function loadDict(l) {
  if (dicts[l]) return;
  const res = await fetch(`/static/i18n/${l}.json?v=${ASSET_V}`);
  dicts[l] = await res.json();
}
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// متن خطای سرور؛ اگر ترجمه‌ای برای این کد نیست، خطای عمومی (نه خود کد)
const errMsg = (code, ...args) => ((dicts[lang]?.[`err_${code}`] ?? dicts.en?.[`err_${code}`]) ? t(`err_${code}`, ...args) : t("err_generic"));
const haptic = (type) => { try { tg.HapticFeedback.notificationOccurred(type); } catch (e) { /* قدیمی */ } };

async function applyLang(l) {
  lang = "fa";
  try { await loadDict(lang); } catch (e) { /* بدون اینترنت: کلیدها نمایش داده می‌شوند */ }
  document.documentElement.lang = lang;
  document.documentElement.dir = LANGS[lang].dir;
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  // متن‌های راهنما با فهرست و پررنگ (فقط از فایل‌های ترجمه‌ی خودمان، نه از کاربر)
  document.querySelectorAll("[data-i18n-html]").forEach((el) => { el.innerHTML = t(el.dataset.i18nHtml); });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
}

const tap = () => { try { tg.HapticFeedback.selectionChanged(); } catch (e) { /* قدیمی */ } };
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// تم: همان روشن/تیره‌ی تلگرام کاربر (design.md § Theme)
const THEME_BG = { light: "#e9ebf3", dark: "#15161b" };
const THEME_ACCENT = { light: "#5b5bd6", dark: "#7c7cf8" };
function applyTheme() {
  const scheme = tg?.colorScheme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.dataset.theme = scheme;
  paintChrome();
}

// شمارش عدد از ۰ تا مقدار نهایی (یک بار، کوتاه)
function countUp(el, to) {
  if (typeof to !== "number" || reducedMotion()) { el.textContent = num(to) ?? "?"; return; }
  const start = performance.now(), dur = 700;
  const step = (now) => {
    const k = Math.min(1, (now - start) / dur), eased = 1 - Math.pow(1 - k, 3);
    el.textContent = num(Math.round(to * eased));
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function showError(key) {
  $("error-text").textContent = t(key);
  $("splash").classList.add("hidden");
  $("error").classList.remove("hidden");
}

let toastTimer;
function toast(text) {
  const el = $("toast");
  el.textContent = text; el.classList.add("show");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove("show"), 2800);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      Authorization: `tma ${tg.initData}`, "X-Bot-Id": VIA_BOT,
      "X-TZ-Offset": String(-new Date().getTimezoneOffset()),
      ...(options.body ? { "Content-Type": "application/json" } : {}),
    },
  });
  if (!res.ok) {
    let code = "generic";
    try { code = (await res.json()).error || code; } catch (e) { /* بدنه‌ی غیر JSON */ }
    const err = new Error(code); err.code = code; err.status = res.status; throw err;
  }
  return res.headers.get("Content-Type")?.includes("json") ? res.json() : res.blob();
}

// خطاهای گوشی واقعی به لاگ سرور می‌رود تا باگ‌هایی که فقط در تلگرام پیش می‌آیند دیده شوند
let reported = 0;
function reportError(message, where) {
  if (reported++ > 10 || !tg.initData) return;
  const page = document.querySelector(".page.active")?.id || "";
  fetch("/api/client-error", { method: "POST", headers: { Authorization: `tma ${tg.initData}`, "X-Bot-Id": VIA_BOT,
    "Content-Type": "application/json" }, body: JSON.stringify({ message: String(message).slice(0, 300), where: String(where || "").slice(0, 300), page }) })
    .catch(() => {});
}
window.addEventListener("error", (e) => reportError(e.message, `${(e.filename || "").split("/").pop()}:${e.lineno}:${e.colno}`));
window.addEventListener("unhandledrejection", (e) => {
  const r = e.reason || {};
  if (r.status && r.status < 500) return;  // خطاهای عادی API (مثلاً «موجودی کافی نیست») باگ نیستند
  reportError(r.message || r, (r.stack || "").split("\n").slice(0, 3).join(" < "));
});

// بله لینک «اشتراک‌گذاری» مثل t.me/share ندارد: برگه‌ی اشتراک خود گوشی، و اگر نبود کپی لینک
async function shareLink(link, text) {
  tap();
  try { if (navigator.share) { await navigator.share(text ? { text, url: link } : { url: link }); return; } }
  catch (e) { if (e && e.name === "AbortError") return; }
  try { await navigator.clipboard.writeText(link); } catch (e) { /* بدون دسترسی به کلیپ‌بورد */ }
  haptic("success"); toast(t("copied"));
}

function openTelegram(url) {
  if (tg.openTelegramLink) tg.openTelegramLink(url); else window.location.href = url;
}

// ---------------- خانه ----------------
function renderChart(days) {
  const svg = $("chart-bars");
  const max = Math.max(1, ...days.map((d) => d.sum));
  const w = 320 / days.length;
  svg.innerHTML = days.map((d, i) => {
    const h = d.sum ? Math.max(6, (d.sum / max) * 112) : 3;
    const x = i * w + w * 0.2;
    const label = d.sum ? `<text class="bar-label" x="${x + w * 0.3}" y="${136 - h - 6}" text-anchor="middle">${d.sum}</text>` : "";
    return `<rect class="bar${d.sum ? "" : " zero"}" style="animation-delay:${i * 40}ms" x="${x}" y="${136 - h}" width="${w * 0.6}" height="${h}" rx="5"/>${label}`;
  }).join("");
  // فارسی و عربی نام کوتاه ندارند («سه‌شنبه»)؛ تک‌حرفی («س») در عرض گوشی جا می‌شود
  const fmt = new Intl.DateTimeFormat(LANGS[lang].locale, { weekday: LANGS[lang].dir === "rtl" ? "narrow" : "short" });
  $("chart-labels").innerHTML = days.map((d) => `<span>${fmt.format(new Date(d.date + "T12:00:00Z"))}</span>`).join("");
}

function renderHeader() {
  const u = tg.initDataUnsafe.user || {};
  $("hd-name").textContent = me.name || u.first_name || "";
  setAvatar($("hd-avatar"), me.name, u.photo_url);
}

function setAvatar(box, name, photo) {
  box.textContent = (name || "?").trim().charAt(0).toUpperCase();
  if (photo) { const img = new Image(); img.alt = ""; img.onload = () => { box.textContent = ""; box.appendChild(img); }; img.src = photo; }
}

function renderKindTiles(kinds) {
  const entries = Object.entries(kinds || {}).sort((a, b) => b[1] - a[1]);
  $("kinds-box").classList.toggle("hidden", !entries.length);
  $("kind-tiles").innerHTML = entries.map(([k, n], i) => `
    <button class="tile" data-k="${k}" style="animation-delay:${Math.min(i, 8) * 40}ms">
      ${kicon(k)}<b>${esc(t("kinds")[k] || k)}</b><small class="num">${n}</small>
    </button>`).join("");
  $("kind-tiles").querySelectorAll(".tile").forEach((b) => {
    b.onclick = () => { tap(); state.kind = b.dataset.k; state.space = "shop"; switchTabSilently("active"); showPage("page-products"); };
  });
}

function renderTop(top) {
  $("top-box").classList.toggle("hidden", !top.length);
  $("top-list").innerHTML = top.map((p, i) => `
    <div class="row" data-id="${p.id}">
      <b class="num top-rank">${i + 1}</b>
      <div class="thumb" style="${kindStyle(p.kind)}">${iconSvg(p.kind)}</div>
      <span class="purchase-meta"><b>${esc(p.title || t("kinds")[p.kind])}</b><small>${t("top_meta", { n: p.sales, s: p.revenue })}</small></span>
    </div>`).join("");
  $("top-list").querySelectorAll(".row").forEach((r) => {
    const p = top.find((x) => x.id === Number(r.dataset.id));
    if (p.has_thumb) loadImage(`/api/products/${p.id}/thumb`, r.querySelector(".thumb"));
  });
}

function renderRing(balance, min) {
  const pct = min > 0 ? Math.max(0, Math.min(100, Math.round(((balance || 0) / min) * 100))) : 100;
  $("ring-value").style.strokeDashoffset = String(251.3 * (1 - pct / 100));
  $("ring-text").textContent = `${pct}%`;
  $("st-withdraw").textContent = balance >= min ? t("withdraw_ready_short") : t("to_withdraw", min - (balance || 0));
}

function renderHome() {
  const shop = me.shop;
  $("home-seller").classList.toggle("hidden", !shop);
  $("home-none").classList.toggle("hidden", !!shop);
  if (!shop) {
    $("status-text").textContent = t("online");
    $("create-btn").onclick = () => { openTelegram(me.create_link); waitForShop(); };
    $("home-explore").onclick = creator.openExplore;
    creator.renderBanners();
    loadPurchases();
    return;
  }
  $("status-text").textContent = shop.suspended ? t("suspended_short") : `@${shop.bot}`;
  $("status-dot").classList.toggle("red", shop.suspended);
  $("suspended").classList.toggle("hidden", !shop.suspended);
  $("need-wallet").classList.toggle("hidden", shop.wallet !== false);
  $("need-wallet").onclick = () => { tap(); openTelegram(shop.wallet_link); };
  if (!renderHome.counted) { countUp($("st-balance"), shop.balance); renderHome.counted = true; }
  else $("st-balance").textContent = num(shop.balance) ?? "?";
  shortSum("st-today-sum", shop.today_sum);
  $("st-today-n").textContent = t("sales", shop.today_n);
  shortSum("st-total-sum", shop.total_sum);
  $("st-total-n").textContent = t("sales", shop.total_n);
  $("st-links").textContent = shop.links;
  requestAnimationFrame(() => renderRing(shop.balance, me.withdraw_min));
  $("hero-wallet").onclick = () => { tap(); openWallet(); };
  renderKindTiles(shop.kinds);
  renderStart();
  renderTop(shop.top || []);
  loadShowcases();
  renderChart(shop.chart);
  creator.renderTools();
  creator.renderBanners();
  if (typeof orders !== "undefined") orders.renderRow();
}

// بعد از زدن «ساخت فروشگاه»، تلگرام صفحه‌ی ساخت ربات را باز می‌کند؛ تا ۳ دقیقه منتظر می‌مانیم تا فروشگاه وصل شود
let waiting = false;
async function waitForShop() {
  if (waiting) return; waiting = true;
  for (let i = 0; i < 60 && !me.shop; i++) {
    await new Promise((r) => setTimeout(r, 3000));
    try { me = await api("/api/me"); } catch (e) { /* دوباره تلاش */ }
  }
  waiting = false;
  if (me.shop) { haptic("success"); toast(t("shop_ready")); renderHome(); }
}

// ---------------- محصولات ----------------
const KIND_ICONS = {
  video: '<path d="M4 6h11v12H4zM15 10l5-3v10l-5-3z" fill="currentColor"/>',
  animation: '<path d="M4 6h11v12H4zM15 10l5-3v10l-5-3z" fill="currentColor"/>',
  video_note: '<circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2.4"/><path d="M10 9l5 3-5 3z" fill="currentColor"/>',
  audio: '<path d="M9 17V5l11-2v12" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="6.5" cy="17" r="2.5" fill="currentColor"/><circle cx="17.5" cy="15" r="2.5" fill="currentColor"/>',
  voice: '<rect x="9" y="3" width="6" height="11" rx="3" fill="currentColor"/><path d="M5 11a7 7 0 0014 0M12 18v3" fill="none" stroke="currentColor" stroke-width="2"/>',
  document: '<path d="M6 2h8l5 5v15H6z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M14 2v5h5" fill="none" stroke="currentColor" stroke-width="2"/>',
  photo: '<rect x="3" y="5" width="18" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="9" cy="10" r="2" fill="currentColor"/><path d="M21 17l-6-6-8 8" fill="none" stroke="currentColor" stroke-width="2"/>',
  text: '<path d="M5 6h14M5 11h14M5 16h9" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>',
};
const iconSvg = (kind) => `<svg viewBox="0 0 24 24">${KIND_ICONS[kind] || KIND_ICONS.document}</svg>`;
// رنگ هر نوع محتوا از توکن‌ها: --k-photo، --k-photo-soft، ...
const kindVar = (kind) => (KIND_ICONS[kind] ? kind : "document");
const kindStyle = (kind) => `--k: var(--k-${kindVar(kind)}); --k-soft: var(--k-${kindVar(kind)}-soft)`;
const kicon = (kind, cls = "") => `<span class="kicon ${cls}" style="${kindStyle(kind)}">${iconSvg(kind)}</span>`;

const state = { tab: "active", view: savedView(), items: [], current: null, draft: {}, query: "", kind: null, space: "shop", links: [], link: null,
                showcases: [], edShowcases: { main: true, ids: new Set() } };
function savedView() { try { return localStorage.getItem("uf_view") || "list"; } catch (e) { return "list"; } }
const thumbCache = new Map();

async function loadThumb(id, box) {
  try {
    if (!thumbCache.has(id)) thumbCache.set(id, URL.createObjectURL(await api(`/api/products/${id}/thumb`)));
    box.innerHTML = `<img src="${thumbCache.get(id)}" alt="">`;
  } catch (e) { /* آیکن نوع محتوا می‌ماند */ }
}

function fillThumb(box, p) {
  box.classList.remove("skeleton");
  box.setAttribute("style", kindStyle(p.kind));
  // متن: در شبکه چند خط اولش، در لیست آیکن
  if (p.kind === "text") { box.innerHTML = `<div class="txt">${esc(p.text)}</div>${iconSvg(p.kind)}`; return; }
  box.innerHTML = iconSvg(p.kind);
  if (p.has_thumb) loadThumb(p.id, box);
}

function productName(p) { return p.title || p.name || t("kinds")[p.kind] || p.kind; }

function priceChip(p) {
  return p.price ? `<span class="price-chip">${toman(p.price)}</span>` : `<span class="price-chip free">${t("free")}</span>`;
}

function renderProducts() {
  const box = $("products");
  box.className = `products ${state.view}`;
  $("ic-grid").classList.toggle("hidden", state.view !== "grid");
  $("ic-list").classList.toggle("hidden", state.view === "grid");
  const q = state.query.trim().toLowerCase();
  const items = state.items.filter((p) => (!q || productName(p).toLowerCase().includes(q)) && (!state.kind || p.kind === state.kind));
  $("kind-filter").classList.toggle("hidden", !state.kind);
  $("kind-filter-text").textContent = state.kind ? t("kinds")[state.kind] : "";
  const noMatch = state.items.length > 0 && items.length === 0;
  $("products-empty").classList.toggle("hidden", items.length > 0);
  $("empty-text").textContent = noMatch ? t("no_results") : t(`empty_${state.tab}`);
  $("empty-upload").classList.toggle("hidden", noMatch || state.tab === "archived");
  box.innerHTML = items.map((p, i) => `
    <button class="p-card" data-id="${p.id}" style="animation-delay:${Math.min(i, 8) * 40}ms">
      <div class="thumb skeleton"></div>
      <div class="card-info">
        <div class="card-name">${esc(productName(p))}</div>
        <div class="card-meta">${p.rating ? `<span class="rating-num"><svg class="star"><use href="#i-star"/></svg><b class="num">${p.rating.avg}</b></span>` : ""}<span><svg><use href="#i-eye"/></svg><b class="num">${p.views}</b></span><span><svg><use href="#i-cart"/></svg><b class="num">${p.sales}</b></span>${p.reports ? `<span class="red">🚩 <b class="num">${p.reports}</b></span>` : ""}${p.in_store === false && state.tab !== "archived" ? `<span class="link-only"><svg><use href="#i-link"/></svg>${t("link_only")}</span>` : ""}${p.physical ? `<span class="link-only ${p.stock === 0 ? "out" : ""}"><svg><use href="#i-box"/></svg>${p.stock === 0 ? t("post_sold_out") : p.stock == null ? t("ed_physical_tag") : t("ed_stock_n", p.stock)}</span>` : ""}</div>
      </div>
      ${p.sensitive ? '<span class="sens-chip">⏳</span>' : ""}
      ${state.tab === "draft" ? "" : priceChip(p)}
    </button>`).join("");
  box.querySelectorAll(".p-card").forEach((card) => {
    const p = state.items.find((x) => x.id === Number(card.dataset.id));
    fillThumb(card.querySelector(".thumb"), p);
    card.onclick = () => openEditor(p);
  });
}

async function loadProducts() {
  // دو فضا: «فروشگاه» (محصولات) و «لینک‌های رایگان» (ربات اصلی)؛ بدون فروشگاه فقط لینک‌ها
  if (!me.shop) state.space = "free";
  const free = state.space === "free";
  $("space-tabs").classList.toggle("hidden", !me.shop);
  document.querySelectorAll(".space-tab").forEach((b) => b.classList.toggle("active", b.dataset.space === state.space));
  $("products-title").textContent = free ? t("my_links") : t("products");
  for (const id of ["status-tabs", "view-toggle", "products"]) $(id).classList.toggle("hidden", free);
  $("links").classList.toggle("hidden", !free);
  if (free) {
    $("products-empty").classList.add("hidden");
    state.links = (await api("/api/links")).items;
    return renderLinks();
  }
  $("links-empty").classList.add("hidden");
  const data = await api(`/api/products?tab=${state.tab}`);
  state.items = data.items;
  for (const k of ["active", "draft", "archived"]) $(`cnt-${k}`).textContent = data.counts[k] || "";
  renderProducts();
}

function initProducts() {
  document.querySelectorAll("#status-tabs .tab").forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll("#status-tabs .tab").forEach((x) => x.classList.toggle("active", x === b));
      state.tab = b.dataset.tab; loadProducts().catch(() => toast(t("err_generic")));
    };
  });
  $("view-toggle").onclick = () => {
    state.view = state.view === "grid" ? "list" : "grid";
    try { localStorage.setItem("uf_view", state.view); } catch (e) { /* حالت خصوصی */ }
    renderProducts();
  };
  $("empty-upload").onclick = () => me.shop && openTelegram(`https://ble.ir/${me.shop.bot}?start=upload`);
  $("product-search").oninput = (e) => { state.query = e.target.value; state.space === "free" ? renderLinks() : renderProducts(); };
  $("kind-filter").onclick = () => { tap(); state.kind = null; state.space === "free" ? renderLinks() : renderProducts(); };
  document.querySelectorAll(".space-tab").forEach((b) => {
    b.onclick = () => {
      if (state.space === b.dataset.space) return;
      tap(); state.space = b.dataset.space; state.kind = null;
      loadProducts().catch(() => toast(t("err_generic")));
    };
  });
  $("links-upload").onclick = () => { tap(); openTelegram(`https://ble.ir/${me.main_bot}`); };
  $("ls-copy").onclick = async () => { await copyText(state.link.link, $("ls-link")); };
  $("ls-share").onclick = () => shareLink(state.link.link);
  $("ls-open").onclick = () => { tap(); openTelegram(state.link.link); };
  $("ls-disable").onclick = () => tg.showConfirm(t("link_disable_confirm"), async (ok) => {
    if (!ok) return;
    try {
      await api(`/api/links/${state.link.id}/disable`, { method: "POST", body: "{}" });
      haptic("success"); toast(t("link_disabled")); closeLangSheet(); await loadProducts();
    } catch (e) { haptic("error"); toast(t("err_generic")); }
  });
}

// ---------------- ویترین‌ها (فروشنده) ----------------
// هدف: در نگاه اول روشن باشد. خانه: کارت هر ویترین با نوع ورود و دکمه‌ی «لینک بایو»؛ ساخت و ویرایش در ۳ قدم
const scEd = { open: false, id: null, access: "free", products: [], picked: new Map() };

async function loadShowcases() {
  try {
    const data = await api("/api/showcases");
    state.showcases = data.items; state.showcaseMain = data.main;
    renderShowcaseCards();
  } catch (e) { /* خانه بدون کارت‌ها هم کار می‌کند */ }
}

function renderShowcaseCards() {
  const main = state.showcaseMain || { items: 0, link: "" };
  const card = (cls, badge, title, meta, link, attrs) => `
    <button class="sc-card ${cls}" ${attrs}>
      ${badge}<b>${esc(title)}</b><small>${meta}</small>
      <span class="bio-btn" data-link="${esc(link)}"><svg><use href="#i-link"/></svg>${t("sc_bio_link")}</span>
    </button>`;
  $("sc-cards").innerHTML =
    card("free", accessBadge("free", 0), t("sc_main"), t("sc_n_items", main.items), main.link, 'data-main="1"')
    + state.showcases.map((x, i) => card(x.access + (x.archived ? " archived" : ""),
         x.archived ? `<span class="sc-badge">${t("sce_archived_badge")}</span>` : accessBadge(x.access, x.price), x.title,
         x.access === "free" ? t("sc_n_items", x.items) : `${t("sc_n_items", x.items)} · ${t("sc_n_members", x.members)}`,
         x.link, `data-id="${x.id}" style="animation-delay:${(i + 1) * 40}ms"`)).join("")
    + `<button class="sc-card new" id="sc-new-card"><span class="kicon"><svg><use href="#i-plus"/></svg></span><b>${t("sc_new")}</b><small>${t("sc_new_hint")}</small></button>`;
  $("sc-cards").querySelectorAll(".bio-btn").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); copyText(b.dataset.link, b).then(() => { toast(t("sc_bio_copied")); markBioCopied(); }); };
  });
  $("sc-cards").querySelectorAll(".sc-card[data-id]").forEach((c) => { c.onclick = () => { tap(); openShowcaseEditor(Number(c.dataset.id)); }; });
  $("sc-cards").querySelector("[data-main]").onclick = () => { tap(); openStore(me.shop.bot_id, true); };
  $("sc-new-card").onclick = () => { tap(); openShowcaseEditor(null); };
}

// ساخت: سه صفحه (اسم ← نوع ورود ← محتواها) و صفحه‌ی «آماده است». مدیریت: فهرست تنظیمات که هر کدام صفحه‌ی خودش را باز می‌کند
const SCE_STEPS = ["name", "access", "items"];

async function openShowcaseEditor(id) {
  if (!me.shop) return;
  let data;
  try {
    if (id) data = await api(`/api/showcases/${id}`);
    else {
      const items = (await api("/api/products?tab=active")).items;
      data = { id: null, title: "", description: "", access: "free", price: 0, private: false, expires_at: null,
               products: items.map((p) => ({ id: p.id, kind: p.kind, title: productName(p), price: p.price,
                                             has_thumb: p.kind !== "text", included: false, member_free: true })) };
    }
  } catch (e) { return toast(errMsg(e.code)); }
  scEd.data = data;
  scEd.trial = undefined; scEd.bundles = null;   // آزمایشی و بسته‌ها از داده‌ی همین ویترین (creator.js)
  Object.assign(scEd, { open: true, id: data.id, access: data.access, products: data.products, code: data.code, link: data.link,
                        picked: new Map(data.products.filter((p) => p.included).map((p) => [p.id, p.member_free])) });
  $("sce-title").value = data.title || ""; $("sce-desc").value = data.description || "";
  $("sce-price").value = data.price || "";
  $("sce-private").checked = $("sce-private2").checked = !!data.private;
  $("sce-expiry").value = data.expires_at ? localDate(data.expires_at) : "";
  showScePage(id ? "manage" : "name");
  $("overlay").classList.add("open"); $("sc-editor").classList.add("open");
  tg.BackButton.show();
}

// یک صفحه از برگه را نشان می‌دهد و دکمه‌ی پایین تلگرام را مناسب همان صفحه می‌کند
function showScePage(page) {
  scEd.page = page;
  const creating = !scEd.id, step = SCE_STEPS.indexOf(page);
  document.querySelectorAll("#sc-editor .sce-page").forEach((el) => el.classList.toggle("on", el.id === (page === "manage" ? "sce-manage" : `sce-p-${page}`)));
  $("sce-dots").classList.toggle("hidden", !creating || step < 0);
  [...$("sce-dots").children].forEach((d, i) => d.classList.toggle("on", i === step));
  const titles = { name: "sce_new", access: "sce_row_access", items: "sce_row_items", settings: "sce_row_settings", done: "sce_done_heading" };
  $("sce-heading").textContent = page === "manage" ? scEd.data.title : creating && page !== "done" ? t("sce_new") : t(titles[page]);
  if (page === "manage") renderSceManage();
  if (page === "access") renderSceAccess();
  if (page === "items") renderSceItems();
  const mb = tg.MainButton;
  if (page === "manage" || page === "done") mb.hide();
  else { mb.setText(creating ? (page === "items" ? t("sce_create") : t("ob_next")) : t("save")); mb.show(); }
  $("sc-editor").scrollTop = 0;
  if (page === "name" && creating) setTimeout(() => $("sce-title").focus(), 300);
}

function renderSceManage() {
  const d = scEd.data, paid = d.access !== "free";
  $("sce-stats").classList.toggle("hidden", !paid);
  $("sces-canceled").classList.toggle("hidden", !(paid && d.canceled));
  if (paid) {
    $("sces-members").textContent = d.members; $("sces-month").textContent = num(d.month_revenue);
    $("sces-total").textContent = num(d.revenue); $("sces-canceled").textContent = t("sce_canceled", d.canceled);
  }
  $("sce-archived-note").classList.toggle("hidden", !d.archived);
  $("sce-link").textContent = d.link;
  $("sce-v-name").textContent = d.title;
  $("sce-v-access").innerHTML = accessBadge(d.access, d.price);
  $("sce-v-items").textContent = t("sc_n_items", d.items);
  $("sce-v-settings").textContent = [d.private ? t("sce_private_short") : "", d.expires_at ? shortDay(d.expires_at) : ""].filter(Boolean).join(" · ") || t("sce_none");
  $("sce-archive-text").textContent = d.archived ? t("sce_unarchive") : t("sce_archive");
}

function renderSceAccess() {
  const paid = scEd.access !== "free";
  document.querySelectorAll(".access-opt").forEach((b) => b.classList.toggle("active", b.dataset.a === scEd.access));
  $("sce-price-box").classList.toggle("hidden", !paid);
  const cap = me.shop.price_cap, price = Math.floor(Number($("sce-price").value) || 0);
  $("sce-cap").textContent = t("price_cap_hint", cap);
  $("sce-chips").innerHTML = me.presets.filter((v) => v <= cap).map((v) =>
    `<button class="chip ${v === price ? "active" : ""}" data-v="${v}">${toman(v)}</button>`).join("");
  $("sce-chips").querySelectorAll(".chip").forEach((c) => {
    c.onclick = () => { tap(); $("sce-price").value = c.dataset.v; renderSceAccess(); };
  });
  creator.renderSceAccess();
}

function renderSceItems() {
  const paid = scEd.access !== "free";
  $("sce-items-hint").textContent = paid ? t("sce_items_hint_paid") : t("sce_items_hint_free");
  $("sce-no-products").classList.toggle("hidden", scEd.products.length > 0);
  $("sce-items").classList.toggle("hidden", !scEd.products.length);
  $("sce-items").innerHTML = scEd.products.map((p) => {
    const on = scEd.picked.has(p.id), mf = scEd.picked.get(p.id);
    const seg = on && paid ? `<div class="seg" data-mf="${p.id}">
        <button data-v="1" class="${mf ? "active" : ""}">🎁 ${t("free_for_members")}</button>
        <button data-v="0" class="${mf ? "" : "active"}">${t("sc_item_paid", p.price)}</button></div>` : "";
    return `<div class="pick-item"><div class="row ${on ? "on" : ""}" data-id="${p.id}">
      <span class="pick"><svg><use href="#i-check"/></svg></span>
      <div class="thumb" style="${kindStyle(p.kind)}">${iconSvg(p.kind)}</div>
      <span class="purchase-meta"><b>${esc(p.title || t("kinds")[p.kind])}</b><small>${p.price ? `${toman(p.price)}` : t("free")}</small></span>
    </div>${seg}</div>`;
  }).join("");
  $("sce-items").querySelectorAll(".row").forEach((r) => {
    const p = scEd.products.find((x) => x.id === Number(r.dataset.id));
    if (p.has_thumb) loadImage(`/api/products/${p.id}/thumb`, r.querySelector(".thumb"));
    r.onclick = () => { tap(); scEd.picked.has(p.id) ? scEd.picked.delete(p.id) : scEd.picked.set(p.id, true); renderSceItems(); };
  });
  $("sce-items").querySelectorAll(".seg button").forEach((b) => {
    b.onclick = () => { tap(); scEd.picked.set(Number(b.parentElement.dataset.mf), b.dataset.v === "1"); renderSceItems(); };
  });
}

// تاریخ «روز آخر» به وقت محلی → پایان همان روز به UTC
const localDate = (iso) => { const d = new Date(iso); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const endOfDay = (value) => (value ? new Date(`${value}T23:59:59`).toISOString() : null);

function closeShowcaseEditor() {
  scEd.open = false;
  $("overlay").classList.remove("open"); $("sc-editor").classList.remove("open");
  tg.MainButton.hide();
  if (!state.current && !walletOpen()) tg.BackButton.hide();
}

// برگشت: در ساخت یک صفحه عقب؛ در مدیریت از صفحه‌ی تنظیم به فهرست
function sceBack() {
  const i = SCE_STEPS.indexOf(scEd.page);
  if (!scEd.id && i > 0) return showScePage(SCE_STEPS[i - 1]);
  if (scEd.id && scEd.page !== "manage" && scEd.page !== "done") return showScePage("manage");
  closeShowcaseEditor();
}

function sceBody() {
  return { title: $("sce-title").value.trim(), description: $("sce-desc").value.trim(), access: scEd.access,
           price: Math.floor(Number($("sce-price").value) || 0), private: $("sce-private").checked,
           items: [...scEd.picked].map(([id, member_free]) => ({ id, member_free })), ...creator.sceAccessBody() };
}

function sceValid(page) {
  if (page === "name" && !$("sce-title").value.trim()) { haptic("error"); $("sce-title").focus(); toast(t("err_sc_need_title")); return false; }
  if (page === "access" && scEd.access !== "free" && !(Number($("sce-price").value) >= 1)) { haptic("error"); toast(t("err_bad_price")); return false; }
  return true;
}

// دکمه‌ی پایین تلگرام: «بعدی» / «ساخت ویترین» / «ذخیره»
async function sceMain() {
  const page = scEd.page;
  if (!sceValid(page)) return;
  if (!scEd.id && page !== "items") return showScePage(SCE_STEPS[SCE_STEPS.indexOf(page) + 1]);
  let body;
  if (!scEd.id) body = sceBody();
  else if (page === "name") body = { title: $("sce-title").value.trim(), description: $("sce-desc").value.trim() };
  else if (page === "access") body = { access: scEd.access, price: Math.floor(Number($("sce-price").value) || 0), private: $("sce-private").checked, ...creator.sceAccessBody() };
  else if (page === "items") body = { items: sceBody().items };
  else if (page === "settings") body = { private: $("sce-private2").checked, expires_at: endOfDay($("sce-expiry").value) };
  const mb = tg.MainButton; mb.showProgress(); mb.disable();
  try {
    const created = !scEd.id;
    const res = await api(created ? "/api/showcases" : `/api/showcases/${scEd.id}`,
                          { method: created ? "POST" : "PATCH", body: JSON.stringify(body) });
    haptic("success");
    scEd.data = res; scEd.id = res.id; scEd.code = res.code; scEd.link = res.link;
    scEd.trial = undefined; scEd.bundles = null;
    $("sce-private").checked = $("sce-private2").checked = !!res.private;
    loadShowcases();
    if (created) { $("sce-done-link").textContent = res.link; showScePage("done"); }
    else { toast(t("saved")); showScePage("manage"); }
  } catch (e) { haptic("error"); toast(errMsg(e.code, me.shop.price_cap)); }
  finally { mb.hideProgress(); mb.enable(); }
}

async function sceArchive() {
  const archived = !scEd.data.archived;
  const run = async () => {
    try {
      scEd.data = await api(`/api/showcases/${scEd.id}`, { method: "PATCH", body: JSON.stringify({ archived }) });
      haptic("success"); toast(archived ? t("sce_archived_toast") : t("sce_unarchived_toast"));
      renderSceManage(); loadShowcases();
    } catch (e) { haptic("error"); toast(errMsg(e.code)); }
  };
  archived ? tg.showConfirm(t("sce_archive_confirm"), (ok) => ok && run()) : run();
}

function initShowcaseEditor() {
  document.querySelectorAll(".access-opt").forEach((b) => {
    b.onclick = () => { tap(); scEd.access = b.dataset.a; renderSceAccess(); };
  });
  $("sce-price").oninput = () => renderSceAccess();
  $("sc-new").onclick = () => { tap(); openShowcaseEditor(null); };
  document.querySelectorAll("#sce-manage [data-go]").forEach((r) => { r.onclick = () => { tap(); showScePage(r.dataset.go); }; });
  const copy = (node) => copyText(scEd.link, node).then(() => { toast(t("sc_bio_copied")); markBioCopied(); });
  $("sce-copy").onclick = () => copy($("sce-link"));
  $("sce-done-copy").onclick = () => copy($("sce-done-link"));
  $("sce-share").onclick = () => shareLink(scEd.link);
  $("sce-story").onclick = () => { tap(); openStory(scEd.code); };
  $("sce-done-story").onclick = () => { tap(); openStory(scEd.code); };
  $("sce-look").onclick = async () => { tap(); const code = scEd.code; closeShowcaseEditor(); await openStore(me.shop.bot_id, true, code); openLookSheet(); };
  const preview = () => { const code = scEd.code; closeShowcaseEditor(); openStore(me.shop.bot_id, true, code); };
  $("sce-preview").onclick = preview; $("sce-done-view").onclick = preview;
  $("sce-expiry-clear").onclick = () => { tap(); $("sce-expiry").value = ""; };
  $("sce-archive").onclick = sceArchive;
  $("sce-delete").onclick = () => tg.showConfirm(t("sc_delete_confirm"), async (ok) => {
    if (!ok) return;
    try { await api(`/api/showcases/${scEd.id}`, { method: "DELETE" }); haptic("success"); closeShowcaseEditor(); loadShowcases(); }
    catch (e) { haptic("error"); toast(errMsg(e.code)); }
  });
  tg.MainButton.onClick(() => { if (scEd.open && !STORE) sceMain(); });
}

// چیپ‌های ویترین در ویرایشگر محصول: «ویترین اصلی» + ویترین‌های اضافه
function renderEdShowcases() {
  const sel = state.edShowcases;
  $("ed-showcases").innerHTML = `<button class="chip ${sel.main ? "active" : ""}" data-main="1">${t("sc_main")}</button>`
    + state.showcases.map((x) => `<button class="chip ${sel.ids.has(x.id) ? "active" : ""}" data-id="${x.id}">${esc(x.title)}</button>`).join("");
  $("ed-showcases").querySelectorAll(".chip").forEach((c) => {
    c.onclick = () => {
      tap();
      if (c.dataset.main) sel.main = !sel.main;
      else { const id = Number(c.dataset.id); sel.ids.has(id) ? sel.ids.delete(id) : sel.ids.add(id); }
      renderEdShowcases(); syncEditor();
    };
  });
}

// ---------------- لینک‌های رایگان ----------------
const shortDay = (iso) => new Intl.DateTimeFormat(LANGS[lang].locale, { month: "short", day: "numeric" }).format(new Date(iso));
function linkName(l) { return l.title || l.text || t("kinds")[l.kind] || l.kind; }

function renderLinks() {
  const q = state.query.trim().toLowerCase();
  const items = (state.links || []).filter((l) => (!q || linkName(l).toLowerCase().includes(q)) && (!state.kind || l.kind === state.kind));
  $("kind-filter").classList.toggle("hidden", !state.kind);
  $("kind-filter-text").textContent = state.kind ? t("kinds")[state.kind] : "";
  const none = !(state.links || []).length;
  $("links-empty").classList.toggle("hidden", items.length > 0);
  $("links-empty").querySelector("p").textContent = none ? t("links_empty") : t("no_results");
  $("links-upload").classList.toggle("hidden", !none);
  $("links").innerHTML = items.map((l, i) => `
    <button class="p-card" data-id="${l.id}" style="animation-delay:${Math.min(i, 8) * 40}ms">
      <div class="thumb" style="${kindStyle(l.kind)}">${iconSvg(l.kind)}</div>
      <div class="card-info">
        <div class="card-name">${esc(linkName(l))}</div>
        <div class="card-meta"><span><svg><use href="#i-eye"/></svg><b class="num">${l.views}</b></span>${l.created ? `<span>${shortDay(l.created)}</span>` : ""}</div>
      </div>
      <svg class="chev"><use href="#i-chev"/></svg>
    </button>`).join("");
  $("links").querySelectorAll(".p-card").forEach((card) => {
    const l = state.links.find((x) => x.id === Number(card.dataset.id));
    if (l.has_thumb) loadImage(`/api/links/${l.id}/thumb`, card.querySelector(".thumb"));
    card.onclick = () => openLinkSheet(l);
  });
}

function openLinkSheet(l) {
  tap();
  state.link = l;
  const box = $("ls-thumb");
  box.setAttribute("style", kindStyle(l.kind)); box.innerHTML = iconSvg(l.kind);
  if (l.has_thumb) loadImage(`/api/links/${l.id}/thumb`, box);
  $("ls-title").textContent = linkName(l);
  $("ls-meta").innerHTML = [t("kinds")[l.kind], humanSize(l.size), humanDuration(l.duration), t("views_n", l.views)]
    .filter(Boolean).map((x) => `<bdi>${esc(x)}</bdi>`).join(" · ");
  $("ls-link").textContent = l.link;
  openSmallSheet("link-sheet");
}

async function copyText(text, node) {
  try { await navigator.clipboard.writeText(text); }
  catch (e) {  // بعضی نسخه‌های تلگرام اجازه‌ی clipboard نمی‌دهند
    const r = document.createRange(); r.selectNodeContents(node);
    const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); document.execCommand("copy");
  }
  haptic("success"); toast(t("copied"));
}

// ---------------- ویرایشگر ----------------
function humanSize(n) {
  if (!n) return "";
  const u = ["B", "KB", "MB", "GB"]; let i = 0;
  while (n >= 1024 && i < 3) { n /= 1024; i++; }
  return `${i ? n.toFixed(1) : n} ${u[i]}`;
}
function humanDuration(s) {
  if (!s) return "";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(x).padStart(2, "0")}` : `${m}:${String(x).padStart(2, "0")}`;
}

function editorValues() {
  const physical = $("ed-physical").checked;
  return { price: Number($("ed-price").value || 0), sensitive: !physical && $("ed-sensitive").checked,
           physical, stock: physical && $("ed-stock").value !== "" ? Number($("ed-stock").value) : null,
           in_store: state.edShowcases.main, showcases: [...state.edShowcases.ids].sort((a, b) => a - b),
           expires_at: $("ed-expiry").value,
           title: $("ed-title").value.trim(), description: $("ed-desc").value.trim(), category: state.category };
}

function isDirty() {
  const p = state.current, v = editorValues();
  return p.status === "draft" || v.price !== p.price || v.sensitive !== p.sensitive || v.in_store !== p.in_store
    || v.showcases.join() !== [...(p.showcases || [])].sort((a, b) => a - b).join()
    || v.expires_at !== (p.expires_at ? localDate(p.expires_at) : "")
    || v.title !== (p.title || "") || v.description !== (p.description || "") || v.category !== p.category
    || v.physical !== !!p.physical || (v.physical && v.stock !== (p.stock ?? null));
}

function syncEditor() {
  const p = state.current, v = editorValues();
  document.querySelectorAll("#ed-chips .chip").forEach((c) => c.classList.toggle("active", Number(c.dataset.v) === v.price));
  document.querySelectorAll("#ed-cats .chip").forEach((c) => c.classList.toggle("active", c.dataset.c === v.category));
  // کالای فیزیکی: موجودی به‌جای «حساس» (چیزی در چت تحویل نمی‌شود)
  $("ed-stock-box").classList.toggle("hidden", !v.physical);
  $("ed-sensitive-row").classList.toggle("hidden", v.physical);
  const mb = tg.MainButton;
  mb.setText(p.status === "draft" ? t("publish") : t("save"));
  if (isDirty() && p.status !== "archived") mb.show(); else mb.hide();
}

function openEditor(p) {
  state.current = p;
  const thumb = $("ed-thumb"); thumb.className = "ed-thumb thumb skeleton"; fillThumb(thumb, p);
  $("ed-status").textContent = t(`st_${p.status}`);
  $("ed-status").className = `badge ${p.status}`;
  $("ed-name").textContent = productName(p);
  // هر بخش جدا ایزوله می‌شود تا عدد و واحد انگلیسی در متن فارسی به‌هم نریزد
  $("ed-specs").innerHTML = [t("kinds")[p.kind], humanSize(p.size), humanDuration(p.duration),
    p.width && p.height ? `${p.width}×${p.height}` : "", p.pages ? t("pages", p.pages) : ""]
    .filter(Boolean).map((x) => `<bdi>${esc(x)}</bdi>`).join(" · ");
  $("ed-views").textContent = p.views; $("ed-sales").textContent = p.sales; $("ed-revenue").textContent = num(p.revenue);
  $("ed-reports").textContent = p.reports; $("ed-reports-box").classList.toggle("hidden", !p.reports);
  $("ed-preview").classList.toggle("hidden", !p.preview);
  $("ed-preview").textContent = p.preview ? `${t("preview_label")} ${p.preview}` : "";

  const cap = me.shop ? me.shop.price_cap : me.max_price;
  $("ed-cap").textContent = t("price_cap_hint", cap);
  $("ed-price").max = Math.max(cap, p.price);
  $("ed-chips").innerHTML = [0, ...me.presets.filter((v) => v <= cap)].map((v) =>
    `<button class="chip" data-v="${v}">${v ? `${toman(v)}` : t("free")}</button>`).join("");
  $("ed-chips").querySelectorAll(".chip").forEach((c) => {
    c.onclick = () => { $("ed-price").value = c.dataset.v; tg.HapticFeedback?.selectionChanged(); syncEditor(); };
  });
  $("ed-price").value = p.price;
  $("ed-title").value = p.title || ""; $("ed-title").placeholder = p.name || t("kinds")[p.kind];
  $("ed-desc").value = p.description || ""; $("ed-desc-count").textContent = "";
  state.category = p.category;
  $("ed-cats").innerHTML = me.categories.map((c) => `<button class="chip" data-c="${c}">${t("cats")[c]}</button>`).join("");
  $("ed-cats").querySelectorAll(".chip").forEach((b) => {
    // دسته اختیاری است؛ زدن دوباره روی دسته‌ی انتخاب‌شده آن را برمی‌دارد
    b.onclick = () => { state.category = state.category === b.dataset.c ? null : b.dataset.c; tg.HapticFeedback?.selectionChanged(); syncEditor(); };
  });
  $("ed-sensitive").checked = p.sensitive;
  $("ed-physical").checked = !!p.physical;
  $("ed-physical-row").classList.toggle("hidden", p.status !== "draft");   // بعد از انتشار نوع محصول عوض نمی‌شود
  $("ed-stock").value = p.stock ?? "";
  const fee = me.shop ? me.shop.shipping_fee : 0;
  $("ed-ship-note").textContent = fee ? t("ed_ship_note", fee) : t("ed_ship_note_free");
  state.edShowcases = { main: p.in_store, ids: new Set(p.showcases || []) };
  $("ed-expiry").value = p.expires_at ? localDate(p.expires_at) : "";
  renderEdShowcases();

  const published = p.status !== "draft";
  $("ed-link-box").classList.toggle("hidden", !published || p.status === "archived");
  $("ed-link").textContent = p.link;
  $("ed-archive").classList.toggle("hidden", !published);
  $("ed-archive").textContent = p.status === "archived" ? t("restore") : t("archive");

  $("overlay").classList.add("open"); $("editor").classList.add("open");
  tg.BackButton.show();
  syncEditor();
  creator.renderEditor(p);
}

function closeEditor() {
  $("overlay").classList.remove("open"); $("editor").classList.remove("open");
  tg.BackButton.hide(); tg.MainButton.hide();
  state.current = null;
}

async function saveEditor() {
  const p = state.current; if (!p) return;
  const v = editorValues();
  if (!Number.isInteger(v.price) || v.price < 0 || v.price > me.max_price) return toast(t("err_bad_price"));
  const cap = me.shop ? me.shop.price_cap : me.max_price;
  if (v.price > p.price && v.price > cap) { haptic("error"); return toast(t("err_price_cap", cap)); }
  if (v.physical && v.price === 0) { haptic("error"); return toast(t("err_phys_price")); }
  if (v.physical && v.stock !== null && (!Number.isInteger(v.stock) || v.stock < 0 || v.stock > 100000)) { haptic("error"); return toast(t("err_bad_stock")); }
  const body = { sensitive: v.sensitive, in_store: v.in_store, showcases: v.showcases,
                 ...(v.expires_at !== (p.expires_at ? localDate(p.expires_at) : "") ? { expires_at: endOfDay(v.expires_at) } : {}), price: v.price, title: v.title, description: v.description };
  if (v.category !== p.category) body.category = v.category || null;
  if (p.status === "draft") { body.publish = true; body.physical = v.physical; }
  if (v.physical) body.stock = v.stock;
  const mb = tg.MainButton;
  mb.showProgress(); mb.disable();
  try {
    const needsPreview = v.price > 0 && !v.physical && (p.status === "draft" || p.price === 0 || v.sensitive !== p.sensitive);
    const updated = await api(`/api/products/${p.id}`, { method: "PATCH", body: JSON.stringify(body) });
    haptic("success");
    toast(p.status === "draft" ? t("published") : needsPreview ? t("preview_note") : t("saved"));
    thumbCache.delete(p.id);
    closeEditor();
    if (p.status === "draft") switchTab("active"); else await loadProducts();
    refreshHome();
    return updated;
  } catch (e) {
    haptic("error"); toast(errMsg(e.code));
  } finally { mb.hideProgress(); mb.enable(); }
}

async function toggleArchive() {
  const p = state.current; if (!p) return;
  const archived = p.status !== "archived";
  try {
    await api(`/api/products/${p.id}`, { method: "PATCH", body: JSON.stringify({ archived }) });
    haptic("success"); toast(archived ? t("archived_ok") : t("restored_ok"));
    closeEditor(); await loadProducts(); refreshHome();
  } catch (e) { haptic("error"); toast(errMsg(e.code)); }
}

async function copyLink() {
  const link = state.current.link;
  try { await navigator.clipboard.writeText(link); }
  catch (e) {  // بعضی نسخه‌های تلگرام اجازه‌ی clipboard نمی‌دهند
    const r = document.createRange(); r.selectNodeContents($("ed-link"));
    const sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); document.execCommand("copy");
  }
  haptic("success"); toast(t("copied"));
}

function initEditor() {
  $("ed-price").oninput = syncEditor;
  $("ed-title").oninput = syncEditor;
  $("ed-desc").oninput = () => { $("ed-desc-count").textContent = `${$("ed-desc").value.length}/${me.description_max}`; syncEditor(); };
  $("ed-sensitive").onchange = syncEditor;
  $("ed-physical").onchange = () => { tap(); syncEditor(); };
  $("ed-stock").oninput = syncEditor;
  $("ed-expiry").onchange = syncEditor;
  $("ed-expiry-clear").onclick = () => { tap(); $("ed-expiry").value = ""; syncEditor(); };
  $("overlay").onclick = overlayClick;
  $("ed-copy").onclick = copyLink;
  $("ed-share").onclick = () => shareLink(state.current.link);
  $("ed-archive").onclick = toggleArchive;
  // دکمه‌های تلگرام بین ویرایشگر و ویترین مشترک‌اند؛ هر کدام فقط وقتی خودش باز است عمل می‌کند
  tg.MainButton.onClick(() => { if (state.current && !STORE) saveEditor(); });
}

// ---------------- ویترین (خریدار) ----------------
const store = { data: null, cat: null, current: null, view: "feed" };

async function loadImage(url, box) {
  try {
    if (!thumbCache.has(url)) thumbCache.set(url, URL.createObjectURL(await api(url)));
    const extras = [...box.querySelectorAll(".lock-overlay, .post-cta")];  // قفل و دکمه‌ی پست بماند
    box.innerHTML = `<img src="${thumbCache.get(url)}" alt="">`;
    extras.forEach((el) => box.appendChild(el));
  } catch (e) { /* آیکن نوع محتوا می‌ماند */ }
  box.classList.remove("skeleton");
}

function storeCardThumb(box, item) {
  box.classList.remove("skeleton");
  box.setAttribute("style", kindStyle(item.kind));
  if (item.kind === "text" && !item.images) { box.innerHTML = `<div class="txt">${esc(item.snippet)}</div>`; return; }
  box.innerHTML = iconSvg(item.kind);
  if (item.images) loadImage(`/api/store/${STORE}/img/${item.id}/0`, box);
}

// نشان نوع ورود ویترین: رایگان / یک‌بار X / ماهانه X
function accessBadge(access, price) {
  const label = access === "once" ? t("badge_once", price) : access === "monthly" ? t("badge_monthly", price) : t("badge_free");
  return `<span class="sc-badge ${access}">${label}</span>`;
}

function renderStore() {
  const { shop, items } = store.data, sc = store.data.showcase;
  const paid = sc && sc.access !== "free";
  const look = store.data.look || { theme: "soft" }, style = { ...STYLE_DEFAULT, ...(look.style || {}) };
  if (renderStore.lookKey !== JSON.stringify(look)) { renderStore.lookKey = JSON.stringify(look); applyLook(look); }
  paintAvatar($("store-avatar"), look.logo, (shop.owner_name || shop.bot).trim().charAt(0).toUpperCase());
  $("store-owner-tools").classList.toggle("hidden", !shop.is_owner);
  $("store-badge").outerHTML = sc ? accessBadge(sc.access, sc.price).replace('class="sc-badge', 'id="store-badge" class="sc-badge')
    : '<span id="store-badge" class="sc-badge hidden"></span>';
  $("store-name").textContent = sc ? sc.title : (shop.owner_name || `@${shop.bot}`);
  $("store-meta").innerHTML = sc ? `${esc(shop.owner_name || "")} · <bdi>@${esc(shop.bot)}</bdi>` : `<bdi>@${esc(shop.bot)}</bdi>`;
  $("store-desc").classList.toggle("hidden", !sc?.description);
  $("store-desc").textContent = sc?.description || "";
  renderSocial(style.links ? look.links || [] : []);
  document.querySelector("#page-store .profile-stats").classList.toggle("hidden", !style.stats);
  // آمار صفر را نشان نمی‌دهیم («۰ عضو» خریدار را دلسرد می‌کند)
  $("store-n-items").textContent = items.length;
  $("store-n-sales").textContent = shop.sales;
  $("store-n-sales").parentElement.classList.toggle("hidden", !shop.sales);
  $("store-members-box").classList.toggle("hidden", !paid || !sc.members);
  $("store-rating-box").classList.toggle("hidden", !shop.rating);
  if (shop.rating) $("store-rating").textContent = shop.rating.avg;
  if (paid) $("store-n-members").textContent = sc.members;
  // کاور: بنر فروشنده؛ وگرنه در تم ملایم پیش‌نمایش تار اولین محتوای تصویری، در بقیه‌ی تم‌ها گرادیان خود تم
  const cover = $("store-cover"), first = items.find((i) => i.images), token = (renderStore.token = (renderStore.token || 0) + 1);
  const setCover = (u) => { if (token !== renderStore.token) return; cover.classList.add("has-image"); cover.style.backgroundImage = `linear-gradient(transparent, var(--color-scrim)), url(${u})`; };
  cover.classList.remove("has-image"); cover.style.backgroundImage = "";
  if (look.cover) imageUrl(look.cover).then(setCover).catch(() => {});
  else if (first && look.theme === "soft") api(`/api/store/${STORE}/img/${first.id}/0`).then((b) => setCover(URL.createObjectURL(b))).catch(() => {});

  const member = sc && (sc.is_member || sc.is_owner);
  $("store-join-box").classList.toggle("hidden", !paid || member || shop.suspended);
  if (paid) $("store-join").innerHTML = `<svg><use href="#i-lock"/></svg><span>${sc.access === "monthly" ? t("sc_join_monthly", sc.price) : t("sc_join_once", sc.price)}</span>`;
  $("store-member").classList.toggle("hidden", !(paid && sc.is_member));
  if (paid && sc.is_member) {
    const until = sc.expires_at ? shortDay(sc.expires_at) : "";
    $("store-member-note").textContent = !sc.expires_at ? t("sc_member_forever")
      : sc.renewal_canceled ? t("sc_member_ends", until) : t("sc_member_until", until);
    $("store-refund").classList.toggle("hidden", !sc.can_refund);
    $("store-renewal").classList.toggle("hidden", !sc.is_subscription);
    $("store-renewal").textContent = sc.renewal_canceled ? t("sc_renew_on") : t("sc_renew_off");
  }
  $("store-owner-note").classList.toggle("hidden", !shop.is_owner);
  $("store-suspended").classList.toggle("hidden", !shop.suspended);

  // ویترین‌های دیگر همین فروشگاه (و برگشت به ویترین اصلی)
  const others = [...(sc ? [{ code: null, title: t("sc_main"), access: "free" }] : []), ...(store.data.others || [])];
  $("store-others").classList.toggle("hidden", !others.length || !style.others);
  $("store-others-list").innerHTML = others.map((o) =>
    `<button class="chip" data-code="${o.code || ""}">${esc(o.title)} ${o.access !== "free" ? `<span class="sc-badge ${o.access}">${toman(o.price)}</span>` : ""}</button>`).join("");
  $("store-others-list").querySelectorAll(".chip").forEach((b) => {
    b.onclick = () => { tap(); SC = b.dataset.code || null; startStore(); };
  });

  const cats = [...new Set(items.map((i) => i.category).filter(Boolean))];
  $("store-cats").classList.toggle("hidden", cats.length === 0 || !style.cats);
  $("store-cats").innerHTML = [null, ...cats].map((c) =>
    `<button class="chip ${c === store.cat ? "active" : ""}" data-c="${c ?? ""}">${c ? t("cats")[c] : t("all_cats")}</button>`).join("");
  $("store-cats").querySelectorAll(".chip").forEach((b) => {
    b.onclick = () => { store.cat = b.dataset.c || null; tg.HapticFeedback?.selectionChanged(); renderStore(); };
  });

  const fixed = { grid2: "grid", grid3: "grid3", list: "links" }[style.layout];
  if (store.layout !== style.layout) { store.layout = style.layout; store.view = fixed || "feed"; }  // چیدمان تازه‌ی فروشنده
  if (fixed) store.view = fixed;
  else if (!["feed", "grid"].includes(store.view)) store.view = "feed";
  $("store-tabs").classList.toggle("hidden", !!fixed);
  // پست سنجاق‌شده اول
  const shown = items.filter((i) => !store.cat || i.category === store.cat)
    .sort((a, b) => (b.id === style.pinned) - (a.id === style.pinned));
  $("store-empty").classList.toggle("hidden", items.length > 0);
  $("store-n-posts").textContent = items.length || "";
  document.querySelectorAll("#store-tabs .tab").forEach((b) => b.classList.toggle("active", b.dataset.v === store.view));
  const box = $("store-items");
  box.className = `products ${store.view}`;
  const initial = (shop.owner_name || shop.bot).trim().charAt(0).toUpperCase();
  const rating = (i) => (i.rating ? `<span class="rating-num"><svg class="star"><use href="#i-star"/></svg><b class="num">${i.rating.avg}</b></span>` : "");
  // دکمه‌ی وسط تصویر هر پست: قفل عضویت / باز کردن با قیمت / خریدی
  const cta = (i) => i.locked ? `<span class="post-cta lock"><svg><use href="#i-lock"/></svg>${t("post_locked")}</span>`
    : i.unlocked ? `<span class="post-cta own"><svg><use href="#i-eye"/></svg>${t("free_for_members")}</span>`
    : i.bought ? `<span class="post-cta own"><svg><use href="#i-check"/></svg>${t("post_bought")}</span>`
    : i.physical ? `<span class="post-cta buy"><svg><use href="#i-store"/></svg>${t(i.in_stock ? "post_order" : "post_sold_out", i.price)}</span>`
    : i.price ? `<span class="post-cta buy"><svg><use href="#i-lock"/></svg>${t("post_unlock", i.price)}</span>`
    : `<span class="post-cta"><svg><use href="#i-eye"/></svg>${t("get_free")}</span>`;
  const pin = (i) => (i.id === style.pinned ? `<span class="pin-badge"><svg><use href="#i-pin"/></svg>${t("pinned")}</span>` : "");
  const pinCls = (i) => (i.id === style.pinned ? " pinned" : "");
  box.innerHTML = shown.map((i, n) => {
    if (store.view === "links") {  // مثل Linktree: ردیف بزرگ با برچسب وضعیت
      const tag = i.locked ? `<span class="lk-tag lock"><svg><use href="#i-lock"/></svg></span>`
        : i.unlocked ? `<span class="lk-tag own">${t("free_for_members")}</span>`
        : i.bought ? `<span class="lk-tag own"><svg><use href="#i-check"/></svg></span>`
        : `<span class="lk-tag">${i.price ? `${toman(i.price)}` : t("free")}</span>`;
      return `
    <button class="lk-row${pinCls(i)}" data-id="${i.id}" style="animation-delay:${Math.min(n, 8) * 40}ms">
      <span class="lk-thumb"><span class="thumb skeleton"></span></span>
      <span class="lk-text"><b>${esc(i.title || t("kinds")[i.kind])}</b><small>${i.category ? t("cats")[i.category] : t("kinds")[i.kind]}${i.id === style.pinned ? " · " + t("pinned") : ""}</small></span>
      ${tag}
    </button>`;
    }
    if (store.view === "feed") return `
    <button class="post${pinCls(i)}" data-id="${i.id}" style="animation-delay:${Math.min(n, 8) * 40}ms">${pin(i)}
      <div class="post-head"><span class="avatar xs">${esc(initial)}</span><b>${esc(shop.owner_name || "@" + shop.bot)}</b><small>${i.created ? shortDay(i.created) : ""}</small></div>
      ${i.title || i.description ? `<div class="post-text">${i.title ? `<b>${esc(i.title)}</b>` : ""}${i.description ? `<p>${esc(i.description)}</p>` : ""}</div>` : ""}
      <div class="thumb skeleton"></div>
      <div class="post-foot">${rating(i)}<span>${i.category ? t("cats")[i.category] : t("kinds")[i.kind]}</span>${i.sales ? `<span><svg><use href="#i-cart"/></svg><b class="num">${i.sales}</b></span>` : ""}${i.sensitive ? "<span>⏳</span>" : ""}</div>
    </button>`;
    const chip = i.locked ? `<span class="member-chip lock-chip">${t("members_only")}</span>`
      : i.unlocked ? `<span class="member-chip">${t("free_for_members")}</span>` : priceChip(i);
    return `
    <button class="p-card ${i.bought ? "bought" : ""}${pinCls(i)}" data-id="${i.id}" style="animation-delay:${Math.min(n, 8) * 40}ms">${pin(i)}
      <div class="thumb skeleton"></div>
      ${i.locked ? '<span class="lock-overlay"><svg><use href="#i-lock"/></svg></span>' : ""}
      ${chip}
      ${i.sensitive ? '<span class="sens-chip">⏳</span>' : ""}
      ${i.bought && !i.unlocked ? '<span class="owned-badge"><svg><use href="#i-check"/></svg></span>' : ""}
      <div class="card-info">
        <div class="card-name">${esc(i.title || t("kinds")[i.kind])}</div>
        <div class="card-meta">${rating(i)}<span>${i.category ? t("cats")[i.category] : t("kinds")[i.kind]}</span>${i.sales ? `<span><svg><use href="#i-cart"/></svg><b class="num">${i.sales}</b></span>` : ""}</div>
      </div>
    </button>`;
  }).join("");
  box.querySelectorAll("[data-id]").forEach((card) => {
    const item = items.find((x) => x.id === Number(card.dataset.id));
    const thumb = card.querySelector(".thumb");
    storeCardThumb(thumb, item);
    if (store.view === "links" && item.kind === "text" && !item.images) thumb.innerHTML = iconSvg("text");  // متن در ۵۲ پیکسل خوانا نیست
    if (store.view === "feed") {
      if (item.locked) thumb.insertAdjacentHTML("beforeend", '<span class="lock-overlay"></span>');
      thumb.insertAdjacentHTML("beforeend", cta(item));
    }
    card.onclick = () => openBuy(item);
  });
  if (look.logo) box.querySelectorAll(".post-head .avatar").forEach((a) => paintAvatar(a, look.logo, initial));
  creator.renderStore();
}

function openBuy(item) {
  store.current = item;
  const gal = $("buy-gallery");
  const n = Math.max(item.images, item.kind === "text" ? 0 : 1);
  gal.innerHTML = Array.from({ length: n }, () => `<div class="thumb skeleton ${n === 1 ? "single" : ""}" style="${kindStyle(item.kind)}">${iconSvg(item.kind)}</div>`).join("");
  gal.querySelectorAll(".thumb").forEach((box, k) => item.images && loadImage(`/api/store/${STORE}/img/${item.id}/${k}`, box));
  gal.classList.toggle("hidden", n === 0);

  const audio = $("buy-audio");
  audio.classList.toggle("hidden", !item.audio);
  if (item.audio) {
    audio.removeAttribute("src");
    // نوع صدا صریح اعلام می‌شود؛ موتور Safari (تلگرام مک و آیفون) بدون آن پخش نمی‌کند
    api(`/api/store/${STORE}/audio/${item.id}?v=2`)
      .then((b) => { audio.src = URL.createObjectURL(new Blob([b], { type: "audio/mp4" })); audio.load(); })
      .catch(() => audio.classList.add("hidden"));
  }

  $("buy-cat").textContent = item.category ? t("cats")[item.category] : t("kinds")[item.kind];
  $("buy-title").textContent = item.title || t("kinds")[item.kind];
  $("buy-specs").innerHTML = [t("kinds")[item.kind], humanSize(item.size), humanDuration(item.duration),
    item.width && item.height ? `${item.width}×${item.height}` : "", item.pages ? t("pages", item.pages) : "",
    item.sales ? t("sold", item.sales) : ""].filter(Boolean).map((x) => `<bdi>${esc(x)}</bdi>`).join(" · ");
  $("buy-desc-box").classList.toggle("hidden", !item.description);
  $("buy-desc").textContent = item.description || "";
  $("buy-snippet").classList.toggle("hidden", !item.snippet);
  $("buy-snippet").textContent = item.snippet ? `${t("preview_label")} ${item.snippet}` : "";
  $("buy-protect").textContent = t("buy_protect");
  $("buy-sensitive").classList.toggle("hidden", !item.sensitive);

  syncBuyButtons();
  renderRate(item);
  creator.renderBuy(item);
  $("overlay").classList.add("open"); $("buy-sheet").classList.add("open");
  tg.BackButton.show();
}

function renderRate(item) {
  const can = (item.bought || item.unlocked) && item.opened && !store.data.shop.is_owner;
  $("buy-rate").classList.toggle("hidden", !can);
  if (!can) return;
  $("buy-stars").innerHTML = [1, 2, 3, 4, 5].map((n) =>
    `<button class="${n <= (item.my_rating || 0) ? "on" : ""}" data-n="${n}" aria-label="${n}"><svg><use href="#i-star"/></svg></button>`).join("");
  $("buy-stars").querySelectorAll("button").forEach((b) => {
    b.onclick = async () => {
      tap();
      try {
        const res = await api(`/api/store/${STORE}/rate/${item.id}`, { method: "POST", body: JSON.stringify({ stars: Number(b.dataset.n) }) });
        item.my_rating = res.my_rating; item.rating = res.rating;
        haptic("success"); toast(t("rated_toast")); renderRate(item); renderStore();
      } catch (e) { haptic("error"); toast(errMsg(e.code)); }
    };
  });
}

function syncBuyButtons() {
  const item = store.current, mine = store.data.shop.is_owner, sc = store.data.showcase;
  const owned = item.bought && !mine && item.price > 0 && !item.unlocked;
  $("buy-owned").classList.toggle("hidden", !owned);
  $("buy-refund").classList.toggle("hidden", !owned || item.opened);
  $("buy-owned").querySelector("p").textContent = item.opened ? t("owned_hint_opened") : t("owned_hint");
  const mb = tg.MainButton;
  if (item.locked) mb.setText(sc.access === "monthly" ? t("sc_join_monthly", sc.price) : t("sc_join_once", sc.price));
  else if (item.unlocked) mb.setText(t("show_content"));
  else if (item.physical) mb.setText(t("order_btn", item.price));   // کالای فیزیکی: فرم نشانی و پرداخت در چت بازو
  else mb.setText(item.bought ? t("show_content") : item.price ? t("buy_btn", item.price) : t("get_free"));
  if (store.data.shop.suspended && !item.bought && !item.unlocked) mb.hide(); else mb.show();
  $("buy-stars-help").classList.toggle("hidden", mine || item.bought || item.unlocked || !(item.price || item.locked) || store.data.shop.suspended);
}

async function showContent() {
  // محتوا فقط در چت ربات فروشنده تحویل داده می‌شود؛ آن‌جا جلوی ذخیره و فوروارد گرفته می‌شود
  const item = store.current;
  const url = item.unlocked ? `/api/sc/${SC}/open/${item.id}` : `/api/store/${STORE}/open/${item.id}`;
  for (let i = 0; i < 8; i++) {
    try {
      const res = await api(url, { method: "POST", body: "{}" });
      item.opened = true; haptic("success");
      if (item.unlocked && store.data.showcase) store.data.showcase.can_refund = false;
      openTelegram(res.chat); return;
    } catch (e) {
      if (e.code !== "not_paid_yet") { toast(errMsg(e.code)); return; }
      await new Promise((r) => setTimeout(r, 1500));  // پرداخت هنوز به ربات نرسیده
    }
  }
  toast(t("err_generic"));
}

async function refundCurrent() {
  const item = store.current; if (!item) return;
  try {
    const res = await api(`/api/store/${STORE}/refund/${item.id}`, { method: "POST", body: "{}" });
    haptic("success"); toast(t("refunded_toast", res.refunded));
    item.bought = false; item.opened = false; syncBuyButtons(); renderStore();
  } catch (e) { haptic("error"); toast(errMsg(e.code)); }
}

function closeBuy() {
  $("overlay").classList.remove("open"); $("buy-sheet").classList.remove("open");
  if (!storeFromHome) tg.BackButton.hide();
  tg.MainButton.hide(); store.current = null;
  const a = $("buy-audio"); a.pause();
}

// عضویت در ویترین پولی: فاکتور از ربات خود فروشنده؛ بعد از پرداخت صفحه دوباره خوانده می‌شود
async function joinShowcase() {
  if (!SC) return;
  tap();
  try {
    const res = await api(`/api/sc/${SC}/join`, { method: "POST", body: "{}" });
    if (res.member) return reloadStore();
    tg.openInvoice(res.invoice, async (status) => {
      if (status !== "paid") return;
      haptic("success"); toast(t("sc_joined_toast"));
      for (let i = 0; i < 8; i++) {   // پرداخت چند ثانیه طول می‌کشد تا به ربات برسد
        await reloadStore();
        if (store.data.showcase?.is_member) break;
        await new Promise((r) => setTimeout(r, 1500));
      }
      if (store.current) { closeBuy(); }
    });
  } catch (e) { haptic("error"); toast(errMsg(e.code)); }
}

// عضو اشتراک ماهانه: خاموش کردن تمدید (تا آخر دوره عضو می‌ماند) یا روشن کردن دوباره
async function toggleRenewal() {
  const sc = store.data.showcase, cancel = !sc.renewal_canceled;
  const run = async () => {
    try {
      await api(`/api/sc/${SC}/renewal`, { method: "POST", body: JSON.stringify({ cancel }) });
      haptic("success"); toast(cancel ? t("renewal_off_toast") : t("renewal_on_toast")); await reloadStore();
    } catch (e) { haptic("error"); toast(errMsg(e.code)); }
  };
  if (!cancel) return run();
  tg.showConfirm(t("sc_renew_off_confirm", shortDay(sc.expires_at)), (ok) => ok && run());
}

async function refundMembership() {
  tg.showConfirm(t("sc_refund_confirm"), async (ok) => {
    if (!ok) return;
    try {
      const res = await api(`/api/sc/${SC}/refund`, { method: "POST", body: "{}" });
      haptic("success"); toast(t("refunded_toast", res.refunded)); await reloadStore();
    } catch (e) { haptic("error"); toast(errMsg(e.code)); }
  });
}

async function buyCurrent() {
  const item = store.current; if (!item) return;
  if (item.locked) return joinShowcase();
  const mb = tg.MainButton; mb.showProgress(); mb.disable();
  try {
    if (item.bought || item.unlocked) { await showContent(); return; }
    const res = await api(`/api/store/${STORE}/invoice/${item.id}`, { method: "POST", body: "{}" });
    if (res.open) { openTelegram(res.open); return; }  // رایگان یا محصول خود فروشنده: تحویل در چت
    tg.openInvoice(res.invoice, (status) => {
      if (status !== "paid") return;
      // Mini App باز می‌ماند: خریدار همین‌جا «نمایش» یا «بازپرداخت» را انتخاب می‌کند
      haptic("success"); toast(t("paid_toast"));
      item.bought = true; item.opened = false; syncBuyButtons(); renderStore();
      $("buy-sheet").scrollTo({ top: 0, behavior: "smooth" });  // پنل «خریدی» بالای برگه
    });
  } catch (e) {
    haptic("error"); toast(errMsg(e.code));
  }
  finally { mb.hideProgress(); mb.enable(); }
}

let storeHandlersReady = false;

// یک دکمه‌ی برگشت برای کل برنامه: هر بار فقط بالاترین لایه بسته می‌شود
function onBack() {
  if (langSheetOpen() || scEd.open || store.current || state.current) return closeTopSheet();
  if (STORE && storeFromHome) return closeStore();
  if (walletOpen()) return closeWallet();
  if (subPage.current) return closeSubPage();
}

async function reloadStore() {
  store.data = await api(SC ? `/api/sc/${SC}` : `/api/store/${STORE}`);
  renderStore();
}

async function startStore() {
  try { await reloadStore(); } catch (e) { return showError(e.status === 404 ? "sc_not_found" : e.code === "sc_ended" ? "sc_ended" : "load_failed"); }
  document.querySelector(".nav-dock").classList.add("hidden");
  $("status-text").textContent = `@${store.data.shop.bot}`;
  store.cat = null;
  showPage("page-store");
  $("page-store").scrollTop = 0;
  if (storeFromHome) tg.BackButton.show();
  if (storeHandlersReady) return;
  storeHandlersReady = true;
  $("buy-refund").onclick = refundCurrent;
  $("buy-show").onclick = () => { if (store.current) showContent(); };
  $("store-join").onclick = joinShowcase;
  document.querySelectorAll("#store-tabs .tab").forEach((b) => {
    b.onclick = () => { if (store.view === b.dataset.v) return; tap(); store.view = b.dataset.v; renderStore(); };
  });
  $("store-refund").onclick = refundMembership;
  $("store-renewal").onclick = toggleRenewal;
  $("store-made").onclick = () => { tap(); openTelegram(`https://ble.ir/${store.data.main_bot}?start=src_made`); };
  $("store-look").onclick = () => { tap(); openLookSheet(); };
  $("buy-stars-help").onclick = openStarsSheet;
  $("join-stars-help").onclick = openStarsSheet;
  $("store-story").onclick = () => { tap(); openStory(storyFromData(store.data)); };
  $("overlay").onclick = overlayClick;
  tg.MainButton.onClick(() => { if (STORE && store.current) buyCurrent(); });
}

// ویترین داخل داشبورد فروشنده، بدون بستن Mini App
async function openStore(botId, fromHome, code = null) {
  STORE = String(botId); storeFromHome = fromHome; SC = code;
  await startStore();
}

function closeStore() {
  STORE = null; SC = null; storeFromHome = false; store.current = null;
  applyLook(null); renderStore.lookKey = null;
  tg.BackButton.hide(); tg.MainButton.hide();
  document.querySelector(".nav-dock").classList.remove("hidden");
  $("status-text").textContent = me.shop ? `@${me.shop.bot}` : t("online");
  if (creator.backToExplore) {   // از صفحه‌ی کشف آمده بود: برگشت به همان‌جا
    creator.backToExplore = false;
    openSubPage("page-explore"); subPage.from = creator.exploreFrom || "page-home";
    return;
  }
  showPage("page-home");
}

// ---------------- ظاهر ویترین، کارت استوری، چک‌لیست شروع ----------------
const THEMES = ["soft", "sunset", "aurora", "noir"];
const LOOK_CHROME = {  // رنگ سربرگ تلگرام و MainButton برای هر تم
  sunset: { bg: "#fff1ea", accent: "#e23a62", ink: "#ffffff" },
  aurora: { bg: "#0a0f24", accent: "#2ee6c8", ink: "#062320" },
  noir: { bg: "#0c0c0d", accent: "#d9b46a", ink: "#1a1408" },
};
// رنگ‌های کارت استوری (مستقل از تم فعلی صفحه)
const STORY_PALETTE = {
  soft: { bg: ["#eef0f8", "#dde2f3"], card: "#ffffff", ink: "#1c1e3a", ink2: "#575b7d", a: "#5b5bd6", b: "#33c3e8", aInk: "#ffffff" },
  sunset: { bg: ["#ffe1d4", "#f9cde8"], card: "#fffaf7", ink: "#3b1530", ink2: "#74445d", a: "#e23a62", b: "#ff8a3d", aInk: "#ffffff" },
  aurora: { bg: ["#0a0f24", "#1a1450"], card: "#121a36", ink: "#eef2ff", ink2: "#aeb7d8", a: "#2ee6c8", b: "#8b6cff", aInk: "#062320" },
  noir: { bg: ["#0c0c0d", "#24201a"], card: "#161617", ink: "#f6f1e7", ink2: "#c3bba9", a: "#d9b46a", b: "#f2d898", aInk: "#1a1408" },
};

const STYLE_DEFAULT = { card: "round", layout: "feed", accent: "auto", buttons: "fill", pinned: null,
                        stats: true, others: true, cats: true, links: true };
const ACCENTS = { violet: "#5b4fe0", rose: "#d6335a", orange: "#c9560a", green: "#11804f", blue: "#2563eb", gold: "#b98a2a" };
// استایل‌های آماده: یک ضربه، بعد اگر خواست جزئیات را عوض می‌کند
const PRESETS = {
  minimal: { theme: "soft", style: { card: "sharp", layout: "list", buttons: "outline", accent: "auto" } },
  insta: { theme: "soft", style: { card: "sharp", layout: "grid3", buttons: "solid", accent: "rose" } },
  luxury: { theme: "noir", style: { card: "polaroid", layout: "grid2", buttons: "solid", accent: "gold" } },
  colorful: { theme: "sunset", style: { card: "pill", layout: "feed", buttons: "fill", accent: "auto" } },
  glow: { theme: "aurora", style: { card: "round", layout: "list", buttons: "fill", accent: "auto" } },
};

function paintChrome() {
  const root = document.documentElement, look = LOOK_CHROME[root.dataset.look];
  const scheme = root.dataset.theme || "light";
  const bg = look ? look.bg : THEME_BG[scheme];
  try { tg.setHeaderColor(bg); tg.setBackgroundColor(bg); tg.setBottomBarColor(bg); } catch (e) { /* قدیمی */ }
  // MainButton همان رنگ اصلی ویترین (تم یا رنگ انتخابی فروشنده)
  const custom = look || (root.dataset.accent && root.dataset.accent !== "auto");
  const cs = getComputedStyle(root);
  try {
    tg.MainButton.setParams(custom ? { color: cs.getPropertyValue("--color-accent").trim(), text_color: cs.getPropertyValue("--color-accent-ink").trim() }
      : { color: THEME_ACCENT[scheme], text_color: "#ffffff" });
  } catch (e) { /* قدیمی */ }
}

// look = {theme, style} از سرور؛ null = برگشت به ظاهر داشبورد
function applyLook(look) {
  const root = document.documentElement, ds = root.dataset;
  const theme = look?.theme, style = { ...STYLE_DEFAULT, ...(look?.style || {}) };
  if (theme && theme !== "soft" && LOOK_CHROME[theme]) ds.look = theme; else delete ds.look;
  if (look) Object.assign(ds, { card: style.card, btn: style.buttons, accent: style.accent, header: style.header, font: style.font });
  else for (const k of ["card", "btn", "accent", "header", "font"]) delete ds[k];
  // عکس پس‌زمینه (کم‌رنگ زیر محتوا تا نوشته‌ها خوانا بمانند)
  const token = (applyLook.token = (applyLook.token || 0) + 1);
  if (look?.background) {
    imageUrl(look.background).then((u) => {
      if (token !== applyLook.token) return;
      root.style.setProperty("--bg-img", `url(${u})`); ds.bgimg = "";
    }).catch(() => {});
  } else { root.style.removeProperty("--bg-img"); delete ds.bgimg; }
  const dark = ds.look ? ds.look !== "sunset" : ds.theme === "dark";
  if (look && dark) ds.dark = ""; else delete ds.dark;
  paintChrome();
}

const imageCache = new Map();
function imageUrl(id) {
  if (!imageCache.has(id)) imageCache.set(id, api(`/api/images/${id}`).then((b) => URL.createObjectURL(b)));
  return imageCache.get(id);
}

// آواتار ویترین: لوگوی فروشگاه یا حرف اول
function paintAvatar(el, logo, initial) {
  el.textContent = initial;
  if (!logo) return;
  imageUrl(logo).then((u) => { el.innerHTML = `<img src="${u}" alt="">`; }).catch(() => {});
}

const SOCIAL_KINDS = ["instagram", "telegram", "youtube", "x", "tiktok", "website"];
const SOCIAL_ICON = { instagram: "i-instagram", telegram: "i-telegram", youtube: "i-youtube", x: "i-x", tiktok: "i-tiktok", website: "i-globe" };

function renderSocial(links) {
  const row = $("store-social");
  row.classList.toggle("hidden", !links.length);
  row.innerHTML = links.map((l, k) => `<button class="social-btn" data-k="${k}" aria-label="${esc(t("social_" + l.kind))}"><svg><use href="#${SOCIAL_ICON[l.kind]}"/></svg></button>`).join("");
  row.querySelectorAll(".social-btn").forEach((b) => {
    b.onclick = () => {
      tap();
      const url = links[b.dataset.k].url;
      if (/^https:\/\/ble\.ir\//.test(url)) openTelegram(url); else if (tg.openLink) tg.openLink(url); else window.open(url, "_blank", "noopener");
    };
  });
}

// «استارز ندارم؟»: راهنمای خرید، با یوزرنیم خود کاربر برای سایت‌های فروش استارز
function openStarsSheet() {
  tap();
  const username = tg.initDataUnsafe?.user?.username;
  $("stars-user").classList.toggle("hidden", !username);
  $("stars-no-user").classList.toggle("hidden", !!username);
  if (username) {
    $("stars-username").textContent = `@${username}`;
    $("stars-copy").onclick = () => copyText(`@${username}`, $("stars-username"));
  }
  openSmallSheet("stars-sheet");
}

// ---- برگه‌ی ظاهر (فقط صاحب ویترین، روی صفحه‌ی خود ویترین) ----
function lookTarget() { return store.data.showcase ? store.data.showcase.id : null; }

function openLookSheet() {
  if (!store.data?.shop?.is_owner) return;
  renderLookSheet();
  openSmallSheet("look-sheet");
}

let lookTab = "theme";

function renderLookSheet() {
  const look = store.data.look || { theme: "soft" }, style = { ...STYLE_DEFAULT, ...(look.style || {}) };
  const setStyle = (patch) => saveLook({ style: patch });
  document.querySelectorAll("#look-tabs .tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.t === lookTab);
    b.onclick = () => { if (lookTab === b.dataset.t) return; tg.HapticFeedback?.selectionChanged(); lookTab = b.dataset.t; renderLookSheet(); };
  });
  document.querySelectorAll(".look-panel").forEach((p) => p.classList.toggle("on", p.dataset.p === lookTab));
  const opts = (box, key, values, pic) => {
    $(box).innerHTML = values.map((v) => `
      <button class="opt ${style[key] === v ? "active" : ""}" data-v="${v}" aria-pressed="${style[key] === v}">
        <span class="opt-pic ${pic}${v}">${pic === "ol-" ? "<i></i>".repeat({ feed: 2, grid2: 4, grid3: 9, list: 4 }[v])
          : pic === "oh-" ? "<i></i><em></em><i></i>" : "<i></i>"}</span>${t(`${key}_${v}`)}
      </button>`).join("");
    $(box).querySelectorAll(".opt").forEach((b) => {
      b.onclick = () => { if (style[key] !== b.dataset.v) { tg.HapticFeedback?.selectionChanged(); setStyle({ [key]: b.dataset.v }); } };
    });
  };

  if (lookTab === "theme") {
    $("look-presets").innerHTML = Object.entries(PRESETS).map(([k, p]) => `
      <button class="preset" data-k="${k}"><span class="theme-sw sw-${p.theme}"><i></i><i></i><span class="sw-btn"></span></span>${t("preset_" + k)}</button>`).join("");
    $("look-presets").querySelectorAll(".preset").forEach((b) => {
      b.onclick = () => { tap(); const p = PRESETS[b.dataset.k]; saveLook({ theme: p.theme, style: p.style }); };
    });
    $("look-themes").innerHTML = THEMES.map((th) => `
      <button class="theme-opt ${look.theme === th ? "active" : ""}" data-th="${th}" aria-pressed="${look.theme === th}">
        <span class="theme-sw sw-${th}"><i></i><i></i><span class="sw-btn"></span></span>${t("theme_" + th)}
      </button>`).join("");
    $("look-themes").querySelectorAll(".theme-opt").forEach((b) => {
      b.onclick = () => { if (b.dataset.th !== look.theme) { tg.HapticFeedback?.selectionChanged(); saveLook({ theme: b.dataset.th }); } };
    });
    $("look-accents").innerHTML = ["auto", ...Object.keys(ACCENTS)].map((a) => `
      <button class="accent-sw ${a === "auto" ? "auto" : ""} ${style.accent === a ? "active" : ""}" data-a="${a}" aria-label="${t("accent_" + a)}"
        ${a === "auto" ? "" : `style="background:${ACCENTS[a]}"`}>${style.accent === a ? '<svg><use href="#i-check"/></svg>' : ""}</button>`).join("");
    $("look-accents").querySelectorAll(".accent-sw").forEach((b) => {
      b.onclick = () => { if (style.accent !== b.dataset.a) { tg.HapticFeedback?.selectionChanged(); setStyle({ accent: b.dataset.a }); } };
    });
    $("look-font").innerHTML = ["classic", "bold", "light", "plex"].map((f) => `
      <button class="opt ${style.font === f ? "active" : ""}" data-v="${f}" aria-pressed="${style.font === f}">
        <span class="opt-pic of-${f}"><b>${t("font_sample")}</b></span>${t("font_" + f)}</button>`).join("");
    $("look-font").querySelectorAll(".opt").forEach((b) => {
      b.onclick = () => { if (style.font !== b.dataset.v) { tg.HapticFeedback?.selectionChanged(); setStyle({ font: b.dataset.v }); } };
    });
    for (const kind of ["cover", "logo", "background"]) {
      const thumb = $(`look-${kind}-thumb`), id = look[kind];
      thumb.innerHTML = '<svg><use href="#i-image"/></svg>';
      if (id) imageUrl(id).then((u) => { thumb.innerHTML = `<img class="cover-img" src="${u}" alt="">`; }).catch(() => {});
      $(`look-${kind}-del`).classList.toggle("hidden", !id);
      $(`look-${kind}-pick`).onclick = () => { tap(); $("look-file").dataset.kind = kind; $("look-file").click(); };
      $(`look-${kind}-del`).onclick = () => { tap(); saveLook({ [kind]: null }); };
    }
    $("look-file").onchange = async (e) => {
      const file = e.target.files[0]; e.target.value = "";
      if (!file) return;
      const kind = $("look-file").dataset.kind, btn = $(`look-${kind}-pick`);
      btn.classList.add("busy");
      try { await saveLook({ [kind]: await uploadImage(file, kind) }); }
      catch (err) { haptic("error"); toast(errMsg(err.code)); }
      finally { btn.classList.remove("busy"); }
    };
  }
  if (lookTab === "cards") {
    opts("look-card", "card", ["round", "sharp", "pill", "polaroid"], "op-");
    opts("look-buttons", "buttons", ["fill", "solid", "outline"], "ob-");
  }
  if (lookTab === "layout") {
    opts("look-header", "header", ["cover", "center"], "oh-");
    opts("look-layout", "layout", ["feed", "grid2", "grid3", "list"], "ol-");
    const items = store.data.items || [];
    $("look-pin").innerHTML = [`<button class="chip ${style.pinned ? "" : "active"}" data-id="">${t("pin_none")}</button>`,
      ...items.map((i) => `<button class="chip ${style.pinned === i.id ? "active" : ""}" data-id="${i.id}">${esc(i.title || t("kinds")[i.kind])}</button>`)].join("");
    $("look-pin").querySelectorAll(".chip").forEach((b) => {
      b.onclick = () => { tg.HapticFeedback?.selectionChanged(); setStyle({ pinned: b.dataset.id ? Number(b.dataset.id) : null }); };
    });
  }
  if (lookTab === "parts") {
    $("look-switches").innerHTML = ["stats", "others", "cats", "links"].map((k) => `
      <label class="switch-row"><span><b>${t("part_" + k)}</b><small>${t("part_" + k + "_d")}</small></span>
        <input type="checkbox" data-k="${k}" ${style[k] ? "checked" : ""}><i class="switch"></i></label>`).join("");
    $("look-switches").querySelectorAll("input").forEach((inp) => {
      inp.onchange = () => { tg.HapticFeedback?.selectionChanged(); setStyle({ [inp.dataset.k]: inp.checked }); };
    });
    const current = Object.fromEntries((look.links || []).map((l) => [l.kind, l.url]));
    $("look-social").innerHTML = SOCIAL_KINDS.map((k) => `
      <label class="social-field" data-k="${k}"><svg><use href="#${SOCIAL_ICON[k]}"/></svg>
        <input type="url" inputmode="url" autocomplete="off" spellcheck="false" maxlength="200" data-k="${k}"
          placeholder="${esc(t("social_ph_" + k))}" value="${esc(current[k] || "")}"></label>`).join("");
    $("look-social").querySelectorAll("input").forEach((inp) => { inp.onchange = saveSocial; });
  }
}

// همه‌ی لینک‌ها با هم ذخیره می‌شوند؛ لینکِ نامعتبر قرمز می‌شود و پیامش می‌آید
async function saveSocial() {
  const links = [...document.querySelectorAll("#look-social input")].map((i) => ({ kind: i.dataset.k, url: i.value.trim() }));
  document.querySelectorAll("#look-social .social-field").forEach((f) => f.classList.remove("bad"));
  try {
    store.data.look = await api("/api/look", { method: "PATCH", body: JSON.stringify({ sc: lookTarget(), links }) });
    haptic("success"); renderStore();
  } catch (e) {
    haptic("error");
    const kind = (e.code || "").startsWith("bad_link_") ? e.code.slice(9) : null;
    if (kind) document.querySelector(`#look-social .social-field[data-k="${kind}"]`)?.classList.add("bad");
    toast(kind ? t("err_bad_link", t("social_" + kind)) : errMsg(e.code));
  }
}

async function saveLook(patch) {
  try {
    store.data.look = await api("/api/look", { method: "PATCH", body: JSON.stringify({ sc: lookTarget(), ...patch }) });
    haptic("success");
    renderStore(); renderLookSheet();
    if (me.shop) me.shop.has_look = true;
  } catch (e) { haptic("error"); toast(errMsg(e.code)); }
}

// عکس در خود گوشی کوچک می‌شود (آپلود سریع از اینترنت کند)؛ سرور دوباره آن را می‌سازد
async function uploadImage(file, kind) {
  const max = kind === "logo" ? 800 : kind === "background" ? 2000 : 1800;
  let src;
  try { src = await createImageBitmap(file, { imageOrientation: "from-image" }); }
  catch (e) {
    src = await new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = URL.createObjectURL(file); })
      .catch(() => { const err = new Error("bad_image"); err.code = "bad_image"; throw err; });
  }
  const w = src.width, h = src.height, k = Math.min(1, max / Math.max(w, h));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(w * k); canvas.height = Math.round(h * k);
  canvas.getContext("2d").drawImage(src, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((res) => canvas.toBlob(res, "image/jpeg", 0.9));
  const r = await fetch(`/api/images?kind=${kind}`, { method: "POST", body: blob,
    headers: { Authorization: `tma ${tg.initData}`, "X-Bot-Id": VIA_BOT, "Content-Type": "image/jpeg" } });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { const err = new Error(data.error || "generic"); err.code = data.error || "generic"; throw err; }
  return data.id;
}

// ---- کارت استوری اینستاگرام (۱۰۸۰×۱۹۲۰) ----
let storyState = null;

async function storySource(code) {  // code: null = ویترین اصلی
  const data = code ? await api(`/api/sc/${code}`) : await api(`/api/store/${me.shop.bot_id}`);
  return storyFromData(data);
}

function storyFromData(d) {
  const sc = d.showcase;
  return { title: sc ? sc.title : (d.shop.owner_name || `@${d.shop.bot}`), desc: sc?.description || "",
           access: sc ? sc.access : "free", price: sc ? sc.price : 0, link: sc ? sc.link : d.link,
           look: d.look || { theme: "soft" }, initial: (d.shop.owner_name || d.shop.bot).trim().charAt(0).toUpperCase() };
}

async function openStory(src) {
  toast(t("story_making"));
  try {
    const blob = await drawStory(typeof src === "string" || src === null ? await storySource(src) : src);
    if (storyState?.url) URL.revokeObjectURL(storyState.url);
    storyState = { blob, url: URL.createObjectURL(blob), link: (typeof src === "object" && src) ? src.link : null };
    if (!storyState.link) storyState.link = (await storySource(src)).link;
    $("story-img").src = storyState.url;
    $("story-tg").classList.toggle("hidden", !(tg.shareToStory && tg.isVersionAtLeast?.("7.8")));
    $("story-save").onclick = saveStory;
    $("story-copy").onclick = () => { copyText(storyState.link, $("story-copy")); markBioCopied(); };
    $("story-tg").onclick = shareStoryTelegram;
    if (scEd.open) closeShowcaseEditor();
    openSmallSheet("story-sheet");
  } catch (e) { haptic("error"); toast(errMsg(e.code)); }
}

function loadImg(url) {
  return new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = url; });
}

function wrapLines(ctx, text, width, maxLines) {
  const words = String(text).split(/\s+/).filter(Boolean), lines = [];
  let line = "";
  for (const w of words) {
    const test = line ? `${line} ${w}` : w;
    if (ctx.measureText(test).width <= width || !line) line = test;
    else { lines.push(line); line = w; }
    if (lines.length === maxLines) break;
  }
  if (lines.length < maxLines && line) lines.push(line);
  if (lines.length === maxLines && words.join(" ").length > lines.join(" ").length) lines[maxLines - 1] = lines[maxLines - 1].replace(/\s*\S*$/, "") + "…";
  return lines;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

function drawImageCover(ctx, im, x, y, w, h) {
  const k = Math.max(w / im.width, h / im.height), sw = w / k, sh = h / k;
  ctx.drawImage(im, (im.width - sw) / 2, (im.height - sh) / 2, sw, sh, x, y, w, h);
}

async function drawStory(s) {
  // رنگ اصلی انتخابی فروشنده روی کارت استوری هم می‌آید
  const STORY_ACCENT = { violet: ["#5b4fe0", "#8f7cff", "#ffffff"], rose: ["#d6335a", "#ff7a93", "#ffffff"],
    orange: ["#c9560a", "#ff9a3d", "#ffffff"], green: ["#11804f", "#2fc58a", "#ffffff"],
    blue: ["#2563eb", "#38bdf8", "#ffffff"], gold: ["#b98a2a", "#f0cf7a", "#1f1606"] };
  const acc = STORY_ACCENT[s.look.style?.accent];
  const P = { ...(STORY_PALETTE[s.look.theme] || STORY_PALETTE.soft), ...(acc ? { a: acc[0], b: acc[1], aInk: acc[2] } : {}) };
  const W = 1080, H = 1920, c = document.createElement("canvas");
  c.width = W; c.height = H;
  const ctx = c.getContext("2d");
  const root = getComputedStyle(document.documentElement);
  const font = root.getPropertyValue("--font-display").trim() || "system-ui";
  const rtl = lang === "fa" || lang === "ar";
  await Promise.all([document.fonts.load(`700 64px ${font}`, s.title), document.fonts.load(`400 36px ${font}`, s.desc || "a")]).catch(() => {});
  ctx.direction = rtl ? "rtl" : "ltr"; ctx.textAlign = "center"; ctx.textBaseline = "middle";

  // زمینه: عکس پس‌زمینه‌ی فروشنده (کم‌رنگ‌شده) یا گرادیان تم
  let g = ctx.createLinearGradient(0, 0, W, H); g.addColorStop(0, P.bg[0]); g.addColorStop(1, P.bg[1]);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  if (s.look.background) {
    try {
      drawImageCover(ctx, await loadImg(await imageUrl(s.look.background)), 0, 0, W, H);
      ctx.fillStyle = P.bg[0] + "8c"; ctx.fillRect(0, 0, W, H);  // ۵۵٪ رنگ تم روی عکس
    } catch (e) { /* همان گرادیان */ }
  }
  for (const [x, y, r, col] of [[W * 0.9, 120, 620, P.a], [0, H * 0.75, 700, P.b]]) {
    const rg = ctx.createRadialGradient(x, y, 0, x, y, r); rg.addColorStop(0, col + "55"); rg.addColorStop(1, col + "00");
    ctx.fillStyle = rg; ctx.fillRect(0, 0, W, H);
  }
  // کارت (داخل محدوده‌ی امن استوری اینستاگرام: بالا ۲۵۰ و پایین ۳۴۰ پیکسل زیر دکمه‌ها می‌رود)
  const X = 90, Y = 250, CW = W - 2 * X, CH = 1290;
  ctx.save(); ctx.shadowColor = "rgba(0,0,0,0.22)"; ctx.shadowBlur = 60; ctx.shadowOffsetY = 24;
  roundRect(ctx, X, Y, CW, CH, 56); ctx.fillStyle = P.card; ctx.fill(); ctx.restore();
  // بنر
  const BH = 340;
  ctx.save(); roundRect(ctx, X, Y, CW, CH, 56); ctx.clip();
  let coverDone = false;
  if (s.look.cover) { try { drawImageCover(ctx, await loadImg(await imageUrl(s.look.cover)), X, Y, CW, BH); coverDone = true; } catch (e) { /* بدون بنر */ } }
  if (!coverDone) { g = ctx.createLinearGradient(X, Y, X + CW, Y + BH); g.addColorStop(0, P.a); g.addColorStop(1, P.b); ctx.fillStyle = g; ctx.fillRect(X, Y, CW, BH); }
  ctx.restore();
  // لوگو
  const LX = W / 2, LY = Y + BH, LR = 110;
  ctx.beginPath(); ctx.arc(LX, LY, LR + 12, 0, Math.PI * 2); ctx.fillStyle = P.card; ctx.fill();
  ctx.save(); ctx.beginPath(); ctx.arc(LX, LY, LR, 0, Math.PI * 2); ctx.clip();
  let logoDone = false;
  if (s.look.logo) { try { drawImageCover(ctx, await loadImg(await imageUrl(s.look.logo)), LX - LR, LY - LR, LR * 2, LR * 2); logoDone = true; } catch (e) { /* حرف اول */ } }
  if (!logoDone) {
    g = ctx.createLinearGradient(LX - LR, LY - LR, LX + LR, LY + LR); g.addColorStop(0, P.a); g.addColorStop(1, P.b);
    ctx.fillStyle = g; ctx.fillRect(LX - LR, LY - LR, LR * 2, LR * 2);
    ctx.fillStyle = P.aInk; ctx.font = `700 110px ${font}`; ctx.fillText(s.initial, LX, LY + 6);
  }
  ctx.restore();
  // عنوان، نوع ورود، توضیح
  let y = LY + LR + 90;
  ctx.fillStyle = P.ink; ctx.font = `700 68px ${font}`;
  for (const l of wrapLines(ctx, s.title, CW - 120, 2)) { ctx.fillText(l, W / 2, y); y += 86; }
  const badge = s.access === "monthly" ? t("story_monthly", s.price) : s.access === "once" ? t("story_once", s.price) : t("story_free");
  ctx.font = `700 36px ${font}`;
  const bw = ctx.measureText(badge).width + 64;
  roundRect(ctx, W / 2 - bw / 2, y - 6, bw, 64, 32);
  g = ctx.createLinearGradient(W / 2 - bw / 2, 0, W / 2 + bw / 2, 0); g.addColorStop(0, P.a); g.addColorStop(1, P.b);
  ctx.fillStyle = g; ctx.fill(); ctx.fillStyle = P.aInk; ctx.fillText(badge, W / 2, y + 27);
  y += 110;
  if (s.desc) {
    ctx.fillStyle = P.ink2; ctx.font = `400 36px ${font}`;
    for (const l of wrapLines(ctx, s.desc, CW - 160, 2)) { ctx.fillText(l, W / 2, y); y += 52; }
  }
  // QR (همیشه تیره روی سفید تا هر دوربینی بخواند)
  const rows = (await api(`/api/qr?text=${encodeURIComponent(s.link)}`)).rows;
  const QS = 380, QX = W / 2 - QS / 2, QY = Math.max(y + 20, Y + CH - QS - 170);
  roundRect(ctx, QX - 28, QY - 28, QS + 56, QS + 56, 36); ctx.fillStyle = "#ffffff"; ctx.fill();
  const m = QS / rows.length; ctx.fillStyle = "#111318";
  rows.forEach((row, r) => { for (let col = 0; col < row.length; col++) if (row[col] === "1") ctx.fillRect(QX + col * m, QY + r * m, Math.ceil(m), Math.ceil(m)); });
  ctx.fillStyle = P.ink; ctx.font = `700 38px ${font}`;
  ctx.fillText(t("story_scan"), W / 2, QY + QS + 80);
  ctx.direction = "ltr"; ctx.fillStyle = P.ink2; ctx.font = `500 32px ${font}`;
  ctx.fillText(s.link.replace("https://", ""), W / 2, QY + QS + 130);
  // امضا (رشد): بیرون از کارت
  ctx.direction = rtl ? "rtl" : "ltr"; ctx.fillStyle = P.ink2; ctx.font = `500 30px ${font}`;
  ctx.fillText(t("story_made"), W / 2, Y + CH + 70);
  return new Promise((res) => c.toBlob(res, "image/jpeg", 0.92));
}

// تلگرام برای ذخیره و استوری یک آدرس عمومی می‌خواهد؛ عکس موقتاً (۳۰ دقیقه) روی سرور می‌ماند
async function storyPublicUrl() {
  if (storyState.public) return storyState.public;
  const r = await fetch("/api/story", { method: "POST", body: storyState.blob,
    headers: { Authorization: `tma ${tg.initData}`, "X-Bot-Id": VIA_BOT, "Content-Type": "image/jpeg" } });
  if (!r.ok) throw Object.assign(new Error("generic"), { code: "generic" });
  storyState.public = location.origin + (await r.json()).url;
  return storyState.public;
}

async function saveStory() {
  tap();
  if (tg.downloadFile && tg.isVersionAtLeast?.("8.0")) {
    try { tg.downloadFile({ url: await storyPublicUrl(), file_name: "uploadfly-story.jpg" }); return; }
    catch (e) { /* راه دوم */ }
  }
  // بله دانلود فایل ندارد: برگه‌ی اشتراک گوشی (ذخیره در گالری یا مستقیم به اینستاگرام)، اگر مرورگر داخلی اجازه بدهد
  try {
    const file = new File([storyState.blob], "uploadfly-story.jpg", { type: "image/jpeg" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) { await navigator.share({ files: [file] }); return; }
  } catch (e) { if (e && e.name === "AbortError") return; /* کاربر بست؛ وگرنه راه سوم */ }
  toast(t("story_longpress"));
}

async function shareStoryTelegram() {
  tap();
  try { tg.shareToStory(await storyPublicUrl(), { text: storyState.link }); }
  catch (e) { haptic("error"); toast(t("err_generic")); }
}

// ---- چک‌لیست شروع فروشنده (خانه) ----
const START_HIDE = "uf_start_hidden", BIO_DONE = "uf_bio_copied";

function markBioCopied() { storageSet(BIO_DONE, "1"); if (me.shop) renderStart(); }

async function renderStart() {
  const shop = me.shop, card = $("start-card");
  if (!shop || (await storageGet(START_HIDE))) return card.classList.add("hidden");
  const products = Object.values(shop.kinds || {}).reduce((a, b) => a + b, 0);
  const mainLink = `https://ble.ir/${shop.bot}?start=store`;
  const steps = [
    { k: "shop", done: true },
    { k: "wallet", done: shop.wallet !== false, go: () => openTelegram(shop.wallet_link) },
    { k: "product", done: products > 0, go: () => openTelegram(`https://ble.ir/${shop.bot}?start=upload`) },
    { k: "look", done: !!shop.has_look, go: async () => { await openStore(shop.bot_id, true); openLookSheet(); } },
    { k: "bio", done: !!(await storageGet(BIO_DONE)), go: () => copyText(mainLink, $("start-list")).then(() => { toast(t("sc_bio_copied")); markBioCopied(); }) },
    { k: "sale", done: shop.total_n > 0, go: () => openStory(null) },
  ];
  const done = steps.filter((s) => s.done).length;
  if (done === steps.length) return card.classList.add("hidden");
  card.classList.remove("hidden");
  $("start-count").textContent = t("start_n", done, steps.length);
  $("start-bar").style.width = `${(done / steps.length) * 100}%`;
  const next = steps.find((s) => !s.done);
  $("start-list").innerHTML = steps.map((s, i) => `
    <button class="start-step ${s.done ? "done" : ""} ${s === next ? "next" : ""}" data-i="${i}" ${s.done ? "disabled" : ""}>
      <span class="ck">${s.done ? '<svg><use href="#i-check"/></svg>' : i + 1}</span>
      <span class="st"><b>${t("st_" + s.k)}</b><small>${t("st_" + s.k + "_d")}</small></span>
      <svg class="chev"><use href="#i-chev"/></svg>
    </button>`).join("");
  $("start-list").querySelectorAll(".start-step:not(.done)").forEach((b) => { b.onclick = () => { tap(); steps[b.dataset.i].go(); }; });
  $("start-close").onclick = () => { tap(); storageSet(START_HIDE, "1"); card.classList.add("hidden"); };
}

// ---------------- زیرصفحه‌های پروفایل (پشتیبانی، پنل مدیریت) ----------------
const subPage = { current: null, from: null };

function openSubPage(id) {
  const current = document.querySelector(".page.active");
  if (current && current.id !== id) subPage.from = current.id;
  showPage(id);
  subPage.current = id;
  tg.BackButton.show();
}

function closeSubPage() {
  const back = subPage.from || "page-profile";
  subPage.current = null;
  showPage(back);
}

// ---------------- پشتیبانی: سؤالات متداول، بعد چت با حساب پشتیبانی یا ایمیل ----------------
// هر دسته: کلیدهای سؤال/جواب در i18n (help_qN/help_aN؛ دسته‌ی پول همان faq_qN صفحه‌ی اعتماد است)
const HELP = [
  ["start", ["help_q1", "help_q2", "help_q3"]],
  ["sell", ["help_q4", "help_q5", "help_q6", "help_q7"]],
  ["buy", ["help_q8", "help_q9", "help_q10", "help_q11"]],
  ["money", ["faq_q1", "faq_q3", "faq_q4", "faq_q5", "faq_q2"]],
  ["safety", ["help_q12", "help_q13", "help_q14"]],
];
const help = { cat: null, q: "" };

async function openSupport() {
  tap();
  openSubPage("page-support");
  renderHelp();
  const sup = me.support || {};
  $("contact-chat").classList.toggle("hidden", !sup.username);
  $("contact-email").classList.toggle("hidden", !sup.email);
  $("contact-soon").classList.toggle("hidden", !!(sup.username || sup.email));
  $("contact-chat").onclick = () => { tap(); openTelegram(`https://ble.ir/${sup.username}`); };
  $("contact-email").onclick = () => {
    tap();
    const url = `mailto:${sup.email}?subject=${encodeURIComponent("UploadFly")}&body=${encodeURIComponent(`ID: ${tg.initDataUnsafe?.user?.id || ""}\n\n`)}`;
    try { tg.openLink(url); } catch (e) { location.href = url; }
  };
  const uid = String(tg.initDataUnsafe?.user?.id || "");
  $("contact-id").textContent = uid;
  $("contact-id-copy").onclick = () => copyText(uid, $("contact-id"));
  $("help-q").value = help.q;
  $("help-q").oninput = (e) => { help.q = e.target.value.trim(); renderHelp(); };
}

function renderHelp() {
  const norm = (x) => x.toLowerCase().replace(/[يى]/g, "ی").replace(/ك/g, "ک");
  const q = norm(help.q);
  $("help-cats").innerHTML = [null, ...HELP.map(([c]) => c)].map((c) =>
    `<button class="chip ${help.cat === c ? "active" : ""}" data-c="${c ?? ""}">${t(c ? "help_cat_" + c : "all_cats")}</button>`).join("");
  $("help-cats").querySelectorAll(".chip").forEach((b) => {
    b.onclick = () => { tg.HapticFeedback?.selectionChanged(); help.cat = b.dataset.c || null; renderHelp(); };
  });
  const items = HELP.filter(([c]) => !help.cat || help.cat === c).flatMap(([, keys]) => keys)
    .map((k) => [t(k), t(k.replace("_q", "_a"))])
    .filter(([qq, aa]) => !q || norm(qq + " " + aa).includes(q));
  $("help-none").classList.toggle("hidden", items.length > 0);
  $("help-list").classList.toggle("hidden", !items.length);
  $("help-list").innerHTML = items.map(([qq, aa]) => `<details><summary>${esc(qq)}</summary><p>${esc(aa)}</p></details>`).join("");
}

// ---------------- پروفایل ----------------
function renderProfile() {
  const u = tg.initDataUnsafe.user || {};
  setAvatar($("pf-avatar"), me.name, u.photo_url);
  $("pf-name").textContent = me.name || "";
  $("pf-username").innerHTML = me.username ? `<bdi>@${esc(me.username)}</bdi>` : "";
  $("pf-lang-value").textContent = LANGS[lang].name;
  $("pf-lang").classList.add("hidden");  // بله: فقط فارسی

  $("pf-shop").classList.toggle("hidden", !me.shop);
  if (me.shop) {
    const shop = me.shop;
    $("pf-bot").innerHTML = `<bdi>@${esc(shop.bot)}</bdi>`;
    $("pf-open-bot").onclick = () => { tap(); openTelegram(`https://ble.ir/${shop.bot}`); };
    // همه‌ی ویترین‌ها (هر کدام با لینک بیو خودش) یک‌جا در خانه هستند
    $("pf-showcases").onclick = () => { tap(); goHomeShowcases(); };
    $("pf-withdraw").onclick = () => { tap(); openWallet(); };
    $("pf-disconnect").onclick = () => tg.showConfirm(t("disconnect_confirm"), async (ok) => {
      if (!ok) return;
      try { await api("/api/shop/disconnect", { method: "POST", body: "{}" }); haptic("success"); toast(t("disconnected")); await refreshHome(); renderProfile(); }
      catch (e) { haptic("error"); toast(t("err_generic")); }
    });
  }
  $("pf-guide").onclick = () => { tap(); showOnboarding(true); };
  $("pf-support").onclick = openSupport;
  $("pf-explore").onclick = creator.openExplore;
  $("pf-rules").onclick = () => { tap(); $("pf-rules-box").classList.toggle("hidden"); };
  // میانبر روی صفحه‌ی اصلی گوشی (Bot API 8.0)؛ فقط وقتی تلگرام پشتیبانی کند
  if (tg.addToHomeScreen && tg.isVersionAtLeast?.("8.0")) {
    tg.checkHomeScreenStatus?.((status) => $("pf-home-screen").classList.toggle("hidden", status === "added" || status === "unsupported"));
    $("pf-home-screen").onclick = () => { tap(); tg.addToHomeScreen(); };
  }
}

// انتخاب زبان: یک برگه‌ی کوچک به‌جای لیست بلند داخل پروفایل
function openLangSheet() {
  $("pf-langs").innerHTML = Object.entries(LANGS).map(([code, L]) => `
    <button class="row ${code === lang ? "selected" : ""}" data-lang="${code}" lang="${code}">
      <span>${L.name}</span>${code === lang ? '<svg><use href="#i-check"/></svg>' : ""}
    </button>`).join("");
  $("pf-langs").querySelectorAll(".row").forEach((r) => {
    r.onclick = async () => { await setLanguage(r.dataset.lang); closeLangSheet(); };
  });
  openSmallSheet("lang-sheet");
}

// برگه‌های کوچک (زبان، «خودت چک کن»، پرسش‌های رایج): یک باز و بستن مشترک
function openSmallSheet(id) {
  document.querySelectorAll(".small-sheet.open").forEach((x) => x.classList.remove("open"));
  $("overlay").classList.add("open"); $(id).classList.add("open");
  tg.BackButton.show();
}
function closeLangSheet() {
  // اگر برگه‌ی بزرگی (خرید، ویرایشگر) هنوز باز است، پس‌زمینه‌ی تیره‌اش بماند
  if (!state.current && !store.current && !scEd.open) $("overlay").classList.remove("open");
  document.querySelectorAll(".small-sheet.open").forEach((x) => x.classList.remove("open"));
  if (!state.current && !store.current && !walletOpen() && !subPage.current) tg.BackButton.hide();
}
const langSheetOpen = () => !!document.querySelector(".small-sheet.open");

// «پولت دست خودته»: فروشنده موجودی را بدون ما، در خود تلگرام می‌بیند
function openVerify() {
  tap();
  const bot = me?.shop?.bot;
  $("verify-step1").textContent = t("verify_step1", bot ? `@${bot}` : t("verify_your_bot"));
  $("verify-open").classList.toggle("hidden", !bot);
  $("verify-open").onclick = () => { tap(); openTelegram(`https://ble.ir/${bot}`); };
  openSmallSheet("verify-sheet");
}
function openFaq() {
  tap();
  document.querySelectorAll("#faq-sheet details").forEach((d) => { d.open = false; });
  openSmallSheet("faq-sheet");
}
function initTrust() {
  document.querySelectorAll(".js-verify").forEach((b) => { b.onclick = openVerify; });
  document.querySelectorAll(".js-faq").forEach((b) => { b.onclick = openFaq; });
  $("faq-tos").classList.add("hidden");  // مخصوص تلگرام بود
  document.querySelectorAll("#faq-sheet summary").forEach((x) => x.addEventListener("click", tap));
}

// ---------------- کیف پول ----------------
// استارزها در ربات فروشگاهِ خود فروشنده‌اند؛ اینجا واضح نشان می‌دهیم چه مقدار آزاد است و چه مقدار در انتظار
const wallet = { from: "page-home", data: null };
const walletOpen = () => $("page-wallet").classList.contains("active");
const shortDate = (iso) => new Intl.DateTimeFormat(LANGS[lang].locale, { month: "short", day: "numeric" }).format(new Date(iso + "T12:00:00Z"));

async function openWallet() {
  if (!me.shop) return;
  const current = document.querySelector(".page.active");
  if (current && current.id !== "page-wallet") wallet.from = current.id;
  showPage("page-wallet");
  tg.BackButton.show();
  try { renderWallet(await api("/api/wallet")); } catch (e) { toast(t("err_generic")); }
}

function closeWallet() { showPage(wallet.from || "page-home"); }

function renderWallet(w) {
  wallet.data = w;
  creator.renderEarnings(w);
  const avail = w.available ?? 0, min = w.min;
  $("w-balance").textContent = num(w.balance) ?? "?";
  $("w-available").textContent = w.available ?? "?";
  $("w-pending").textContent = w.pending;
  $("w-unlock").textContent = w.next_unlock ? t("wallet_next_unlock", shortDate(w.next_unlock)) : t("wallet_nothing_pending");
  const pct = min > 0 ? Math.max(0, Math.min(100, Math.round((avail / min) * 100))) : 100;  // بله: حداقل برداشت نداریم
  requestAnimationFrame(() => { $("w-ring").style.strokeDashoffset = String(251.3 * (1 - pct / 100)); });
  $("w-ring-text").textContent = `${pct}%`;
  $("w-sub").textContent = avail >= min ? t("withdraw_ready_short") : t("to_withdraw", min - avail);

  // Premium برای خود فروشنده، از موجودی ربات (گران‌ترین = به‌صرفه‌ترین)
  const bal = w.balance ?? 0;
  $("w-premium").innerHTML = w.premium.map((o, i) => `
    <button class="premium-opt ${i === w.premium.length - 1 ? "best" : ""}" data-m="${o.months}" ${bal < o.stars ? "disabled" : ""}>
      <b>${t("premium_months", o.months)}</b>
      <span class="num">${o.stars}<svg><use href="#i-star"/></svg></span>
      <small>${bal >= o.stars ? t("premium_buy") : t("premium_need", o.stars - bal)}</small>
    </button>`).join("");
  $("w-premium").querySelectorAll(".premium-opt").forEach((b) => {
    b.onclick = () => buyPremium(w.premium.find((o) => o.months === Number(b.dataset.m)));
  });

  $("w-withdraw").innerHTML = avail >= min ? t("withdraw_ready", avail, w.bot)
    : `${t("withdraw_wait", avail, min, min - avail)}<div class="bar-track"><i style="width:${pct}%"></i></div>`;

  $("w-sales-empty").classList.toggle("hidden", w.sales.length > 0);
  $("w-sales").classList.toggle("hidden", !w.sales.length);
  $("w-sales").innerHTML = w.sales.map((x) => {
    const [cls, label] = x.refunded ? ["gone", t("wallet_refunded")] : x.unlocked ? ["", t("wallet_unlocked")] : ["wait", t("wallet_locked")];
    return `<div class="row">
      ${kicon(x.kind)}
      <span class="purchase-meta"><b>${esc(x.title || t("kinds")[x.kind])}</b>
        <small>${x.date ? shortDate(x.date) : ""}</small><span class="tag ${cls}">${label}</span></span>
      <b class="num sale-amount ${x.refunded ? "refunded" : ""}">+${toman(x.amount)}</b>
    </div>`;
  }).join("");
}

function buyPremium(o) {
  if (!o) return;
  tap();
  tg.showConfirm(t("premium_confirm", { s: o.stars, n: o.months }), async (ok) => {
    if (!ok) return;
    try {
      renderWallet(await api("/api/wallet/premium", { method: "POST", body: JSON.stringify({ months: o.months }) }));
      haptic("success"); toast(t("premium_done")); refreshHome();
    } catch (e) { haptic("error"); toast(errMsg(e.code)); }
  });
}

// ---------------- خریدها ----------------
function purchaseRow(p) {
  return `
    <button class="row" data-link="${esc(p.link)}">
      ${kicon(p.kind)}
      <span class="purchase-meta"><b>${esc(p.title || t("kinds")[p.kind])}</b>
        <small><span class="num gold">${toman(p.amount)}</span> · <bdi>@${esc(p.shop)}</bdi></small>
        ${p.order && p.order.tracking ? `<small>${t("ord_tracking")}: <bdi class="num">${esc(p.order.tracking)}</bdi></small>` : ""}
        <span class="tag ${p.order ? (p.order.status === "paid" ? "new" : "") : p.opened ? "" : "new"}">${p.order ? t("ord_st_" + p.order.status) : p.opened ? t("opened_tag") : t("not_opened_tag")}</span></span>
      <svg class="chev"><use href="#i-chev"/></svg>
    </button>`;
}

async function loadPurchases() {
  let items = [], memberships = [];
  try { ({ items, memberships } = await api("/api/purchases")); } catch (e) { /* خالی */ }
  $("pf-memberships-box").classList.toggle("hidden", !memberships.length);
  $("pf-memberships").innerHTML = memberships.map((m) => {
    const status = !m.active ? t("ms_ended") : !m.expires_at ? t("sc_member_forever")
      : m.canceled ? t("sc_member_ends", shortDay(m.expires_at)) : t("sc_member_until", shortDay(m.expires_at));
    return `<button class="row" data-link="${esc(m.link)}">
      <span class="kicon" style="--k: var(--color-accent); --k-soft: var(--color-accent-soft)"><svg><use href="#i-store"/></svg></span>
      <span class="purchase-meta"><b>${esc(m.title)}</b><small><bdi>@${esc(m.shop)}</bdi> · ${status}</small>
        <span class="tag ${m.active ? "" : "new"}">${m.active ? t("sc_you_member") : t("ms_rejoin")}</span></span>
      <svg class="chev"><use href="#i-chev"/></svg></button>`;
  }).join("");
  $("pf-memberships").querySelectorAll(".row").forEach((r) => { r.onclick = () => { tap(); openTelegram(r.dataset.link); }; });
  items = items || [];
  $("pf-purchases").classList.toggle("hidden", !items.length);
  $("pf-purchases-empty").classList.toggle("hidden", !!items.length || !!memberships.length);
  $("pf-purchases").innerHTML = items.map(purchaseRow).join("");
  // خانه‌ی کسی که فروشگاه ندارد: سه خرید آخر
  $("home-purchases-box").classList.toggle("hidden", !items.length);
  $("home-purchases").innerHTML = items.slice(0, 3).map(purchaseRow).join("");
  document.querySelectorAll("#pf-purchases .row, #home-purchases .row").forEach((r) => {
    r.onclick = () => { tap(); openTelegram(r.dataset.link); };
  });
}

async function setLanguage(l) {
  if (l === lang) return;
  tap();
  try {
    await api("/api/me", { method: "PATCH", body: JSON.stringify({ lang: l }) });
    me.lang = l; await applyLang(l); haptic("success");
    renderHome(); renderProfile();
    if (state.items.length) renderProducts();
    if ($("page-purchases").classList.contains("active")) loadPurchases();
  } catch (e) { toast(t("err_generic")); }
}

// ---------------- راهنمای اولین ورود ----------------
// «دیده شد» در CloudStorage تلگرام ذخیره می‌شود تا روی همه‌ی دستگاه‌های کاربر یادش بماند
const OB_KEY = "uf_onboarded_v1";
function localGet(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
function storageGet(key) {
  return new Promise((resolve) => {
    const local = localGet(key);
    if (local || !tg.CloudStorage || !tg.isVersionAtLeast?.("6.9")) return resolve(local);
    // اگر تلگرام جواب نداد (نسخه‌ی قدیمی، شبکه‌ی کند) منتظر نمی‌مانیم
    const timer = setTimeout(() => resolve(null), 1500);
    try { tg.CloudStorage.getItem(key, (err, v) => { clearTimeout(timer); resolve(err ? null : v); }); }
    catch (e) { clearTimeout(timer); resolve(null); }
  });
}
function storageSet(key, value) {
  try { localStorage.setItem(key, value); } catch (e) { /* حالت خصوصی */ }
  try { if (tg.CloudStorage && tg.isVersionAtLeast?.("6.9")) tg.CloudStorage.setItem(key, value); } catch (e) { /* قدیمی */ }
}

function showOnboarding(replay = false) {
  const layer = $("onboarding"), track = $("ob-track"), slides = [...track.children], dots = [...$("ob-dots").children];
  let index = 0;
  const go = (i) => {
    index = Math.max(0, Math.min(slides.length - 1, i));
    const dir = LANGS[lang].dir === "rtl" ? -1 : 1;
    track.scrollTo({ left: dir * index * track.clientWidth, behavior: reducedMotion() ? "auto" : "smooth" });
    mark();
  };
  const mark = () => {
    slides.forEach((s, k) => s.classList.toggle("in", k === index));
    dots.forEach((d, k) => d.classList.toggle("on", k === index));
    $("ob-next").textContent = index === slides.length - 1 ? t(replay ? "ob_close" : "ob_start") : t("ob_next");
  };
  const finish = () => {
    storageSet(OB_KEY, "1");
    layer.classList.add("fade");
    setTimeout(() => { layer.classList.add("hidden"); layer.classList.remove("fade"); }, 300);
    haptic("success");
  };
  track.onscroll = () => {
    const k = Math.round(Math.abs(track.scrollLeft) / track.clientWidth);
    if (k !== index) { index = k; mark(); tap(); }
  };
  $("ob-next").onclick = () => { tap(); index === slides.length - 1 ? finish() : go(index + 1); };
  $("ob-skip").onclick = finish;
  layer.classList.remove("hidden");
  track.scrollLeft = 0;
  index = 0; mark();
}

// ---------------- ناوبری ----------------
function showPage(pageId) {
  document.querySelectorAll(".page").forEach((p) => p.classList.toggle("active", p.id === pageId));
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.page === pageId));
  if (pageId === "page-products") loadProducts().catch(() => toast(t("err_generic")));
  if (pageId === "page-profile") renderProfile();
  if (pageId === "page-purchases") loadPurchases();
  // دکمه‌ی برگشت تلگرام فقط برای کیف پول، برگه‌ها و ویترینِ داخل داشبورد
  if (pageId !== subPage.current) subPage.current = null;
  if (pageId !== "page-wallet" && pageId !== "page-store" && !state.current && !langSheetOpen()) tg.BackButton.hide();
}

// از پروفایل: رفتن به کارت‌های ویترین در خانه و یک چشمک کوتاه تا معلوم باشد کجاست
function goHomeShowcases() {
  showPage("page-home");
  const box = $("sc-box");
  box.scrollIntoView({ behavior: "smooth", block: "start" });
  box.classList.remove("flash"); void box.offsetWidth; box.classList.add("flash");
}

function switchTab(tab) {
  switchTabSilently(tab); return loadProducts();
}
function switchTabSilently(tab) {
  document.querySelectorAll("#status-tabs .tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === tab));
  state.tab = tab;
}

async function refreshHome() {
  try { me = await api("/api/me"); renderHome(); } catch (e) { /* خانه با داده‌ی قبلی می‌ماند */ }
}

// یک بستن برای همه‌ی برگه‌ها (کلیک روی پس‌زمینه یا دکمه‌ی برگشت تلگرام)
function overlayClick() {
  if (scEd.open) return closeShowcaseEditor();
  closeTopSheet();
}

function closeTopSheet() {
  if (langSheetOpen()) return closeLangSheet();
  if (scEd.open) return sceBack();
  if (store.current) return closeBuy();
  if (state.current) return closeEditor();
}

function initNav() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.onclick = () => {
      if (btn.dataset.page === "page-products" && state.kind && btn.classList.contains("active")) { state.kind = null; renderProducts(); }
      if (!btn.classList.contains("active")) { showPage(btn.dataset.page); tap(); }
    };
  });
  $("see-purchases").onclick = () => { tap(); showPage("page-purchases"); };
  // دکمه‌ی آپلود وسط: فروشنده → ربات فروشگاه؛ بقیه → ربات اصلی (لینک رایگان)
  $("fab").onclick = () => {
    tap();
    openTelegram(me.shop ? `https://ble.ir/${me.shop.bot}?start=upload` : `https://ble.ir/${me.main_bot}`);
  };
  // دکمه‌ی «تنظیمات» در منوی سه‌نقطه‌ی تلگرام → پروفایل
  try { tg.SettingsButton.show(); tg.SettingsButton.onClick(() => { if (!STORE) showPage("page-profile"); }); } catch (e) { /* قدیمی */ }
  // برگشت به Mini App (مثلاً بعد از آپلود در ربات فروشگاه): داده‌ها تازه می‌شوند
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible" || STORE) return;
    refreshHome();
    if ($("page-products").classList.contains("active")) loadProducts().catch(() => {});
  });
}

// زبان پیش از رسیدن پاسخ سرور: از زبان تلگرام حدس می‌زنیم
function guessLang() {
  return "fa";  // نسخه‌ی بله فقط فارسی است
}

async function main() {
  document.querySelector(".splash-logo")?.addEventListener("error", (e) => e.target.remove());
  applyTheme();  // قبل از هر چیز تا اسپلش هم با تم کاربر باشد
  try { tg.onEvent("themeChanged", applyTheme); } catch (e) { /* بیرون از تلگرام */ }
  await applyLang(guessLang());
  if (!tg || !tg.initData) return showError("no_telegram");

  tg.ready(); tg.expand();
  tg.BackButton.onClick(onBack);  // فقط یک بار، برای همه‌ی صفحه‌ها و برگه‌ها
  try { tg.disableVerticalSwipes?.(); } catch (e) { /* قدیمی */ }


  try { me = await api("/api/me"); } catch (e) { return showError(e.code === "banned" ? "err_banned" : "load_failed"); }

  await applyLang(me.lang);  // زبانی که کاربر انتخاب کرده
  renderHeader();
  if (STORE) { await startStore(); }
  else { initNav(); initProducts(); initEditor(); initTrust(); initShowcaseEditor(); renderHome(); }
  $("app").classList.remove("hidden");
  $("splash").classList.add("fade");
  setTimeout(() => $("splash").classList.add("hidden"), 400);
  if (STORE) return;

  if (OPEN_PRODUCT && me.shop) {  // از دکمه‌ی «تنظیم محصول» در ربات فروشنده
    showPage("page-products");
    try {
      const p = await api(`/api/products/${OPEN_PRODUCT}`);
      await switchTab(p.status);
      openEditor(p);
    } catch (e) { toast(t("err_generic")); }
    return;
  }
  if (params.get("page") === "support") { showPage("page-profile"); await openSupport(); return; }
  if (!(await storageGet(OB_KEY))) showOnboarding();
}

main();
