"""
LinkedIn automation service wrapping Playwright browser automation.
Uses a persistent Chrome profile and optional proxy configuration.
Fully self-contained — no external tool dependencies.
"""

import asyncio
import sys
import json
import logging
import os
import platform
import time
from datetime import datetime, date
from typing import Optional, List, Dict, Any

# Playwright is optional — LinkedIn automation only works when installed
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    async_playwright = None
    HAS_PLAYWRIGHT = False

from backend.database import get_db_ctx

logger = logging.getLogger(__name__)

# ── Chromium auto-download ──────────────────────────────────────
# Chromium is downloaded on first LinkedIn use, cached in user dir
if sys.platform == "win32":
    _USER_DATA_DIR = os.path.join(os.environ.get("APPDATA", ""), ".destiny")
else:
    _USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".destiny")

_BROWSER_DIR = os.path.join(_USER_DATA_DIR, "chromium")


def _ensure_chromium():
    """Set PLAYWRIGHT_BROWSERS_PATH. Download Chromium in dev mode only."""
    IS_BUNDLED = getattr(sys, '_MEIPASS', None) is not None

    if IS_BUNDLED:
        # In PyInstaller bundle: point to bundled Chromium
        bundled_browsers = os.path.join(sys._MEIPASS, 'playwright-browsers')
        if os.path.isdir(bundled_browsers):
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = bundled_browsers
            logger.info("Using bundled Chromium: %s", bundled_browsers)
        else:
            # Fallback: try default Playwright browser path
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
            logger.warning("Bundled Chromium not found at %s, using fallback", bundled_browsers)
        return

    # Development mode: use custom download path
    import subprocess
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _BROWSER_DIR

    # Already downloaded?
    if os.path.isdir(_BROWSER_DIR):
        for entry in os.listdir(_BROWSER_DIR):
            if entry.startswith("chromium-"):
                return  # already cached

    # First time — download
    logger.info("Downloading Chromium to %s ...", _BROWSER_DIR)
    os.makedirs(_BROWSER_DIR, exist_ok=True)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode == 0:
            logger.info("Chromium installed successfully")
        else:
            logger.error("Chromium install failed: %s", result.stderr)
    except Exception as e:
        logger.error("Chromium install error: %s", e)

# ── Config ──────────────────────────────────────────────────────────

# Profile directory: app-local data dir (supports PyInstaller bundle)
if getattr(sys, '_MEIPASS', None) is not None:
    # Bundled mode: use user-writable directory
    if sys.platform == "win32":
        PROFILE_DIR = os.path.join(os.environ.get("APPDATA", ""), ".destiny", "linkedin-profile")
    else:
        PROFILE_DIR = os.path.join(os.path.expanduser("~"), ".destiny", "linkedin-profile")
else:
    PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'linkedin-profile')

def _detect_system_proxy() -> str:
    """Auto-detect system proxy. Checks:
    1. Environment variables (HTTP_PROXY, HTTPS_PROXY, ALL_PROXY)
    2. Common VPN/proxy ports (V2Ray, Clash, Shadowsocks, etc.)
    Returns empty string if no proxy found.
    """
    # 1. Check env vars
    for var in ('ALL_PROXY', 'HTTPS_PROXY', 'HTTP_PROXY', 'all_proxy', 'https_proxy', 'http_proxy'):
        val = os.environ.get(var, '').strip()
        if val:
            return val

    # 2. Probe common local proxy ports
    import socket
    common_ports = [
        (7890, 'http'),   # Clash
        (7891, 'http'),   # Clash alternate
        (1080, 'socks5'), # Shadowsocks
        (1081, 'socks5'), # V2Ray
        (10808, 'socks5'), # V2Ray alternate
        (10809, 'http'),   # V2Ray HTTP
        (8080, 'http'),    # Generic
        (33210, 'socks5'), # Proxifier
    ]
    for port, proto in common_ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            s.connect(('127.0.0.1', port))
            s.close()
            return f'{proto}://127.0.0.1:{port}'
        except (socket.timeout, ConnectionRefusedError, OSError):
            continue

    return ''

PROXY = _detect_system_proxy()

# Chrome path: auto-detect per platform, fallback to Playwright bundled Chromium

