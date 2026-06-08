from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from typing import Optional, List, Dict, Any
from datetime import datetime, date
import asyncio
import json
import os

from backend.linkedin_schemas import (
    LinkedInAction, LinkedInStatus, SearchConfig, ConnectConfig, MessageConfig,
    TaskCreate, TaskResponse, DailyQuota, LinkedInProfile
)

class LinkedInAutomation:
    """LinkedIn浏览器自动化模块"""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.is_logged_in = False
        self._playwright = None
        
        # 额度控制
        self._daily_quota: Dict[str, DailyQuota] = {}
        
        # 任务队列
        self._tasks: Dict[str, TaskResponse] = {}
        self._task_counter = 0
    
    def _get_today_quota(self) -> DailyQuota:
        """获取今日额度"""
        today = date.today().isoformat()
        if today not in self._daily_quota:
            self._daily_quota[today] = DailyQuota(date=date.today())
        return self._daily_quota[today]
    
    def _check_quota(self, action: LinkedInAction, count: int = 1) -> bool:
        """检查额度是否足够"""
        quota = self._get_today_quota()
        
        if action == LinkedInAction.SEARCH:
            return quota.search_remaining >= count
        elif action == LinkedInAction.CONNECT:
            return quota.connect_remaining >= count
        elif action == LinkedInAction.MESSAGE:
            return quota.message_remaining >= count
        return False
    
    def _consume_quota(self, action: LinkedInAction, count: int = 1):
        """消耗额度"""
        quota = self._get_today_quota()
        
        if action == LinkedInAction.SEARCH:
            quota.search_count += count
        elif action == LinkedInAction.CONNECT:
            quota.connect_count += count
        elif action == LinkedInAction.MESSAGE:
            quota.message_count += count
    
    async def start(self, headless: bool = False):
        """启动浏览器"""
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=headless,
            args=['--disable-blink-features=AutomationControlled']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        self.page = await self.context.new_page()
        
        # 注入脚本隐藏webdriver特征
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        print("[LinkedIn] 浏览器已启动")
    
    async def login(self, email: str, password: str) -> bool:
        """登录LinkedIn"""
        if not self.page:
            raise RuntimeError("浏览器未启动")
        
        try:
            # 访问登录页面
            await self.page.goto('https://www.linkedin.com/login', wait_until='networkidle')
            
            # 检查是否已经登录
            if 'feed' in self.page.url:
                self.is_logged_in = True
                print("[LinkedIn] 已经登录")
                return True
            
            # 填写邮箱
            await self.page.fill('input#username', email)
            await asyncio.sleep(0.5)
            
            # 填写密码
            await self.page.fill('input#password', password)
            await asyncio.sleep(0.5)
            
            # 点击登录按钮
            await self.page.click('button[type="submit"]')
            await self.page.wait_for_load_state('networkidle')
            
            # 检查是否登录成功
            await asyncio.sleep(3)
            
            if 'feed' in self.page.url or 'checkpoint' not in self.page.url:
                self.is_logged_in = True
                print("[LinkedIn] 登录成功")
                return True
            else:
                print(f"[LinkedIn] 登录失败，当前URL: {self.page.url}")
                return False
                
        except Exception as e:
            print(f"[LinkedIn] 登录异常: {e}")
            return False
    
    async def search_people(self, config: SearchConfig) -> List[LinkedInProfile]:
        """搜索LinkedIn用户"""
        if not self.is_logged_in:
            raise RuntimeError("未登录")
        
        if not self._check_quota(LinkedInAction.SEARCH):
            raise RuntimeError("今日搜索额度已用完")
        
        profiles = []
        
        try:
            # 构建搜索URL
            search_url = f"https://www.linkedin.com/search/results/people/?keywords={config.keywords}"
            if config.location:
                search_url += f"&location={config.location}"
            
            await self.page.goto(search_url, wait_until='networkidle')
            await asyncio.sleep(2)
            
            # 滚动加载更多结果
            for _ in range(min(config.max_results // 10, 5)):
                await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(1)
            
            # 提取搜索结果
            results = await self.page.query_selector_all('li.reusable-search__result-container')
            
            for result in results[:config.max_results]:
                try:
                    # 提取姓名
                    name_elem = await result.query_selector('span.entity-result__title-text a span')
                    name = await name_elem.inner_text() if name_elem else "Unknown"
                    
                    # 提取职位
                    headline_elem = await result.query_selector('div.entity-result__primary-subtitle')
                    headline = await headline_elem.inner_text() if headline_elem else None
                    
                    # 提取位置
                    location_elem = await result.query_selector('div.entity-result__secondary-subtitle')
                    location = await location_elem.inner_text() if location_elem else None
                    
                    # 提取链接
                    link_elem = await result.query_selector('a.app-aware-link')
                    profile_url = await link_elem.get_attribute('href') if link_elem else ""
                    
                    # 检查连接状态
                    connect_btn = await result.query_selector('button[aria-label*="Connect"]')
                    is_connected = connect_btn is None
                    
                    profile = LinkedInProfile(
                        name=name.strip(),
                        headline=headline.strip() if headline else None,
                        location=location.strip() if location else None,
                        profile_url=profile_url,
                        is_connected=is_connected,
                        connection_degree="2nd" if not is_connected else "1st"
                    )
                    profiles.append(profile)
                    
                except Exception as e:
                    print(f"[LinkedIn] 解析搜索结果异常: {e}")
                    continue
            
            # 消耗额度
            self._consume_quota(LinkedInAction.SEARCH, len(profiles))
            print(f"[LinkedIn] 搜索完成，找到 {len(profiles)} 个结果")
            
        except Exception as e:
            print(f"[LinkedIn] 搜索异常: {e}")
        
        return profiles
    
    async def connect_people(self, config: ConnectConfig) -> Dict[str, Any]:
        """发送好友请求"""
        if not self.is_logged_in:
            raise RuntimeError("未登录")
        
        if not self._check_quota(LinkedInAction.CONNECT, len(config.profile_urls)):
            raise RuntimeError("今日加好友额度不足")
        
        results = {
            "success": [],
            "failed": [],
            "skipped": []
        }
        
        for i, profile_url in enumerate(config.profile_urls):
            if i >= config.max_daily:
                results["skipped"].append(f"{profile_url}: 超过每日上限")
                continue
            
            try:
                # 访问个人主页
                await self.page.goto(profile_url, wait_until='networkidle')
                await asyncio.sleep(2)
                
                # 查找Connect按钮
                connect_btn = await self.page.query_selector('button[aria-label*="Connect"]')
                
                if not connect_btn:
                    # 可能已经连接或无法连接
                    results["skipped"].append(f"{profile_url}: 无法找到Connect按钮")
                    continue
                
                # 点击Connect
                await connect_btn.click()
                await asyncio.sleep(1)
                
                # 如果有添加note的选项
                if config.note:
                    add_note_btn = await self.page.query_selector('button[aria-label*="Add a note"]')
                    if add_note_btn:
                        await add_note_btn.click()
                        await asyncio.sleep(0.5)
                        
                        # 填写note
                        note_textarea = await self.page.query_selector('textarea#custom-message')
                        if note_textarea:
                            await note_textarea.fill(config.note)
                            await asyncio.sleep(0.5)
                
                # 发送请求
                send_btn = await self.page.query_selector('button[aria-label*="Send invitation"]')
                if send_btn:
                    await send_btn.click()
                    await asyncio.sleep(1)
                
                results["success"].append(profile_url)
                self._consume_quota(LinkedInAction.CONNECT)
                
                # 随机延迟，避免被封
                await asyncio.sleep(2 + (i % 3))
                
            except Exception as e:
                results["failed"].append(f"{profile_url}: {str(e)}")
        
        print(f"[LinkedIn] 好友请求: {len(results['success'])} 成功, {len(results['failed'])} 失败, {len(results['skipped'])} 跳过")
        return results
    
    async def send_messages(self, config: MessageConfig) -> Dict[str, Any]:
        """发送消息给已连接好友"""
        if not self.is_logged_in:
            raise RuntimeError("未登录")
        
        if not self._check_quota(LinkedInAction.MESSAGE, len(config.connection_ids)):
            raise RuntimeError("今日发消息额度不足")
        
        results = {
            "success": [],
            "failed": [],
            "skipped": []
        }
        
        for i, connection_id in enumerate(config.connection_ids):
            if i >= config.max_daily:
                results["skipped"].append(f"{connection_id}: 超过每日上限")
                continue
            
            try:
                # 构建消息页面URL
                message_url = f"https://www.linkedin.com/messaging/thread/{connection_id}/"
                await self.page.goto(message_url, wait_until='networkidle')
                await asyncio.sleep(2)
                
                # 查找消息输入框
                msg_input = await self.page.query_selector('div[contenteditable="true"]')
                
                if not msg_input:
                    results["skipped"].append(f"{connection_id}: 无法找到消息输入框")
                    continue
                
                # 输入消息
                await msg_input.fill(config.message)
                await asyncio.sleep(0.5)
                
                # 发送
                send_btn = await self.page.query_selector('button[type="submit"]')
                if send_btn:
                    await send_btn.click()
                    await asyncio.sleep(1)
                else:
                    # 尝试按Enter发送
                    await msg_input.press('Enter')
                    await asyncio.sleep(1)
                
                results["success"].append(connection_id)
                self._consume_quota(LinkedInAction.MESSAGE)
                
                # 随机延迟
                await asyncio.sleep(1 + (i % 2))
                
            except Exception as e:
                results["failed"].append(f"{connection_id}: {str(e)}")
        
        print(f"[LinkedIn] 消息发送: {len(results['success'])} 成功, {len(results['failed'])} 失败, {len(results['skipped'])} 跳过")
        return results
    
    async def get_quota(self) -> DailyQuota:
        """获取今日额度"""
        return self._get_today_quota()
    
    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        print("[LinkedIn] 浏览器已关闭")

# 全局实例
_linkedin: Optional[LinkedInAutomation] = None

async def get_linkedin() -> LinkedInAutomation:
    """获取LinkedIn自动化实例"""
    global _linkedin
    if _linkedin is None:
        _linkedin = LinkedInAutomation()
    return _linkedin

async def close_linkedin():
    """关闭LinkedIn自动化实例"""
    global _linkedin
    if _linkedin:
        await _linkedin.close()
        _linkedin = None
