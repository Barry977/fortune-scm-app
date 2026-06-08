# Fortune SCM 客户开发系统 — 完整需求文档

## 项目概述
基于现有 Fortune SCM App，开发完整的客户开发系统。

## 技术栈
- **后端**: FastAPI + SQLite
- **前端**: HTML/CSS/JS (Tailwind CSS + Alpine.js)
- **桌面**: pywebview (原生窗口)
- **打包**: PyInstaller

## 模块清单

### 1. 用户系统
- 登录界面（独立页面）
- 管理员账号：admin / admin123
- 子账号 CRUD（管理员可创建/删除/禁用）
- 权限隔离（每个子账号只能看自己的数据）
- JWT 认证

### 2. LinkedIn 浏览器自动化
- LinkedIn 登录界面（内置浏览器窗口）
- 自动搜索客户（按行业/职位/地区）
- 自动加好友
- 自动发消息
- 额度控制（每日上限）

### 3. AI 模型配置
- 模型选择界面（OpenAI/Claude/通义千问/文心一言/Kimi/MiMo 等）
- API Key 输入框
- 测试连接功能
- AI 生成功能（营销内容、客户分析）

### 4. 数据分析
- 客户画像分析
- 转化漏斗（搜索→加好友→通过→成交）
- 效果统计（每日/周/月报表）
- 可视化图表

### 5. CRM 系统
- 客户管理（信息/状态/标签）
- 跟进记录
- 待跟进提醒
- CSV/Excel 导入导出

### 6. 企业微信/邮件
- SMTP 邮件发送
- 邮件模板
- 批量发送
- 发送记录追踪

### 7. 桌面应用
- 原生窗口（不依赖浏览器）
- 应用图标
- 自动更新检查

## 开发顺序
并行开发所有模块，完成后统一集成测试。

## 数据库表设计
- users（用户表）
- customers（客户表）
- linkedin_accounts（LinkedIn 账号）
- linkedin_tasks（LinkedIn 任务）
- ai_configs（AI 配置）
- email_configs（邮件配置）
- email_logs（邮件记录）
- follow_ups（跟进记录）
- analytics（分析数据）