LINKEDIN_EMAIL = os.environ.get("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.environ.get("LINKEDIN_PASSWORD", "")

# Daily limits (LinkedIn safe thresholds)
DAILY_LIMITS = {
    "search": 100,
    "connect": 20,
    "message": 50,
}

CONNECTION_NOTE = "Hi, I would like to connect regarding logistics and supply chain solutions."

MESSAGE_TEMPLATE = """Hi {name},

I noticed your profile and thought we might connect. I work with Fortune SCM, specializing in international logistics and supply chain solutions.

Would you be open to a brief conversation about how we might support your logistics needs?

Best regards,
Barry Yang"""

# Geo URN filters for LinkedIn search
GEO_FILTERS = {
    "US": "urn:li:fs_geo:103644278",
    "EU": "urn:li:fs_geo:100506914",
    "ME": "",  # no single URN for Middle East
}


# ── Runtime configuration ───────────────────────────────────────────

def configure_proxy(proxy_url: str):
    """Set the proxy URL used for LinkedIn browser sessions at runtime.

    Args:
        proxy_url: Proxy server URL (e.g. "socks5://127.0.0.1:1081").
                   Pass empty string to disable proxy.
    """
    global PROXY
    PROXY = proxy_url or ""
    logger.info("[LinkedIn] Proxy set to: %s", PROXY or "(none)")
    # Persist to app settings table if available
    try:
        with get_db_ctx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("linkedin_proxy", PROXY),
            )
    except Exception as e:
        logger.debug("Could not persist proxy setting to DB: %s", e)


def get_config() -> Dict[str, Any]:
    """Return the current LinkedIn service configuration."""
    return {
        "profile_dir": PROFILE_DIR,
        "proxy": PROXY,
        "chrome_path": CHROME_PATH,
    }


def _load_proxy_from_db():
    """Load proxy setting from the app's settings table, if present."""
    global PROXY
    try:
        with get_db_ctx() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?", ("linkedin_proxy",)
            ).fetchone()
            if row and row[0]:
                PROXY = row[0]
                logger.info("[LinkedIn] Loaded proxy from settings: %s", PROXY)
    except Exception:
        # settings table may not exist yet; env var / default is fine
        pass


# Try loading persisted proxy on module import
_load_proxy_from_db()


# ── Browser singleton ───────────────────────────────────────────────

_playwright = None
_browser_ctx = None
_page = None


def is_browser_running() -> bool:
    """Check if the browser is already running without launching it."""
    if _page and not _page.is_closed():
        return True
    return False


async def _get_page(headless: bool = True):
    """Get or create a persistent Playwright browser page."""
    if not HAS_PLAYWRIGHT:
        raise RuntimeError('Playwright 未安装')
    global _playwright, _browser_ctx, _page

    if _page and not _page.is_closed():
        try:
            await _page.evaluate("1")
            return _page
        except Exception:
            # page dead, re-create
            _page = None


    if _browser_ctx:
        try:
            await _browser_ctx.close()
        except Exception:
            pass
        _browser_ctx = None

    if _playwright:
        try:
            await _playwright.stop()
        except Exception:
            pass

    # Ensure profile directory exists
    os.makedirs(PROFILE_DIR, exist_ok=True)

    # Ensure Chromium is downloaded (first use only)
    _ensure_chromium()

    _playwright = await async_playwright().start()

    launch_kwargs: Dict[str, Any] = {
        "user_data_dir": PROFILE_DIR,
        "headless": headless,
        "args": [
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
        ],
        "ignore_default_args": ["--enable-automation"],
        "viewport": {"width": 1280, "height": 800},
        "locale": "en-US",
    }

    # Only set proxy if configured
    if PROXY:
        launch_kwargs["proxy"] = {"server": PROXY}

    _browser_ctx = await _playwright.chromium.launch_persistent_context(**launch_kwargs)
    _page = _browser_ctx.pages[0] if _browser_ctx.pages else await _browser_ctx.new_page()
    logger.info("[LinkedIn] Browser launched (headless=%s, proxy=%s)", headless, PROXY or "none")
    return _page


async def close_browser():
    """Shut down the browser session."""
    global _playwright, _browser_ctx, _page
    try:
        if _browser_ctx:
            await _browser_ctx.close()
    except Exception:
        pass
    try:
        if _playwright:
            await _playwright.stop()
    except Exception:
        pass
    _playwright = None
    _browser_ctx = None
    _page = None


# ── Login helpers ───────────────────────────────────────────────────

async def is_logged_in(page=None) -> bool:
    """Check if the current browser session has an active LinkedIn login."""
    page = page or await _get_page()
    try:
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        url = page.url
        logged_in = "feed" in url and "login" not in url.lower()
        return logged_in
    except Exception as e:
        logger.error("Login check failed: %s", e)
        return False


