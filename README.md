# 🚀 Fortune SCM App

LinkedIn 自动化 + AI 内容生成工具，专为物流供应链 B2B 销售打造。

## 功能

- **素材库管理** — 上传文字/图片素材，标签分类，全文搜索
- **AI 动态生成** — 从素材库抽取 1-3 条素材，自动生成 LinkedIn 帖子（含 hashtag）
- **定时调度** — APScheduler 每日自动生成 + 发布
- **LinkedIn 自动化** — Playwright 内置浏览器登录、搜索客户、加好友、发消息
- **客户管理** — 客户列表、跟进记录
- **邮件营销** — SMTP Cold Email 发送

## 快速开始

### 前置要求

- Python 3.9+
- macOS / Windows / Linux

### 1. 克隆项目

```bash
cd ~/projects/fortune-scm-app
```

### 2. 一键启动

```bash
python start.py
```

`start.py` 会自动：
1. 创建虚拟环境 (`.venv/`)
2. 安装所有依赖
3. 安装 Playwright 浏览器
4. 启动 FastAPI 服务器 (http://localhost:8765)
5. 自动打开浏览器

### 3. 配置 AI

首次使用需要在 **设置页面** 配置 AI 模型：

| Provider | Model 示例 | API Key |
|----------|-----------|---------|
| OpenAI | gpt-4o-mini | sk-... |
| Anthropic | claude-3-haiku-20240307 | sk-ant-... |
| 自定义 | 任意模型名 | 任意 key |

支持任何 OpenAI 兼容 API（DeepSeek、本地 Ollama 等），只需填写 `base_url`。

### 4. 配置发布

在设置页面可以配置：
- **发布时间** — 每天几点自动生成/发布
- **每日限额** — 每天最多发布几条
- **自动发布** — 开启后每日自动生成并发布

## 项目结构

```
fortune-scm-app/
├── start.py              # 启动脚本
├── content_engine.py     # 内容引擎（素材库 + AI 生成 + 调度）
├── main.py               # FastAPI 服务器（start.py 自动生成）
├── requirements.txt      # Python 依赖
├── SPEC_BACKEND.md       # 后端 API 规格
├── SPEC_FRONTEND.md      # 前端 UI 规格
├── uploads/              # 上传的素材文件
├── fortune_scm.db        # SQLite 数据库（自动生成）
├── frontend/
│   ├── index.html        # 主页面
│   └── static/
│       ├── css/
│       └── js/
└── .venv/                # 虚拟环境（自动生成）
```

## API 端点

### 素材库
```
GET    /api/materials              # 列表（支持 ?tag=&search=&limit=&offset=）
POST   /api/materials/upload       # 上传素材
DELETE /api/materials/{id}         # 删除素材
GET    /api/materials/tags         # 所有标签
```

### AI 动态
```
POST   /api/content/generate       # 生成帖子（body: {material_ids, custom_prompt}）
GET    /api/content/preview/{id}   # 预览帖子
GET    /api/content/posts          # 帖子列表（?status=draft|published）
PUT    /api/content/posts/{id}     # 编辑帖子
DELETE /api/content/posts/{id}     # 删除帖子
POST   /api/content/publish/{id}   # 发布到 LinkedIn
```

### 设置
```
GET    /api/settings               # 获取设置
PUT    /api/settings               # 更新设置
```

### 统计
```
GET    /api/stats/daily            # 每日统计
GET    /api/stats/customers        # 客户列表
```

## 技术栈

- **后端**: Python 3.9 + FastAPI + Uvicorn
- **数据库**: SQLite (本地存储)
- **AI**: OpenAI / Anthropic / 自定义 API (通过 httpx)
- **调度**: APScheduler
- **浏览器**: Playwright
- **前端**: HTML + Tailwind CSS + Alpine.js (CDN, 无需构建)

## 手动启动

如果不想用 `start.py`，也可以手动操作：

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 安装浏览器
playwright install chromium

# 启动服务器
uvicorn main:app --host 127.0.0.1 --port 8765 --reload
```

## 注意事项

- 所有数据存储在本地 `fortune_scm.db`，无需外部数据库
- LinkedIn 登录使用 Playwright 内置浏览器，Cookie 持久化到本地
- 不需要代理配置，用户自行使用 VPN
- AI API Key 存储在本地数据库，请勿泄露
