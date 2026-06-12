"""
LinkedInOps - LinkedIn 操作层
职责：搜索、连接、消息、发帖，每个操作都带选择器fallback + 重试 + 异常捕获
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from backend.linkedin.browser_adapter import BrowserAdapter

logger = logging.getLogger(__name__)

# ── 选择器加载 ──────────────────────────────────────────────

_SELECTORS_PATH = Path(__file__).parent / "selectors.json"
_selectors_cache = None


def _load_selectors() -> dict:
    """加载选择器配置（带缓存，支持热更新）"""
    global _selectors_cache
    try:
        with open(_SELECTORS_PATH) as f:
            _selectors_cache = json.load(f)
    except Exception as e:
        logger.error("[Selectors] 加载失败: %s", e)
        if _selectors_cache is None:
            _selectors_cache = {}
    return _selectors_cache


def _get_selectors(section: str, element: str) -> List[str]:
    """获取某个元素的所有候选选择器"""
    sel = _load_selectors()
    return sel.get(section, {}).get(element, [])


# ── 选择器查找工具 ─────────────────────────────────────────

async def _find_element(page, section: str, element: str, timeout: int = 5000):
    """
    按优先级尝试多个选择器，返回第一个匹配的 locator
    返回 (locator, used_selector) 或 (None, None)
    """
    selectors = _get_selectors(section, element)
    for sel in selectors:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            if count > 0:
                # 验证是否可见
                if await loc.first.is_visible(timeout=1000):
                    return loc, sel
        except Exception:
            continue
    return None, None


async def _find_and_click(page, section: str, element: str, timeout: int = 5000) -> bool:
    """查找并点击元素"""
    loc, sel = await _find_element(page, section, element, timeout)
    if loc:
        try:
            await loc.first.click(timeout=timeout)
            return True
        except Exception as e:
            logger.debug("[Click] 点击失败 (%s): %s", sel, e)
    return False


async def _find_and_fill(page, section: str, element: str, text: str, timeout: int = 5000) -> bool:
    """查找并填写文本（模拟人类打字）"""
    loc, sel = await _find_element(page, section, element, timeout)
    if loc:
        try:
            # 先点击获取焦点
            await loc.first.click(timeout=timeout)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # 清空现有内容
            await loc.first.press("Control+a")
            await asyncio.sleep(random.uniform(0.05, 0.15))
            
            # 使用 type 模拟逐字输入（而非 fill 直接设置值）
            await loc.first.type(text, delay=random.randint(50, 150))
            return True
        except Exception as e:
            logger.debug("[Fill] 填写失败 (%s): %s", sel, e)
            # fallback: 尝试 fill
            try:
                await loc.first.fill(text, timeout=timeout)
                return True
            except Exception:
                pass
    return False


# ── 重试装饰器 ─────────────────────────────────────────────

async def _with_retry(coro_factory: Callable, max_retries: int = 3, base_delay: float = 2.0):
    """
    带指数退避的重试
    coro_factory: 一个返回 coroutine 的工厂函数（每次重试需要新的协程）
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return await coro_factory()
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning("[Retry] 第%d次失败，%.1f秒后重试: %s", attempt + 1, delay, e)
                await asyncio.sleep(delay)
            else:
                logger.error("[Retry] 全部%d次尝试失败: %s", max_retries, e)
    raise last_error or RuntimeError("重试失败")


# ── LinkedIn 操作类 ─────────────────────────────────────────