async def login(email: str = "", password: str = "") -> dict:
    """Log in to LinkedIn. Returns {success, message} with details."""
    if not HAS_PLAYWRIGHT:
        return {"success": False, "message": "Playwright 未安装，请重新安装应用"}

    email = email or LINKEDIN_EMAIL
    password = password or LINKEDIN_PASSWORD

    try:
        page = await _get_page()
    except Exception as e:
        logger.error("Failed to launch browser: %s", e)
        return {"success": False, "message": f"浏览器启动失败: {str(e)[:200]}"}

    try:
        if await is_logged_in(page):
            return {"success": True, "message": "已登录"}
    except Exception as e:
        logger.error("Login check failed: %s", e)

    if not email or not password:
        return {"success": False, "message": "请先配置 LinkedIn 账号密码（在 AI配置 页面设置，或点击登录时输入）"}

    try:
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(4)

        email_inputs = page.locator('input[type="email"]')
        pwd_inputs = page.locator('input[type="password"]')

        for idx in [1, 0]:
            try:
                await email_inputs.nth(idx).fill(email, timeout=5000)
                await pwd_inputs.nth(idx).fill(password, timeout=5000)
                await pwd_inputs.nth(idx).press("Enter")
                break
            except Exception:
                continue

        await asyncio.sleep(8)
        if "feed" in page.url:
            return {"success": True, "message": "登录成功"}
        elif "checkpoint" in page.url or "challenge" in page.url:
            return {"success": False, "message": "需要验证（验证码/二次验证），请手动登录"}
        elif "login" in page.url:
            return {"success": False, "message": "账号或密码错误"}
        else:
            return {"success": False, "message": f"登录状态未知，当前页面: {page.url[:100]}"}
    except Exception as e:
        logger.error("Login failed: %s", e)
        return {"success": False, "message": f"登录异常: {str(e)[:200]}"}


# ── Core LinkedIn operations ────────────────────────────────────────

async def search_people(keywords: str, market: str = "US", max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Search LinkedIn people by keywords with optional market geo-filter.
    Returns list of {name, vanity, url, title, location}.
    """
    page = await _get_page()
    if not await is_logged_in(page):
        if not await login():
            raise RuntimeError("LinkedIn login required")

    encoded = keywords.replace(" ", "%20")
    geo_urn = GEO_FILTERS.get(market.upper(), "")
    geo_param = f"&geoUrn={geo_urn}" if geo_urn else ""
    url = f"https://www.linkedin.com/search/results/people/?keywords={encoded}{geo_param}"

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(8)

        results = await page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="/in/"]');
            const seen = new Set();
            const items = [];
            for (const link of links) {
                const href = link.getAttribute('href').split('?')[0];
                if (seen.has(href) || !href.includes('/in/')) continue;
                seen.add(href);
                let card = link;
                for (let i = 0; i < 6; i++) {
                    if (!card.parentElement) break;
                    card = card.parentElement;
                    if (card.tagName === 'LI') break;
                }
                const text = card.innerText || '';
                const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
                const nameEl = link.querySelector('span[aria-hidden="true"]') || link;
                let name = nameEl.textContent.trim().split('•')[0].trim();
                if (!name || name.length < 2 || name.includes('LinkedIn')) continue;
                const vanity = href.replace('https://www.linkedin.com/in/', '').replace('/', '');
                let title = '', location = '';
                const filtered = lines.filter(l =>
                    l !== name && !l.includes('Connect') && !l.includes('Message') &&
                    l !== 'LinkedIn Member' && l.length > 3 && !l.match(/^\\d/)
                );
                if (filtered.length >= 1) title = filtered[0];
                if (filtered.length >= 2) location = filtered[1];
                items.push({name, vanity, url: href, title, location});
            }
            return items;
        }""")

        _log_task("search", {"keywords": keywords, "market": market}, len(results))
        _update_quota("search", len(results))
        return results[:max_results]

    except Exception as e:
        logger.error("Search failed: %s", e)
        raise


