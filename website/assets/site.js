// تنها جاوااسکریپت سایت: باز و بسته کردن منو روی گوشی
(() => {
  const btn = document.querySelector(".menu"), nav = document.getElementById("nav");
  if (!btn || !nav) return;
  btn.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    btn.setAttribute("aria-expanded", String(open));
  });
  nav.addEventListener("click", (e) => { if (e.target.closest("a")) { nav.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); } });
})();
