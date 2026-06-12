"""
BrowserAdapter - 浏览器管理层
职责：反检测、崩溃恢复、Cookie持久化、代理管理
"""

import asyncio
import json
import logging
import os
import platform
import random
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from playwright_stealth.stealth import Stealth
    _stealth = Stealth()
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False
    logging.warning("playwright-stealth not installed, using basic anti-detection")

logger = logging.getLogger(__name__)

# ── 路径配置 ──────────────────────────────────────────────────

IS_BUNDLED = getattr(sys, '_MEIPASS', None) is not None

if sys.platform == "win32":
    _USER_DATA = Path(os.environ.get("APPDATA", "")) / ".destiny"
else:
    _USER_DATA = Path.home() / ".destiny"

BROWSER_PROFILE_DIR = _USER_DATA / "linkedin-profile"
COOKIE_FILE = BROWSER_PROFILE_DIR / "cookies.json"
BROWSER_STATE_FILE = BROWSER_PROFILE_DIR / "state.json"

# ── 反检测 User-Agent 池 ─────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# 随机视口尺寸池
VIEWPORTS = [
    {"width": 1366, "height": 768},
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 800},
]


def _detect_proxy() -> str:
    """自动检测系统代理"""
    for var in ('ALL_PROXY', 'HTTPS_PROXY', 'HTTP_PROXY', 'all_proxy', 'https_proxy', 'http_proxy'):
        val = os.environ.get(var, '').strip()
        if val:
            return val

    import socket
    common_ports = [
        (7890, 'http'), (7891, 'http'),   # Clash
        (1080, 'socks5'), (1081, 'socks5'),  # SS/V2Ray
        (10808, 'socks5'), (10809, 'http'),  # V2Ray
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


# ── Stealth 脚本注入 ─────────────────────────────────────────

STEALTH_SCRIPTS = [
    # 隐藏 webdriver 标志
    """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    """,
    # 伪造 plugins
    """
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5].map(() => ({
            name: 'Chrome PDF Plugin',
            description: 'Portable Document Format',
            filename: 'internal-pdf-viewer',
        }))
    });
    """,
    # 伪造 languages
    """
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    """,
    # 伪造 hardwareConcurrency
    """
    Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
    """,
    # 覆盖 chrome runtime
    """
    window.chrome = { runtime: {} };
    """,
    # 覆盖 permissions query
    """
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters)
    );
    """,
]


class BrowserAdapter:
    """
    浏览器生命周期管理器
    - 反检测：stealth注入 + 随机UA/视口
    - 崩溃恢复：自动检测浏览器死亡并重建
    - Cookie持久化：登录状态跨会话保持
    """

    def __init__(self, proxy: str = ""):
        self._playwright = None
        self._browser_ctx = None
        self._page = None
        self._proxy = proxy or _detect_proxy()
        self._ua = random.choice(USER_AGENTS)
        self._viewport = random.choice(VIEWPORTS)
        self._launch_count = 0
        self._last_activity = 0.0
        self._on_status_change = None  # callback

        # 确保目录存在
        BROWSER_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def is_running(self) -> bool:
        """浏览器是否存活"""
        return self._page is not None and not self._page.is_closed()

    @property
    def page(self):
        return self._page

    @property
    def proxy(self) -> str:
        return self._proxy

    def set_proxy(self, proxy_url: str):
        self._proxy = proxy_url or ""

    def on_status_change(self, callback):
        """注册状态变化回调: callback(status: str, detail: str)"""
        self._on_status_change = callback

    def _notify(self, status: str, detail: str):
        if self._on_status_change:
            try:
                self._on_status_change(status, detail)
            except Exception:
                pass

    async def get_page(self, force_new: bool = False):
        """获取可用页面，如果浏览器死了自动重建"""
        if not force_new and self.is_running:
            try:
                # 心跳检测
                await self._page.evaluate("1")
                self._last_activity = time.time()
                return self._page
            except Exception:
                logger.warning("[Browser] 心跳失败，重建浏览器")
                await self._cleanup()

        return await self._launch()

    async def _launch(self):
        """启动浏览器（带反检测）"""
        from playwright.async_api import async_playwright

        self._launch_count += 1
        self._notify("launching", f"启动浏览器 (第{self._launch_count}次)")

        # 确保 Chromium 可用
        self._ensure_chromium()

        self._playwright = await async_playwright().start()

        launch_kwargs = {
            "user_data_dir": str(BROWSER_PROFILE_DIR),
            "headless": False,  # LinkedIn 检测 headless
            "args": [
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--disable-setuid-sandbox",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                f"--window-size={self._viewport['width']},{self._viewport['height']}",
            ],
            "ignore_default_args": ["--enable-automation", "--enable-logging"],
            "viewport": self._viewport,
            "user_agent": self._ua,
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "bypass_csp": True,
            "java_script_enabled": True,
        }

        if self._proxy:
            launch_kwargs["proxy"] = {"server": self._proxy}
            logger.info("[Browser] 使用代理: %s", self._proxy)

        try:
            self._browser_ctx = await self._playwright.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as e:
            logger.error("[Browser] 启动失败: %s", e)
            self._notify("error", f"浏览器启动失败: {str(e)[:200]}")
            raise

        # 注入反检测脚本
        page = self._browser_ctx.pages[0] if self._browser_ctx.pages else await self._browser_ctx.new_page()
        
        # 使用 playwright-stealth（如果可用）
        if HAS_STEALTH:
            try:
                await _stealth.apply_stealth_async(page)
                logger.info("[Browser] playwright-stealth 已应用")
            except Exception as e:
                logger.warning("[Browser] stealth 应用失败: %s, 使用基础脚本", e)
                for script in STEALTH_SCRIPTS:
                    try:
                        await page.add_init_script(script)
                    except Exception:
                        pass
        else:
            # fallback: 手动脚本
            for script in STEALTH_SCRIPTS:
                try:
                    await page.add_init_script(script)
                except Exception:
                    pass
        
        # 额外的反检测：移除 cdc_ 相关属性
        await page.add_init_script("""
            // 移除 Playwright 注入的 cdc_ 属性
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // 覆盖 toString 检测
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === Function.prototype.toString) return 'function toString() { [native code] }';
                return originalToString.call(this);
            };
        """)

        self._page = page
        self._last_activity = time.time()

        # 恢复 Cookie
        await self._restore_cookies()

        self._notify("running", "浏览器已启动")
        logger.info("[Browser] 浏览器启动成功 (UA=%s, viewport=%s)", self._ua[:50], self._viewport)
        return self._page

    async def _cleanup(self):
        """安全关闭浏览器"""
        global _page, _browser_ctx, _playwright
        try:
            if self._page and not self._page.is_closed():
                # 保存 Cookie
                await self._save_cookies()
        except Exception:
            pass

        try:
            if self._browser_ctx:
                await self._browser_ctx.close()
        except Exception:
            pass

        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass

        self._page = None
        self._browser_ctx = None
        self._playwright = None

    async def close(self):
        """关闭浏览器并保存状态"""
        await self._cleanup()
        self._notify("closed", "浏览器已关闭")
        logger.info("[Browser] 浏览器已关闭")

    async def _save_cookies(self):
        """持久化 Cookie"""
        try:
            if self._browser_ctx:
                cookies = await self._browser_ctx.cookies()
                with open(COOKIE_FILE, 'w') as f:
                    json.dump(cookies, f, indent=2)
                logger.debug("[Browser] Cookie 已保存 (%d条)", len(cookies))
        except Exception as e:
            logger.warning("[Browser] Cookie 保存失败: %s", e)

    async def _restore_cookies(self):
        """恢复 Cookie"""
        try:
            if COOKIE_FILE.exists() and self._browser_ctx:
                with open(COOKIE_FILE) as f:
                    cookies = json.load(f)
                if cookies:
                    await self._browser_ctx.add_cookies(cookies)
                    logger.info("[Browser] Cookie 已恢复 (%d条)", len(cookies))
        except Exception as e:
            logger.warning("[Browser] Cookie 恢复失败: %s", e)

    def _ensure_chromium(self):
        """确保 Chromium 可用（打包模式用内置的，开发模式按需下载）"""
        if IS_BUNDLED:
            bundled = Path(sys._MEIPASS) / 'playwright-browsers'
            if bundled.is_dir():
                os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled)
                return
            # fallback
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"
            return

        # 开发模式
        dev_browsers = _USER_DATA / "chromium"
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(dev_browsers)

        # 检查是否已下载
        if dev_browsers.is_dir():
            for entry in dev_browsers.iterdir():
                if entry.name.startswith("chromium-"):
                    return

        # 首次下载
        import subprocess
        logger.info("[Browser] 首次运行，下载 Chromium...")
        dev_browsers.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True, timeout=600,
            )
        except Exception as e:
            logger.error("[Browser] Chromium 下载失败: %s", e)

    async def save_state(self):
        """保存当前浏览器状态（用于崩溃恢复后重建）"""
        try:
            state = {
                "last_url": self._page.url if self.is_running else "",
                "last_activity": self._last_activity,
                "launch_count": self._launch_count,
            }
            with open(BROWSER_STATE_FILE, 'w') as f:
                json.dump(state, f)
        except Exception:
            pass

    async def human_delay(self, min_s: float = 2.0, max_s: float = 8.0):
        """模拟人类操作间隔（随机延时）"""
        delay = random.uniform(min_s, max_s)
        await asyncio.sleep(delay)

    async def human_type(self, selector_or_element, text: str, delay_range=(30, 120)):
        """模拟人类打字（每个字符随机延时）"""
        if hasattr(selector_or_element, 'type'):
            # 是一个 Playwright ElementHandle
            for char in text:
                await selector_or_element.type(char, delay=0)
                await asyncio.sleep(random.uniform(delay_range[0], delay_range[1]) / 1000)
        else:
            # 是一个 locator
            for char in text:
                await selector_or_element.type(char, delay=0)
                await asyncio.sleep(random.uniform(delay_range[0], delay_range[1]) / 1000)

    async def human_mouse_move(self, x: int, y: int, steps: int = 10):
        """模拟人类鼠标移动（贝塞尔曲线）"""
        if not self._page:
            return
        # 简化的贝塞尔曲线
        current = await self._page.evaluate("() => ({x: 0, y: 0})")
        for i in range(steps):
            t = i / steps
            # 三次贝塞尔
            px = current['x'] + (x - current['x']) * t
            py = current['y'] + (y - current['y']) * t + random.uniform(-5, 5)
            await self._page.mouse.move(px, py)
            await asyncio.sleep(random.uniform(0.01, 0.03))

    async def dismiss_popups(self):
        """尝试关闭各种弹窗"""
        if not self._page:
            return
        try:
            dismiss_selectors = [
                "button[aria-label='Dismiss']",
                "button:has-text('Got it')",
                "button:has-text('知道了')",
                "button.artdeco-modal__dismiss",
                "button:has-text('Close')",
            ]
            for sel in dismiss_selectors:
                try:
                    btn = self._page.locator(sel)
                    if await btn.count() > 0 and await btn.first.is_visible():
                        await btn.first.click()
                        await asyncio.sleep(0.5)
                except Exception:
                    continue
        except Exception:
            pass