async def send_connections(count: int = 5, note: Optional[str] = None, market: str = "US") -> Dict[str, Any]:
    """
    Send connection requests to customers with status 'new' / '新线索'.
    Processes up to `count` profiles. Returns {sent, failed, details}.
    """
    page = await _get_page()
    if not await is_logged_in(page):
        if not await login():
            raise RuntimeError("LinkedIn login required")

    note = note or CONNECTION_NOTE
    sent, failed = 0, 0
    details = []

    # Get pending customers from the app DB
    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT * FROM customers WHERE status IN ('new', '新线索') ORDER BY created_at DESC LIMIT ?",
            (count,)
        ).fetchall()

    if not rows:
        return {"sent": 0, "failed": 0, "message": "No pending customers to connect", "details": []}

    for row in rows:
        customer = dict(row)
        li_url = customer.get("linkedin_url", "")
        if not li_url or "/in/" not in li_url:
            details.append({"name": customer["name"], "status": "skipped", "reason": "no linkedin url"})
            failed += 1
            continue

        vanity = li_url.split("/in/")[-1].strip("/")

        try:
            success = await _connect_one(page, vanity, note)
            if success:
                sent += 1
                details.append({"name": customer["name"], "status": "sent", "vanity": vanity})
                with get_db_ctx() as conn:
                    conn.execute(
                        "UPDATE customers SET status = 'connected', updated_at = ? WHERE id = ?",
                        (datetime.now().isoformat(), customer["id"])
                    )
            else:
                failed += 1
                details.append({"name": customer["name"], "status": "failed", "reason": "connect button not found"})

            # Random delay between requests (10-20s)
            await asyncio.sleep(10 + (hash(vanity) % 10))

        except Exception as e:
            failed += 1
            details.append({"name": customer["name"], "status": "error", "reason": str(e)[:200]})
            logger.error("Connect error for %s: %s", customer["name"], e)

    _log_task("connect", {"count": count}, sent)
    _update_quota("connect", sent)
    return {"sent": sent, "failed": failed, "details": details}


async def _connect_one(page, vanity: str, note: str) -> bool:
    """Send a single connection request via the preload invite dialog."""
    url = f"https://www.linkedin.com/preload/custom-invite/?vanityName={vanity}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)

        if note:
            add_note = page.locator('button:has-text("Add a note")')
            if await add_note.count() > 0:
                await add_note.click()
                await asyncio.sleep(2)
                textarea = page.locator("textarea")
                if await textarea.count() > 0:
                    await textarea.first.fill(note)
                    await asyncio.sleep(1)

        send_btn = page.locator('button:has-text("Send")')
        if await send_btn.count() > 0:
            await send_btn.first.click()
            await asyncio.sleep(3)
            return True

        return False
    except Exception as e:
        logger.error("Connect failed for %s: %s", vanity, e)
        return False


async def send_messages(count: int = 5, message: Optional[str] = None) -> Dict[str, Any]:
    """
    Send messages to customers with status 'connected' / '已连接'.
    Processes up to `count` profiles. Returns {sent, failed, details}.
    """
    page = await _get_page()
    if not await is_logged_in(page):
        if not await login():
            raise RuntimeError("LinkedIn login required")

    sent, failed = 0, 0
    details = []

    with get_db_ctx() as conn:
        rows = conn.execute(
            "SELECT * FROM customers WHERE status IN ('connected', '已连接') ORDER BY updated_at ASC LIMIT ?",
            (count,)
        ).fetchall()

    if not rows:
        return {"sent": 0, "failed": 0, "message": "No connected customers to message", "details": []}

    for row in rows:
        customer = dict(row)
        li_url = customer.get("linkedin_url", "")
        if not li_url or "/in/" not in li_url:
            details.append({"name": customer["name"], "status": "skipped", "reason": "no linkedin url"})
            failed += 1
            continue

        vanity = li_url.split("/in/")[-1].strip("/")
        msg = (message or MESSAGE_TEMPLATE).format(name=customer.get("name", ""))

        try:
            success = await _message_one(page, vanity, msg)
            if success:
                sent += 1
                details.append({"name": customer["name"], "status": "sent", "vanity": vanity})
                with get_db_ctx() as conn:
                    conn.execute(
                        "UPDATE customers SET status = 'messaged', updated_at = ? WHERE id = ?",
                        (datetime.now().isoformat(), customer["id"])
                    )
            else:
                failed += 1
                details.append({"name": customer["name"], "status": "failed", "reason": "message UI not found"})

            # Random delay between messages (15-30s)
            await asyncio.sleep(15 + (hash(vanity) % 15))

        except Exception as e:
            failed += 1
            details.append({"name": customer["name"], "status": "error", "reason": str(e)[:200]})
            logger.error("Message error for %s: %s", customer["name"], e)

    _log_task("message", {"count": count}, sent)
    _update_quota("message", sent)
    return {"sent": sent, "failed": failed, "details": details}