class LinkedInOps:
    """
    LinkedIn 操作封装
    每个操作：选择器fallback + 重试 + 延时 + 状态上报
    """

    def __init__(self, browser: BrowserAdapter):
        self.browser = browser
        self._status_callback: Optional[Callable] = None

    def on_status(self, callback: Callable):
        """注册状态回调: callback(action: str, status: str, detail: str)"""
        self._status_callback = callback

    def _notify(self, action: str, status: str, detail: str = ""):
        if self._status_callback:
            try:
                self._status_callback(action, status, detail)
            except Exception:
                pass

    # ── 登录 ────────────────────────────────────────────────

    async def login_manual(self) -> Dict[str, Any]:
        """
        手动登录：打开 LinkedIn 登录页，等用户自己登录
        浏览器是非 headless 的，用户可以直接操作
        """
        page = await self.browser.get_page()

        # 先检查是否已登录
        try:
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            if "feed" in page.url and "login" not in page.url:
                self._notify("login", "logged_in", "已登录")
                await self.browser._save_cookies()
                return {"success": True, "status": "logged_in", "message": "已登录，无需重复登录"}
        except Exception:
            pass

        # 导航到登录页
        try:
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
            self._notify("login", "waiting", "请在浏览器中登录 LinkedIn")
            logger.info("[Login] 已打开登录页，等待用户手动登录")
        except Exception as e:
            logger.error("[Login] 打开登录页失败: %s", e)
            return {"success": False, "status": "error", "message": f"打开登录页失败: {str(e)[:200]}"}

        # 启动后台轮询，检测登录成功
        asyncio.create_task(self._wait_for_login_loop())

        return {"success": True, "status": "waiting", "message": "请在弹出的浏览器中登录 LinkedIn，登录成功后会自动保存"}

    async def _wait_for_login_loop(self):
        """后台轮询：检测用户是否登录成功（浏览器关闭则停止）"""
        page = self.browser.page
        if not page:
            return

        while True:
            try:
                if page.is_closed():
                    logger.warning("[Login] 浏览器已关闭，停止等待")
                    self._notify("login", "cancelled", "浏览器已关闭")
                    return

                current_url = page.url
                if "linkedin.com" in current_url and "login" not in current_url and "checkpoint" not in current_url:
                    # 可能已登录，去 feed 页确认
                    try:
                        await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
                        await asyncio.sleep(2)
                    except Exception:
                        pass

                    if "feed" in page.url and "login" not in page.url:
                        await self.browser._save_cookies()
                        self._notify("login", "logged_in", "登录成功")
                        logger.info("[Login] 用户手动登录成功")
                        return

                # 检查是否有登录错误提示
                error_el = await page.query_selector('.alert-content, .form-error, #error-for-username, #error-for-password')
                if error_el:
                    error_text = await error_el.text_content()
                    if error_text and error_text.strip():
                        self._notify("login", "error", f"登录错误: {error_text.strip()}")
                        logger.warning("[Login] 登录页错误: %s", error_text.strip())

            except Exception as e:
                logger.debug("[Login] 轮询异常: %s", e)

            await asyncio.sleep(3)

    async def ensure_logged_in(self, email: str = "", password: str = "") -> Dict[str, Any]:
        """
        确保已登录 LinkedIn
        1. 恢复 cookie 检查是否已登录
        2. 如果未登录，返回 login_required（不自动填密码）
        """
        page = await self.browser.get_page()

        # 检查 cookie 是否有效
        try:
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            if "feed" in page.url and "login" not in page.url:
                self._notify("login", "logged_in", "已登录")
                await self.browser._save_cookies()
                return {"success": True, "status": "logged_in", "message": "已登录"}
        except Exception as e:
            logger.debug("[Login] 登录检查失败: %s", e)

        # 未登录，需要用户手动登录
        self._notify("login", "need_login", "请重新登录 LinkedIn")
        return {"success": False, "status": "need_login", "message": "LinkedIn 未登录或会话已过期，请重新登录", "login_required": True}

    # ── 搜索 ────────────────────────────────────────────────

    async def search_people(self, keywords: str, market: str = "US", max_results: int = 50,
                            on_progress: Optional[Callable] = None) -> Dict[str, Any]:
        """
        搜索 LinkedIn 用户
        返回 {success, results: [{name, url, title, location}], count}
        """
        self._notify("search", "running", f"搜索: {keywords}")

        geo_urns = {
            "US": "urn:li:fs_geo:103644278",
            "EU": "urn:li:fs_geo:100506914",
            "ME": "",
            "ASIA": "urn:li:fs_geo:102890851",
        }

        async def _do_search():
            page = await self.browser.get_page()

            encoded = keywords.replace(" ", "%20")
            geo_urn = geo_urns.get(market.upper(), "")
            geo_param = f"&geoUrn={geo_urn}" if geo_urn else ""
            url = f"https://www.linkedin.com/search/results/people/?keywords={encoded}{geo_param}"

            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(5, 8))

            # 关闭可能出现的弹窗
            await self.browser.dismiss_popups()

            # 滚动加载更多
            for _ in range(min(max_results // 10, 5)):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(random.uniform(1, 2))

            # 提取结果 - 用 JS 做多重匹配
            results = await page.evaluate("""() => {
                const links = document.querySelectorAll('a[href*="/in/"]');
                const seen = new Set();
                const items = [];
                for (const link of links) {
                    const href = link.getAttribute('href');
                    if (!href || seen.has(href.split('?')[0])) continue;
                    seen.add(href.split('?')[0]);
                    
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
                    
                    const vanity = href.split('/in/')[1]?.split('?')[0]?.replace('/', '') || '';
                    let title = '', location = '';
                    const filtered = lines.filter(l =>
                        l !== name && !l.includes('Connect') && !l.includes('Message') &&
                        l !== 'LinkedIn Member' && l.length > 3 && !l.match(/^\\d/)
                    );
                    if (filtered.length >= 1) title = filtered[0];
                    if (filtered.length >= 2) location = filtered[1];
                    items.push({name, vanity, url: href.split('?')[0], title, location});
                }
                return items;
            }""")

            return results[:max_results]

        try:
            results = await _with_retry(_do_search)
            self._notify("search", "done", f"找到 {len(results)} 个结果")
            logger.info("[Search] '%s' 找到 %d 个结果", keywords, len(results))
            return {"success": True, "results": results, "count": len(results)}
        except Exception as e:
            self._notify("search", "error", str(e)[:200])
            logger.error("[Search] 搜索失败: %s", e)
            return {"success": False, "results": [], "count": 0, "error": str(e)[:200]}

    # ── 发送连接请求 ────────────────────────────────────────

    async def send_connect(self, profile_url: str, note: str = "") -> Dict[str, Any]:
        """
        向单个用户发送连接请求
        返回 {success, status, message}
        """

        async def _do_connect():
            page = await self.browser.get_page()
            vanity = profile_url.split("/in/")[-1].strip("/")

            # 方式1: 用 preload invite dialog（更可靠）
            invite_url = f"https://www.linkedin.com/preload/custom-invite/?vanityName={vanity}"
            try:
                await page.goto(invite_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(random.uniform(3, 5))

                # 检查是否弹出了邀请对话框
                send_loc, send_sel = await _find_element(page, "connect", "send_button")
                if send_loc:
                    # 如果需要添加备注
                    if note:
                        add_note_loc, _ = await _find_element(page, "connect", "add_note_button")
                        if add_note_loc:
                            await add_note_loc.first.click()
                            await asyncio.sleep(1)
                            await _find_and_fill(page, "connect", "note_textarea", note)
                            await asyncio.sleep(1)

                    await send_loc.first.click()
                    await asyncio.sleep(random.uniform(2, 4))
                    return {"success": True, "status": "sent"}
            except Exception as e:
                logger.debug("[Connect] preload方式失败，尝试profile方式: %s", e)

            # 方式2: 访问个人主页
            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(4, 7))
            await self.browser.dismiss_popups()

            # 检查是否已连接
            already, _ = await _find_element(page, "connect", "already_connected")
            if already:
                return {"success": True, "status": "already_connected"}

            # 点击 Connect
            connect_loc, _ = await _find_element(page, "connect", "connect_button")
            if not connect_loc:
                return {"success": False, "status": "no_connect_button", "message": "找不到连接按钮"}

            await connect_loc.first.click()
            await asyncio.sleep(random.uniform(2, 4))

            # 添加备注
            if note:
                add_note_loc, _ = await _find_element(page, "connect", "add_note_button")
                if add_note_loc:
                    await add_note_loc.first.click()
                    await asyncio.sleep(1)
                    await _find_and_fill(page, "connect", "note_textarea", note)
                    await asyncio.sleep(1)

            # 发送
            send_loc, _ = await _find_element(page, "connect", "send_button")
            if send_loc:
                await send_loc.first.click()
                await asyncio.sleep(random.uniform(2, 4))
                return {"success": True, "status": "sent"}

            return {"success": False, "status": "send_failed", "message": "找不到发送按钮"}

        try:
            result = await _with_retry(_do_connect)
            status = result.get("status", "unknown")
            self._notify("connect", status, profile_url)
            return result
        except Exception as e:
            self._notify("connect", "error", str(e)[:200])
            return {"success": False, "status": "error", "message": str(e)[:200]}

    # ── 批量连接 ────────────────────────────────────────────

    async def batch_connect(self, count: int = 5, note: str = "",
                            market: str = "US") -> Dict[str, Any]:
        """
        从CRM中取新客户，批量发送连接请求
        返回 {sent, failed, skipped, details}
        """
        from backend.database import get_db_ctx

        self._notify("batch_connect", "running", f"准备发送 {count} 个连接请求")

        with get_db_ctx() as conn:
            rows = conn.execute(
                """SELECT * FROM customers 
                   WHERE status IN ('new', '新线索') 
                   AND linkedin_url IS NOT NULL AND linkedin_url != ''
                   AND linkedin_url LIKE '%/in/%'
                   ORDER BY created_at DESC LIMIT ?""",
                (count,)
            ).fetchall()

        if not rows:
            self._notify("batch_connect", "done", "没有待连接的客户")
            return {"sent": 0, "failed": 0, "skipped": 0, "details": [], "message": "没有待连接的客户"}

        sent, failed, skipped = 0, 0, 0
        details = []

        for row in rows:
            customer = dict(row)
            url = customer.get("linkedin_url", "")

            try:
                result = await self.send_connect(url, note)
                if result["success"]:
                    sent += 1
                    detail = {"name": customer["name"], "status": result["status"]}
                    details.append(detail)
                    # 更新CRM状态
                    with get_db_ctx() as conn:
                        conn.execute(
                            "UPDATE customers SET status = 'connected', updated_at = ? WHERE id = ?",
                            (datetime.now().isoformat(), customer["id"])
                        )
                else:
                    if result["status"] == "already_connected":
                        skipped += 1
                        with get_db_ctx() as conn:
                            conn.execute(
                                "UPDATE customers SET status = 'connected', updated_at = ? WHERE id = ?",
                                (datetime.now().isoformat(), customer["id"])
                            )
                    else:
                        failed += 1
                    details.append({"name": customer["name"], "status": result["status"], "message": result.get("message", "")})

                # 人类操作间隔（10-25秒）
                await asyncio.sleep(random.uniform(10, 25))

            except Exception as e:
                failed += 1
                details.append({"name": customer["name"], "status": "error", "message": str(e)[:200]})
                logger.error("[BatchConnect] %s 失败: %s", customer["name"], e)

        self._notify("batch_connect", "done", f"完成: 发送{sent}, 失败{failed}, 跳过{skipped}")
        return {"sent": sent, "failed": failed, "skipped": skipped, "details": details}

    # ── 发送消息 ────────────────────────────────────────────

    async def send_message(self, profile_url: str, message: str) -> Dict[str, Any]:
        """向单个用户发送消息"""

        async def _do_message():
            page = await self.browser.get_page()

            await page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(4, 7))
            await self.browser.dismiss_popups()

            # 点击 Message 按钮
            msg_loc, _ = await _find_element(page, "message", "message_button")
            if not msg_loc:
                return {"success": False, "status": "no_message_button", "message": "找不到消息按钮"}

            await msg_loc.first.click()
            await asyncio.sleep(random.uniform(2, 4))

            # 找到编辑器
            editor_loc, _ = await _find_element(page, "message", "editor")
            if not editor_loc:
                return {"success": False, "status": "no_editor", "message": "找不到消息编辑器"}

            # 点击编辑器
            await editor_loc.first.click()
            await asyncio.sleep(1)

            # 逐字符输入（反检测）
            for char in message:
                await editor_loc.first.type(char, delay=0)
                await asyncio.sleep(random.uniform(0.03, 0.12))

            await asyncio.sleep(random.uniform(1, 2))

            # 发送
            send_loc, _ = await _find_element(page, "message", "send_button")
            if send_loc:
                # 等待按钮可用
                for _ in range(10):
                    if await send_loc.first.is_enabled():
                        break
                    await asyncio.sleep(0.5)
                await send_loc.first.click()
                await asyncio.sleep(random.uniform(2, 3))
                return {"success": True, "status": "sent"}

            return {"success": False, "status": "send_failed", "message": "找不到发送按钮"}

        try:
            result = await _with_retry(_do_message)
            self._notify("message", result.get("status", "unknown"), profile_url)
            return result
        except Exception as e:
            self._notify("message", "error", str(e)[:200])
            return {"success": False, "status": "error", "message": str(e)[:200]}

    # ── 批量消息 ────────────────────────────────────────────

    async def batch_message(self, count: int = 5, message_template: str = "") -> Dict[str, Any]:
        """从CRM中取已连接客户，批量发送消息"""
        from backend.database import get_db_ctx

        if not message_template:
            message_template = "Hi {name}, I'd love to connect and discuss potential logistics opportunities."

        self._notify("batch_message", "running", f"准备发送 {count} 条消息")

        with get_db_ctx() as conn:
            rows = conn.execute(
                """SELECT * FROM customers 
                   WHERE status IN ('connected', '已连接')
                   AND linkedin_url IS NOT NULL AND linkedin_url != ''
                   AND linkedin_url LIKE '%/in/%'
                   ORDER BY updated_at ASC LIMIT ?""",
                (count,)
            ).fetchall()

        if not rows:
            self._notify("batch_message", "done", "没有待发消息的客户")
            return {"sent": 0, "failed": 0, "details": [], "message": "没有待发消息的客户"}

        sent, failed = 0, 0
        details = []

        for row in rows:
            customer = dict(row)
            url = customer.get("linkedin_url", "")
            msg = message_template.format(name=customer.get("name", ""))

            try:
                result = await self.send_message(url, msg)
                if result["success"]:
                    sent += 1
                    with get_db_ctx() as conn:
                        conn.execute(
                            "UPDATE customers SET status = 'messaged', updated_at = ? WHERE id = ?",
                            (datetime.now().isoformat(), customer["id"])
                        )
                else:
                    failed += 1
                details.append({"name": customer["name"], "status": result.get("status", "unknown")})

                # 人类操作间隔（15-30秒）
                await asyncio.sleep(random.uniform(15, 30))

            except Exception as e:
                failed += 1
                details.append({"name": customer["name"], "status": "error", "message": str(e)[:200]})

        self._notify("batch_message", "done", f"完成: 发送{sent}, 失败{failed}")
        return {"sent": sent, "failed": failed, "details": details}

    # ── 发帖 ────────────────────────────────────────────────

    async def publish_post(self, content: str) -> Dict[str, Any]:
        """发布 LinkedIn 帖子"""
        self._notify("post", "running", "正在发帖...")

        async def _do_post():
            page = await self.browser.get_page()

            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(4, 7))

            # 点击"开始发帖"
            start_loc, _ = await _find_element(page, "post", "start_post_button")
            if not start_loc:
                return {"success": False, "message": "找不到发帖按钮"}

            await start_loc.first.click()
            await asyncio.sleep(random.uniform(2, 4))

            # 找到编辑器
            editor_loc, _ = await _find_element(page, "post", "editor")
            if not editor_loc:
                return {"success": False, "message": "找不到帖子编辑器"}

            await editor_loc.first.click()
            await asyncio.sleep(1)

            # 逐字符输入
            for char in content:
                await editor_loc.first.type(char, delay=0)
                await asyncio.sleep(random.uniform(0.02, 0.08))

            await asyncio.sleep(random.uniform(2, 4))

            # 点击发布
            post_loc, _ = await _find_element(page, "post", "post_button")
            if not post_loc:
                return {"success": False, "message": "找不到发布按钮"}

            await post_loc.first.click()
            await asyncio.sleep(random.uniform(4, 6))

            # 保存到数据库
            from backend.database import get_db_ctx
            with get_db_ctx() as conn:
                cursor = conn.execute(
                    "INSERT INTO linkedin_posts (content, status, published_at) VALUES (?, 'published', ?)",
                    (content, datetime.now().isoformat())
                )
                post_id = cursor.lastrowid

            return {"success": True, "post_id": post_id, "message": "发帖成功"}

        try:
            result = await _with_retry(_do_post)
            self._notify("post", "done" if result["success"] else "error", result.get("message", ""))
            return result
        except Exception as e:
            self._notify("post", "error", str(e)[:200])
            return {"success": False, "message": f"发帖失败: {str(e)[:200]}"}

    # ── 状态检查 ────────────────────────────────────────────

    async def check_login_status(self) -> Dict[str, Any]:
        """检查登录状态（不触发自动登录）"""
        if not self.browser.is_running:
            return {"logged_in": False, "browser_running": False, "status": "浏览器未启动"}

        try:
            page = self.browser.page
            current_url = page.url
            if "linkedin.com" in current_url and "login" not in current_url:
                return {"logged_in": True, "browser_running": True, "status": "已登录", "url": current_url}

            # 去 feed 页验证
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(3)
            logged_in = "feed" in page.url and "login" not in page.url
            return {
                "logged_in": logged_in,
                "browser_running": True,
                "status": "已登录" if logged_in else "未登录",
                "url": page.url
            }
        except Exception as e:
            return {"logged_in": False, "browser_running": False, "status": f"检查失败: {str(e)[:100]}"}
