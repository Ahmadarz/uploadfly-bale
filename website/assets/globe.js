// کره‌ی نقطه‌ای «فروش در هر جای دنیا» (الهام از بخش Region: Earth سایت Cloudflare).
// بدون کتابخانه: canvas دوبعدی، نقطه‌ها فقط روی خشکی (globe-land.js). با موس/انگشت چرخانده می‌شود،
// وقتی کسی دست نمی‌زند آرام می‌چرخد، و قوس‌هایی با ⭐ از شهرهای دنیا به فروشنده می‌روند (نمایشی، نه آمار واقعی).
(() => {
  const host = document.querySelector("[data-globe]");
  const land = window.UF_LAND;
  if (!host || !land || !host.querySelector("canvas").getContext) return;
  const canvas = host.querySelector("canvas");
  const ctx = canvas.getContext("2d");
  const reduce = matchMedia("(prefers-reduced-motion: reduce)");
  const RAD = Math.PI / 180;

  // ---------- نقشه‌ی خشکی ----------
  const MW = 720, MH = 360;
  const raw = atob(land);
  const isLand = (lat, lon) => {
    const x = Math.min(MW - 1, Math.floor((lon + 180) / 360 * MW));
    const y = Math.min(MH - 1, Math.floor((90 - lat) / 180 * MH));
    const i = y * MW + x;
    return (raw.charCodeAt(i >> 3) >> (i & 7)) & 1;
  };

  // نقطه‌های یکنواخت روی کره (مارپیچ فیبوناچی)، فقط روی خشکی
  const N = 22000, golden = Math.PI * (3 - Math.sqrt(5));
  const pts = [];
  for (let i = 0; i < N; i++) {
    const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), th = golden * i;
    const x = Math.cos(th) * r, z = Math.sin(th) * r;
    const lat = Math.asin(y) / RAD, lon = Math.atan2(x, z) / RAD;
    if (isLand(lat, lon)) pts.push(x, y, z);
  }
  const P = new Float32Array(pts);

  const vec = (lat, lon) => [Math.cos(lat * RAD) * Math.sin(lon * RAD), Math.sin(lat * RAD), Math.cos(lat * RAD) * Math.cos(lon * RAD)];
  const CITIES = [[41, 29], [52.5, 13.4], [51.5, -0.1], [43.7, -79.4], [40.7, -74], [34, -118.2], [25.2, 55.3], [55.75, 37.6],
    [-33.9, 151.2], [35.7, 139.7], [3.1, 101.7], [-23.5, -46.6], [59.3, 18], [40.4, 49.9], [34.5, 69.2], [19, 72.8],
    [30, 31.2], [48.9, 2.35], [40.2, 44.5], [43.2, 76.9], [-26.2, 28], [39.9, 116.4], [1.35, 103.8], [45.5, -73.6],
    [41.3, 69.2], [24.7, 46.7], [37.6, 127], [52.4, 4.9], [-37.8, 145], [6.5, 3.4]].map(([a, b]) => vec(a, b));
  const hubAttr = host.dataset.hub; // «lat,lon» فروشنده؛ بدون آن قوس‌ها بین دو شهر تصادفی‌اند
  const HUB = hubAttr ? vec(...hubAttr.split(",").map(Number)) : null;

  // ---------- چرخش ----------
  let yaw = HUB ? -Math.atan2(HUB[0], HUB[2]) + 0.5 : -0.9;   // اول، فروشنده کمی کنار وسط باشد
  let pitch = 0.3, vYaw = 0, dragging = false, lastX = 0, lastY = 0, lastT = 0, idleAt = 0;
  const AUTO = 0.0016;

  const rot = (v) => {
    const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const x = v[0] * cy + v[2] * sy, z0 = -v[0] * sy + v[2] * cy;
    return [x, v[1] * cp - z0 * sp, v[1] * sp + z0 * cp];
  };

  // ---------- رنگ‌ها از CSS (روشن/تیره) ----------
  let C = {};
  const readColors = () => {
    const s = getComputedStyle(host);
    const g = (n) => s.getPropertyValue(n).trim();
    C = { dot: g("--globe-dot"), arc: g("--globe-arc"), star: g("--globe-star"), glow: g("--globe-glow"), glow0: g("--globe-glow-0"), ball: g("--globe-ball"), ball0: g("--globe-ball-0") };
  };
  readColors();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { readColors(); draw(); });

  // ---------- اندازه ----------
  let W = 0, H = 0, R = 0, cx = 0, cy = 0, dpr = 1;
  const resize = () => {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const r = canvas.getBoundingClientRect();
    W = r.width; H = r.height;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    R = Math.min(W * 0.42, H * 0.6);
    cx = W / 2; cy = R * 1.2;
    draw();
  };

  // ---------- قوس‌ها ----------
  const arcs = [];
  let nextArc = 0;
  const slerp = (a, b, t) => {
    const d = Math.acos(Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2])));
    if (d < 1e-6) return a;
    const s = Math.sin(d), k1 = Math.sin((1 - t) * d) / s, k2 = Math.sin(t * d) / s;
    return [a[0] * k1 + b[0] * k2, a[1] * k1 + b[1] * k2, a[2] * k1 + b[2] * k2];
  };
  const spawn = (now) => {
    const front = (v) => rot(v)[2] > 0.15;
    const pick = (not) => {
      const ok = CITIES.filter((c) => c !== not && front(c));
      const list = ok.length ? ok : CITIES;
      return list[Math.floor(Math.random() * list.length)];
    };
    const to = HUB || pick(null);
    const from = pick(to);
    const d = Math.acos(from[0] * to[0] + from[1] * to[1] + from[2] * to[2]);
    arcs.push({ from, to, t0: now, dur: 1400 + d * 900, lift: 0.08 + d * 0.16 });
  };
  const arcPoint = (a, t) => {
    const p = slerp(a.from, a.to, t), h = 1 + Math.sin(Math.PI * t) * a.lift;
    return rot([p[0] * h, p[1] * h, p[2] * h]);
  };
  const scr = (v) => [cx + v[0] * R, cy - v[1] * R];
  const visible = (v) => v[2] > 0 || Math.hypot(v[0], v[1]) > 1; // پشت کره پنهان، مگر بالاتر از لبه

  // ---------- کشیدن ----------
  function draw(now = performance.now()) {
    if (!W) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    // هاله و خود کره
    const halo = ctx.createRadialGradient(cx, cy, R * 0.95, cx, cy, R * 1.19);
    halo.addColorStop(0, C.glow); halo.addColorStop(1, C.glow0);
    ctx.fillStyle = halo; ctx.beginPath(); ctx.arc(cx, cy, R * 1.19, 0, Math.PI * 2); ctx.fill();
    const ball = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.45, R * 0.1, cx, cy, R);
    ball.addColorStop(0, C.ball); ball.addColorStop(1, C.ball0);
    ctx.fillStyle = ball; ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();
    // نقطه‌های خشکی
    const cyw = Math.cos(yaw), syw = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const size = Math.max(1.1, R / 210);
    ctx.fillStyle = C.dot;
    for (let i = 0; i < P.length; i += 3) {
      const x = P[i] * cyw + P[i + 2] * syw, z0 = -P[i] * syw + P[i + 2] * cyw;
      const y = P[i + 1] * cp - z0 * sp, z = P[i + 1] * sp + z0 * cp;
      if (z <= 0) continue;
      const sy = cy - y * R;
      if (sy > H + 4) continue;
      ctx.globalAlpha = 0.18 + z * 0.82;
      const s = size * (0.55 + z * 0.45);
      ctx.fillRect(cx + x * R - s / 2, sy - s / 2, s, s);
    }
    ctx.globalAlpha = 1;
    // قوس‌ها
    ctx.lineCap = "round";
    for (const a of arcs) {
      const t = Math.min(1, (now - a.t0) / a.dur);
      const tail = Math.max(0, t - 0.45), fade = t >= 1 ? Math.max(0, 1 - (now - a.t0 - a.dur) / 900) : 1;
      const steps = 40;
      ctx.strokeStyle = C.arc; ctx.lineWidth = 2;
      for (let k = 0; k < steps; k++) {
        const u0 = tail + (t - tail) * (k / steps), u1 = tail + (t - tail) * ((k + 1) / steps);
        const p0 = arcPoint(a, u0), p1 = arcPoint(a, u1);
        if (!visible(p0) || !visible(p1)) continue;
        ctx.globalAlpha = fade * (k / steps);
        const s0 = scr(p0), s1 = scr(p1);
        ctx.beginPath(); ctx.moveTo(s0[0], s0[1]); ctx.lineTo(s1[0], s1[1]); ctx.stroke();
      }
      // نقطه‌ی شروع (خریدار)
      const f = rot(a.from);
      if (f[2] > 0) { const s = scr(f); ctx.globalAlpha = fade; ctx.fillStyle = C.arc; ctx.beginPath(); ctx.arc(s[0], s[1], 2.6, 0, Math.PI * 2); ctx.fill(); }
      // ستاره‌ی در حال پرواز، بعد موج و «+⭐» روی فروشنده
      const head = arcPoint(a, t);
      if (t < 1 && visible(head)) {
        const s = scr(head);
        ctx.globalAlpha = 1; ctx.fillStyle = C.star; ctx.font = `${Math.round(12 + R / 40)}px sans-serif`;
        ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText("★", s[0], s[1]);
      } else if (t >= 1) {
        const e = rot(a.to);
        if (e[2] > 0) {
          const k = Math.min(1, (now - a.t0 - a.dur) / 900), s = scr(e);
          ctx.globalAlpha = 1 - k; ctx.strokeStyle = C.star; ctx.lineWidth = 2;
          ctx.beginPath(); ctx.arc(s[0], s[1], 4 + k * 22, 0, Math.PI * 2); ctx.stroke();
          ctx.fillStyle = C.star; ctx.font = `700 ${Math.round(13 + R / 45)}px sans-serif`;
          ctx.fillText("+★", s[0], s[1] - 14 - k * 18);
        }
      }
    }
    ctx.globalAlpha = 1;
    // نشان فروشنده
    if (HUB) {
      const h = rot(HUB);
      if (h[2] > 0) {
        const s = scr(h), pulse = reduce.matches ? 0.5 : (now % 1800) / 1800;
        ctx.fillStyle = C.star;
        ctx.globalAlpha = 0.35 * (1 - pulse); ctx.beginPath(); ctx.arc(s[0], s[1], 5 + pulse * 12, 0, Math.PI * 2); ctx.fill();
        ctx.globalAlpha = 1; ctx.beginPath(); ctx.arc(s[0], s[1], 4.5, 0, Math.PI * 2); ctx.fill();
      }
    }
  }

  // ---------- حلقه ----------
  let running = false, raf = 0, last = 0;
  const frame = (now) => {
    const dt = Math.min(50, now - (last || now)); last = now;
    if (!dragging) {
      const auto = now - idleAt > 1600 ? AUTO : 0;
      vYaw += (auto - vYaw) * 0.04;         // اینرسی بعد از رها کردن، بعد برگشت به چرخش آرام
      yaw += vYaw * dt;
    }
    if (now > nextArc) { spawn(now); nextArc = now + 650 + Math.random() * 700; }
    while (arcs.length && now - arcs[0].t0 > arcs[0].dur + 900) arcs.shift();
    draw(now);
    raf = running ? requestAnimationFrame(frame) : 0;
  };
  const start = () => { if (!running && !reduce.matches) { running = true; last = 0; raf = requestAnimationFrame(frame); } };
  const stop = () => { running = false; cancelAnimationFrame(raf); };

  // ---------- موس و انگشت ----------
  canvas.addEventListener("pointerdown", (e) => {
    dragging = true; lastX = e.clientX; lastY = e.clientY; lastT = performance.now(); vYaw = 0;
    canvas.setPointerCapture(e.pointerId); host.classList.add("grabbing");
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const now = performance.now(), dx = e.clientX - lastX, dy = e.clientY - lastY;
    yaw += dx / R; pitch = Math.max(-0.2, Math.min(1.0, pitch + dy / R * 0.6));
    vYaw = dx / R / Math.max(8, now - lastT);
    lastX = e.clientX; lastY = e.clientY; lastT = now;
    if (!running) draw();
  });
  const release = () => { if (!dragging) return; dragging = false; idleAt = performance.now(); host.classList.remove("grabbing"); };
  canvas.addEventListener("pointerup", release);
  canvas.addEventListener("pointercancel", release);
  // کیبورد: چپ و راست
  host.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault(); yaw += e.key === "ArrowLeft" ? -0.15 : 0.15; idleAt = performance.now(); vYaw = 0; if (!running) draw();
  });

  // فقط وقتی دیده می‌شود کار کند (باتری گوشی)
  new IntersectionObserver(([en]) => (en.isIntersecting ? start() : stop())).observe(host);
  document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));
  reduce.addEventListener("change", () => (reduce.matches ? stop() : start()));
  new ResizeObserver(resize).observe(canvas);
  resize();
})();