async def _message_one(page, vanity: str, message: str) -> bool:
    """Send a direct message to a LinkedIn profile."""
    url = f"https://www.linkedin.com/in/{vanity}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        # Dismiss any existing popup
        await page.keyboard.press("Escape")
        await asyncio.sleep(1)

        # Click Message button
        msg_btn = page.locator('button:has-text("Message")')
        if await msg_btn.count() == 0:
            return False

        await msg_btn.first.click()
        await asyncio.sleep(3)

        # Find message input
        textbox = page.locator('div[role="textbox"]')
        if await textbox.count() == 0:
            return False

        await textbox.first.scroll_into_view_if_needed()
        await asyncio.sleep(1)

        try:
            await textbox.first.click(force=True, timeout=5000)
        except Exception:
            box = await textbox.first.bounding_box()
            if box:
                await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            else:
                return False

        await asyncio.sleep(1)

        # Type message character by character (anti-detection)
        await textbox.first.type(message, delay=50)
        await asyncio.sleep(2)

        # Click Send
        send_btn = page.locator('button[type="submit"]:has-text("Send")')
        if await send_btn.count() > 0:
            for _ in range(10):
                if await send_btn.first.is_enabled():
                    break
                await asyncio.sleep(1)

            await send_btn.first.scroll_into_view_if_needed()
            await asyncio.sleep(1)

            try:
                await send_btn.first.click(force=True, timeout=5000)
            except Exception:
                box = await send_btn.first.bounding_box()
                if box:
                    await page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                else:
                    return False

            await asyncio.sleep(2)
            await page.keyboard.press("Escape")
            await asyncio.sleep(1)
            return True

        return False

    except Exception as e:
        logger.error("Message send failed for %s: %s", vanity, e)
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass
        return False


# ── LinkedIn Posting ───────────────────────────────────────────────

async def create_post(content: str, image_paths: Optional[List[str]] = None, headless: bool = True) -> Dict[str, Any]:
    """
    Publish a LinkedIn post with optional images.
    
    Args:
        content: Post text content
        image_paths: List of local image file paths to attach
        headless: Run browser in headless mode
        
    Returns:
        {success, post_id, message}
    """
    page = await _get_page(headless=headless)
    if not await is_logged_in(page):
        if not await login():
            raise RuntimeError("LinkedIn login required")
    
    try:
        # Navigate to LinkedIn feed
        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        
        # Click "Start a post" button
        start_post_btn = page.locator('button:has-text("Start a post")')
        if await start_post_btn.count() == 0:
            # Try alternative selector
            start_post_btn = page.locator('.share-box-feed-entry__trigger')
        
        if await start_post_btn.count() == 0:
            return {"success": False, "message": "Could not find 'Start a post' button"}
        
        await start_post_btn.first.click()
        await asyncio.sleep(3)
        
        # Find the post editor
        editor = page.locator('div[role="textbox"][contenteditable="true"]')
        if await editor.count() == 0:
            editor = page.locator('.ql-editor[contenteditable="true"]')
        
        if await editor.count() == 0:
            return {"success": False, "message": "Could not find post editor"}
        
        # Type content
        await editor.first.click()
        await asyncio.sleep(1)
        await editor.first.type(content, delay=30)
        await asyncio.sleep(2)
        
        # Upload images if provided
        if image_paths:
            # Click image/media button
            media_btn = page.locator('button:has-text("Add a photo")')
            if await media_btn.count() == 0:
                media_btn = page.locator('button[aria-label*="image"], button[aria-label*="photo"], button[aria-label*="media"]')
            
            if await media_btn.count() > 0:
                await media_btn.first.click()
                await asyncio.sleep(2)
                
                # Find file input and upload
                file_input = page.locator('input[type="file"][accept*="image"]')
                if await file_input.count() == 0:
                    file_input = page.locator('input[type="file"]')
                
                if await file_input.count() > 0:
                    for img_path in image_paths:
                        if os.path.exists(img_path):
                            await file_input.first.set_input_files(img_path)
                            await asyncio.sleep(3)  # Wait for upload
                    
                    # Wait for all uploads to complete
                    await asyncio.sleep(5)
                    
                    # Click "Done" if present
                    done_btn = page.locator('button:has-text("Done")')
                    if await done_btn.count() > 0:
                        await done_btn.first.click()
                        await asyncio.sleep(2)
        
        # Click Post button
        post_btn = page.locator('button:has-text("Post")')
        if await post_btn.count() == 0:
            post_btn = page.locator('button.share-actions__primary-action')
        
        if await post_btn.count() == 0:
            return {"success": False, "message": "Could not find Post button"}
        
        await post_btn.first.click()
        await asyncio.sleep(5)
        
        # Save to database
        post_id = None
        with get_db_ctx() as conn:
            cursor = conn.execute(
                "INSERT INTO linkedin_posts (content, image_paths, status, published_at) VALUES (?, ?, ?, ?)",
                (content, json.dumps(image_paths or []), "published", datetime.now().isoformat())
            )
            post_id = cursor.lastrowid
        
        _log_task("post", {"content": content[:100]}, 1)
        
        return {
            "success": True,
            "post_id": post_id,
            "message": "Post published successfully"
        }
        
    except Exception as e:
        logger.error("Post creation failed: %s", e)
        # Save as draft on failure
        with get_db_ctx() as conn:
            conn.execute(
                "INSERT INTO linkedin_posts (content, image_paths, status) VALUES (?, ?, ?)",
                (content, json.dumps(image_paths or []), "draft")
            )
        return {"success": False, "message": f"Post failed: {str(e)}"}


