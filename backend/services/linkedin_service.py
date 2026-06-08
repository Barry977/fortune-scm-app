import asyncio
import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
BROWSER_PROFILE = os.path.join(DATA_DIR, "browser_profile")
COOKIE_FILE = os.path.join(BROWSER_PROFILE, "cookies.json")

_browser = None
_context = None
_page = None


async def _get_page():
    global _browser, _context, _page
    from playwright.async_api import async_playwright
    if _page and not _page.is_closed():
        return _page
    os.makedirs(BROWSER_PROFILE, exist_ok=True)
    pw = await async_playwright().start()
    _browser = await pw.chromium.launch_persistent_context(
        BROWSER_PROFILE,
        headless=False,
        viewport={"width": 1280, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    if os.path.exists(COOKIE_FILE):
        try:
            cookies = json.loads(open(COOKIE_FILE).read())
            await _browser.add_cookies(cookies)
        except Exception:
            pass
    pages = _browser.pages
    _page = pages[0] if pages else await _browser.new_page()
    return _page


async def open_login():
    page = await _get_page()
    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    return {"status": "opened", "message": "LinkedIn login page opened. Please log in manually."}


async def check_status() -> dict:
    page = await _get_page()
    try:
        current = page.url
        if "/feed" in current or "/mynetwork" in current or "linkedin.com/in/" in current:
            return {"logged_in": True, "url": current}
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(2)
        url = page.url
        logged_in = "/feed" in url and "login" not in url
        if logged_in:
            cookies = await _browser.cookies()
            with open(COOKIE_FILE, "w") as f:
                json.dump(cookies, f)
        return {"logged_in": logged_in, "url": url}
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return {"logged_in": False, "error": str(e)}


async def search_people(keywords: str, location: str = None, title: str = None,
                        company: str = None, limit: int = 25) -> list[dict]:
    page = await _get_page()
    params = f"keywords={keywords}"
    if title:
        params += f"&title={title}"
    if company:
        params += f"&company={company}"
    url = f"https://www.linkedin.com/search/results/people/?{params}"
    await page.goto(url, wait_until="domcontentloaded", timeout=20000)
    await asyncio.sleep(3)
    results = await page.evaluate("""() => {
        const items = document.querySelectorAll('.reusable-search__result-container');
        return Array.from(items).slice(0, 50).map(item => {
            const nameEl = item.querySelector('.entity-result__title-text a');
            const subtitleEl = item.querySelector('.entity-result__primary-subtitle');
            const secondaryEl = item.querySelector('.entity-result__secondary-subtitle');
            return {
                name: nameEl ? nameEl.innerText.trim().split('\\n')[0] : '',
                url: nameEl ? nameEl.href : '',
                title: subtitleEl ? subtitleEl.innerText.trim() : '',
                company: secondaryEl ? secondaryEl.innerText.trim() : '',
            };
        }).filter(r => r.name);
    }""")
    return results[:limit]


async def send_connect(profile_url: str, message: str = None) -> dict:
    page = await _get_page()
    await page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
    await asyncio.sleep(2)
    try:
        connect_btn = page.locator('button:has-text("Connect"), button:has-text("连接")')
        if await connect_btn.count() > 0:
            await connect_btn.first.click()
            await asyncio.sleep(1)
            if message:
                add_note = page.locator('button:has-text("Add a note"), button:has-text("添加备注")')
                if await add_note.count() > 0:
                    await add_note.first.click()
                    await asyncio.sleep(0.5)
                    textarea = page.locator('textarea[name="message"]')
                    await textarea.fill(message)
            send_btn = page.locator('button:has-text("Send"), button:has-text("发送")')
            if await send_btn.count() > 0:
                await send_btn.first.click()
                await asyncio.sleep(1)
                return {"status": "sent", "profile": profile_url}
        return {"status": "already_connected_or_unavailable", "profile": profile_url}
    except Exception as e:
        logger.error(f"Connect error: {e}")
        return {"status": "error", "error": str(e)}


async def send_message(profile_url: str, message: str) -> dict:
    page = await _get_page()
    await page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
    await asyncio.sleep(2)
    try:
        msg_btn = page.locator('button:has-text("Message"), button:has-text("消息")')
        if await msg_btn.count() > 0:
            await msg_btn.first.click()
            await asyncio.sleep(1)
            editor = page.locator('.msg-form__contenteditable, div[role="textbox"]')
            if await editor.count() > 0:
                await editor.first.fill(message)
                await asyncio.sleep(0.5)
                send_btn = page.locator('button.msg-form__send-button, button:has-text("Send")')
                if await send_btn.count() > 0:
                    await send_btn.first.click()
                    await asyncio.sleep(1)
                    return {"status": "sent", "profile": profile_url}
        return {"status": "failed", "error": "Could not find message button or editor"}
    except Exception as e:
        logger.error(f"Message error: {e}")
        return {"status": "error", "error": str(e)}


async def publish_post(content: str) -> dict:
    page = await _get_page()
    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=20000)
    await asyncio.sleep(2)
    try:
        start_post = page.locator('button:has-text("Start a post"), button:has-text("开始发帖")')
        if await start_post.count() > 0:
            await start_post.first.click()
            await asyncio.sleep(1)
            editor = page.locator('div[role="textbox"]')
            if await editor.count() > 0:
                await editor.first.fill(content)
                await asyncio.sleep(1)
                post_btn = page.locator('button:has-text("Post"), button:has-text("发布")')
                if await post_btn.count() > 0:
                    await post_btn.first.click()
                    await asyncio.sleep(2)
                    return {"status": "published"}
        return {"status": "failed", "error": "Could not create post"}
    except Exception as e:
        logger.error(f"Publish error: {e}")
        return {"status": "error", "error": str(e)}
