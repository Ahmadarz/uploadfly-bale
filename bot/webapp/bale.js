// لایه‌ی سازگاری بله: مینی‌اپ برای Telegram.WebApp نوشته شده؛ این فایل همان شکل را روی Bale.WebApp می‌سازد
// (docs.bale.ai/miniapp). چیزهایی که بله ندارد (دکمه‌ی اصلی پایین صفحه، پنجره‌ی تأیید، لرزش، ذخیره‌ی ابری)
// داخل خود صفحه ساخته می‌شوند تا بقیه‌ی کد (app.js) دست نخورد.
"use strict";
(function () {
  const B = window.Bale && window.Bale.WebApp;
  if (!B) return;  // کتابخانه‌ی بله بار نشده (اینترنت قطع یا بیرون از بله)

  const safe = (fn) => { try { return fn(); } catch (e) { return undefined; } };  // بیرون از اپ بله پل ارتباطی نیست

  const css = document.createElement("style");
  css.textContent = `
    .bale-main { position: fixed; inset-inline: 0; bottom: 0; z-index: 900; padding: 10px 16px calc(10px + env(safe-area-inset-bottom));
      background: var(--color-paper, #e9ebf3); box-shadow: 0 -6px 18px rgba(0,0,0,.08); display: none; }
    .bale-main.on { display: block; }
    .bale-main button { width: 100%; min-height: 50px; border: 0; border-radius: 16px; font: inherit; font-weight: 700; font-size: 16px;
      background: var(--color-accent, #5b5bd6); color: var(--color-accent-ink, #fff); display: flex; align-items: center; justify-content: center; gap: 8px; }
    .bale-main button:disabled { opacity: .55; }
    .bale-main .spin { width: 18px; height: 18px; border-radius: 50%; border: 2.5px solid currentColor; border-inline-end-color: transparent;
      animation: bale-spin .7s linear infinite; display: none; }
    .bale-main.busy .spin { display: block; }
    @keyframes bale-spin { to { transform: rotate(360deg); } }
    body.bale-has-main { padding-bottom: 76px; }
    .bale-confirm { position: fixed; inset: 0; z-index: 1000; background: rgba(10,12,24,.5); display: flex; align-items: center; justify-content: center; padding: 24px; }
    .bale-confirm > div { background: var(--color-paper-2, #fff); color: var(--color-ink, #1c1e3a); border-radius: 22px; padding: 22px 20px 14px;
      max-width: 340px; width: 100%; box-shadow: 0 18px 50px rgba(0,0,0,.3); }
    .bale-confirm p { margin: 0 0 18px; line-height: 1.9; font-size: 15px; white-space: pre-line; }
    .bale-confirm .acts { display: flex; gap: 10px; }
    .bale-confirm button { flex: 1; min-height: 44px; border: 0; border-radius: 14px; font: inherit; font-weight: 700; font-size: 15px; }
    .bale-confirm .yes { background: var(--color-accent, #5b5bd6); color: var(--color-accent-ink, #fff); }
    .bale-confirm .no { background: transparent; color: inherit; opacity: .75; }
  `;
  document.head.appendChild(css);

  // --- دکمه‌ی اصلی (در تلگرام بیرون از صفحه و زیر آن است؛ این‌جا نوار ثابت پایین صفحه) ---
  let bar = null, btn = null, label = null;
  const clicks = [];
  const state = { visible: false, active: true, busy: false, text: "" };
  function mount() {
    if (bar || !document.body) return;
    bar = document.createElement("div"); bar.className = "bale-main";
    btn = document.createElement("button"); btn.type = "button";
    const spin = document.createElement("span"); spin.className = "spin";
    label = document.createElement("span");
    btn.append(spin, label); bar.appendChild(btn); document.body.appendChild(bar);
    btn.addEventListener("click", () => { if (state.active && !state.busy) clicks.slice().forEach((fn) => safe(fn)); });
  }
  function paint() {
    mount(); if (!bar) return;
    label.textContent = state.text;
    btn.disabled = !state.active || state.busy;
    bar.classList.toggle("on", state.visible);
    bar.classList.toggle("busy", state.busy);
    document.body.classList.toggle("bale-has-main", state.visible);
  }
  const MainButton = {
    get isVisible() { return state.visible; },
    get isActive() { return state.active; },
    setText(text) { state.text = text; paint(); return MainButton; },
    show() { state.visible = true; paint(); return MainButton; },
    hide() { state.visible = false; paint(); return MainButton; },
    enable() { state.active = true; paint(); return MainButton; },
    disable() { state.active = false; paint(); return MainButton; },
    showProgress() { state.busy = true; paint(); return MainButton; },
    hideProgress() { state.busy = false; paint(); return MainButton; },
    onClick(fn) { if (!clicks.includes(fn)) clicks.push(fn); return MainButton; },
    offClick(fn) { const i = clicks.indexOf(fn); if (i !== -1) clicks.splice(i, 1); return MainButton; },
    setParams(p) {
      if (!p) return MainButton;
      if (typeof p.text === "string") state.text = p.text;
      if (typeof p.is_visible === "boolean") state.visible = p.is_visible;
      if (typeof p.is_active === "boolean") state.active = p.is_active;
      paint();
      if (btn) { btn.style.background = p.color || ""; btn.style.color = p.text_color || ""; }
      return MainButton;
    },
  };

  // --- پنجره‌ی تأیید و پیام ---
  function dialog(message, withCancel, done) {
    const wrap = document.createElement("div"); wrap.className = "bale-confirm";
    const box = document.createElement("div"), p = document.createElement("p"), acts = document.createElement("div");
    p.textContent = message; acts.className = "acts";
    const close = (ok) => { wrap.remove(); if (done) safe(() => done(ok)); };
    const yes = document.createElement("button"); yes.className = "yes"; yes.textContent = withCancel ? "بله" : "باشه"; yes.onclick = () => close(true);
    acts.appendChild(yes);
    if (withCancel) {
      const no = document.createElement("button"); no.className = "no"; no.textContent = "انصراف"; no.onclick = () => close(false);
      acts.appendChild(no);
      wrap.addEventListener("click", (e) => { if (e.target === wrap) close(false); });
    }
    box.append(p, acts); wrap.appendChild(box); document.body.appendChild(wrap);
  }

  const atLeast = (need) => {
    const a = String(B.version || "0").split("."), b = need.split(".");
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
      const x = parseInt(a[i]) || 0, y = parseInt(b[i]) || 0;
      if (x !== y) return x > y;
    }
    return true;
  };
  const vibrate = (ms) => safe(() => navigator.vibrate && navigator.vibrate(ms));
  const status = (r) => (typeof r === "string" ? r : (r && r.status) || "failed");  // بله: رشته یا {status}

  const adapter = {
    get initData() { return B.initData || ""; },
    get initDataUnsafe() { return B.initDataUnsafe || {}; },
    get colorScheme() { return B.colorScheme || "light"; },
    get themeParams() { return B.themeParams || {}; },
    get version() { return B.version; },
    get isMiniAppSupported() { return B.isMiniAppSupported !== false; },   // false = اپ بله قدیمی است
    platform: "bale",
    isBale: true,
    MainButton,
    BackButton: {
      get isVisible() { return B.BackButton.isVisible; },
      show() { safe(() => B.BackButton.show()); }, hide() { safe(() => B.BackButton.hide()); },
      onClick(fn) { B.BackButton.onClick(fn); }, offClick(fn) { B.BackButton.offClick(fn); },
    },
    SettingsButton: {
      show() { safe(() => B.SettingsButton.show()); }, hide() { safe(() => B.SettingsButton.hide()); },
      onClick(fn) { B.SettingsButton.onClick(fn); }, offClick(fn) { B.SettingsButton.offClick(fn); },
    },
    HapticFeedback: {
      notificationOccurred() { vibrate(18); }, selectionChanged() { vibrate(8); }, impactOccurred() { vibrate(12); },
    },
    isVersionAtLeast() { return false; },   // قابلیت‌های نسخه‌دار تلگرام (استوری، دانلود فایل، ذخیره‌ی ابری) در بله نیست
    ready() { safe(() => B.ready()); },
    expand() { safe(() => B.expand()); },
    close() { safe(() => B.close()); },
    onEvent(name, fn) { safe(() => B.onEvent(name, fn)); },
    offEvent(name, fn) { safe(() => B.offEvent(name, fn)); },
    setHeaderColor(c) { safe(() => B.setHeaderColor(c)); },
    setBackgroundColor() {}, setBottomBarColor() {},
    openLink(url) { if (safe(() => { B.openLink(url); return true; }) !== true) window.open(url, "_blank", "noopener"); },
    openTelegramLink(url) { if (safe(() => { B.openLink(url); return true; }) !== true) window.location.href = url; },
    openInvoice(invoice, cb) {
      // پرداخت داخل مینی‌اپ از نسخه‌ی ۱.۳ کتابخانه‌ی بله آمده؛ کلاینت قدیمی‌تر بی‌صدا هیچ کاری نمی‌کند
      if (!atLeast("1.3")) { if (cb) cb("unsupported"); return; }
      try { B.openInvoice(invoice, (r) => cb && cb(status(r))); } catch (e) { if (cb) cb("failed"); }
    },
    showConfirm(message, cb) { dialog(message, true, cb); },
    showAlert(message, cb) { dialog(message, false, cb && (() => cb())); },
  };
  window.Telegram = { WebApp: adapter };
})();