def get_posts(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Get LinkedIn posts with optional status filter."""
    with get_db_ctx() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM linkedin_posts WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM linkedin_posts ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
    return [dict(r) for r in rows]


def update_post_stats(post_id: int, likes: int = 0, comments: int = 0, views: int = 0):
    """Update engagement stats for a post."""
    with get_db_ctx() as conn:
        conn.execute(
            "UPDATE linkedin_posts SET likes_count = ?, comments_count = ?, views_count = ? WHERE id = ?",
            (likes, comments, views, post_id)
        )


def delete_post(post_id: int) -> bool:
    """Delete a post record."""
    with get_db_ctx() as conn:
        result = conn.execute("DELETE FROM linkedin_posts WHERE id = ?", (post_id,))
        return result.rowcount > 0


# ── Status & Quota ──────────────────────────────────────────────────

def get_customer_stats() -> Dict[str, Any]:
    """Aggregate customer stats from the app database."""
    with get_db_ctx() as conn:
        total = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

        by_status = {}
        for row in conn.execute("SELECT status, COUNT(*) as c FROM customers GROUP BY status"):
            by_status[row["status"]] = row["c"]

        today = date.today().isoformat()
        today_new = conn.execute(
            "SELECT COUNT(*) FROM customers WHERE DATE(created_at) = ?", (today,)
        ).fetchone()[0]

        today_contacted = conn.execute(
            "SELECT COUNT(*) FROM customers WHERE DATE(updated_at) = ? AND status != 'new'", (today,)
        ).fetchone()[0]

    return {
        "total_customers": total,
        "by_status": by_status,
        "today_new": today_new,
        "today_contacted": today_contacted,
    }


def get_quota() -> Dict[str, Any]:
    """Return today's usage and limits for search / connect / message."""
    today = date.today().isoformat()
    used = {"search": 0, "connect": 0, "message": 0}

    with get_db_ctx() as conn:
        for action in used:
            row = conn.execute(
                "SELECT COALESCE(SUM(result_count), 0) as total FROM linkedin_tasks WHERE task_type = ? AND DATE(created_at) = ?",
                (action, today)
            ).fetchone()
            used[action] = row["total"] if row else 0

    return {
        "date": today,
        "search": {"used": used["search"], "limit": DAILY_LIMITS["search"], "remaining": max(0, DAILY_LIMITS["search"] - used["search"])},
        "connect": {"used": used["connect"], "limit": DAILY_LIMITS["connect"], "remaining": max(0, DAILY_LIMITS["connect"] - used["connect"])},
        "message": {"used": used["message"], "limit": DAILY_LIMITS["message"], "remaining": max(0, DAILY_LIMITS["message"] - used["message"])},
    }


# ── Internal DB helpers ─────────────────────────────────────────────

def _log_task(task_type: str, params: dict, result_count: int):
    """Record a completed LinkedIn task in the DB."""
    try:
        with get_db_ctx() as conn:
            conn.execute(
                "INSERT INTO linkedin_tasks (user_id, task_type, status, params, result, result_count) VALUES (NULL, ?, 'done', ?, ?, ?)",
                (task_type, json.dumps(params), str(result_count), result_count)
            )
    except Exception as e:
        logger.warning("Failed to log task: %s", e)


def _update_quota(action: str, count: int):
    """No-op placeholder; quota is derived from linkedin_tasks table counts."""
    pass
