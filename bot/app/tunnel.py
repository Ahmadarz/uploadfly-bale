"""تونل HTTPS موقت برای آزمایش روی کامپیوتر خود مالک (Cloudflare quick tunnel، رایگان و بدون حساب).

بله فقط Mini App با آدرس HTTPS را باز می‌کند. روی سرور به‌جای این، WEBAPP_URL ثابت در .env گذاشته می‌شود.
آدرس تونل با هر اجرا عوض می‌شود؛ دکمه‌ی «باز کردن UploadFly» در /start همان آدرس تازه را می‌گیرد.
cloudflared باید نصب باشد، یا فایل cloudflared.exe در پوشه‌ی tools/ کنار پوشه‌ی bot/ گذاشته شود.
"""
import asyncio
import logging
import os
import re
import shutil
import signal

from pathlib import Path

import aiohttp

log = logging.getLogger(__name__)

_tasks: set[asyncio.Task] = set()
URL_RE = re.compile(rb"https://[a-z0-9-]+\.trycloudflare\.com")


def find_cloudflared() -> str | None:
    found = shutil.which("cloudflared")
    if found:
        return found
    root = Path(__file__).resolve().parent.parent.parent
    for path in (root / "tools" / "cloudflared.exe", root / "tools" / "cloudflared",
                 Path("/opt/homebrew/opt/cloudflared/bin/cloudflared")):
        if path.is_file():
            return str(path)
    return None


async def _read_url(proc: asyncio.subprocess.Process) -> str | None:
    while True:
        line = await proc.stderr.readline()
        if not line:
            return None
        if m := URL_RE.search(line):
            return m.group(0).decode()


async def start_tunnel(port: int, timeout: float = 40) -> tuple[asyncio.subprocess.Process, str] | None:
    exe = find_cloudflared()
    if exe is None:
        log.warning("cloudflared not installed; Mini App disabled")
        return None
    proc = await asyncio.create_subprocess_exec(
        exe, "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{port}",
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    try:
        url = await asyncio.wait_for(_read_url(proc), timeout)
    except asyncio.TimeoutError:
        url = None
    if url is None:
        proc.kill()
        log.warning("Could not start Cloudflare tunnel; Mini App disabled")
        return None
    # خروجی cloudflared باید خوانده شود وگرنه بافر پر می‌شود و تونل گیر می‌کند
    for coro in (_drain(proc), watch(url)):  # ارجاع نگه می‌داریم تا پایتون تسک را دور نیندازد
        task = asyncio.create_task(coro)
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    log.info("Mini App tunnel: %s", url)
    return proc, url


async def _drain(proc: asyncio.subprocess.Process) -> None:
    while await proc.stderr.readline():
        pass
    # تونل مرده؛ آدرسش دیگر کار نمی‌کند. برنامه را می‌بندیم تا سرویس‌دهنده (یا خود مالک) با تونل تازه بالا بیاورد
    await proc.wait()
    log.error("Cloudflare tunnel exited (code %s); restarting the app for a new tunnel", proc.returncode)
    os.kill(os.getpid(), signal.SIGTERM)


async def reachable(session: aiohttp.ClientSession, url: str) -> bool:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            return resp.status < 500
    except Exception:
        return False


async def watch(url: str, interval: float = 60, failures_to_restart: int = 3) -> None:
    """گاهی پردازه‌ی cloudflared زنده می‌ماند ولی آدرسش دیگر کار نمی‌کند (Mini App باز نمی‌شود).
    اگر چند بار پشت سر هم آدرس تونل جواب نداد ولی خود Cloudflare در دسترس بود، برنامه را می‌بندیم
    تا launchd با تونل تازه بالا بیاورد. اگر اینترنت قطع است ری‌استارت نمی‌کنیم (بدتر می‌شد: تونلی ساخته نمی‌شد)."""
    failures = 0
    async with aiohttp.ClientSession() as session:
        while True:
            await asyncio.sleep(interval)
            if await reachable(session, url + "/static/tokens.css"):
                failures = 0
                continue
            if not await reachable(session, "https://www.cloudflare.com/cdn-cgi/trace"):
                continue  # اینترنت قطع است؛ صبر می‌کنیم
            failures += 1
            log.warning("Mini App tunnel not reachable (%s/%s)", failures, failures_to_restart)
            if failures >= failures_to_restart:
                log.error("Mini App tunnel is dead; restarting the app for a new tunnel")
                os.kill(os.getpid(), signal.SIGTERM)
                return
