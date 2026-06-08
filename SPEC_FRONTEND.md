# Fortune SCM App - 前端 UI 规格

## 技术栈
- 纯 HTML + Tailwind CSS (CDN) + Alpine.js (CDN)
- 无需构建步骤，直接用 Python 提供静态文件
- 后端 API 地址: http://localhost:8765

## 页面结构

### 1. 控制台 (Dashboard)
- 今日统计卡片：新增客户、加好友数、发消息数、发动态数
- 最近活动列表
- LinkedIn 登录状态指示器

### 2. LinkedIn 自动化
- 搜索条件表单：行业、职位、地区、关键词
- 搜索结果列表（带选择框）
- 批量操作按钮：加好友、发消息
- 每日限额显示

### 3. 素材库
- 素材列表（卡片布局）
- 上传表单：标题、内容（富文本）、标签
- 文件上传支持
- 标签筛选

### 4. AI 动态
- 生成按钮（从素材库随机抽取）
- 预览区域
- 发布按钮
- 历史动态列表
- AI 模型配置（API Key、模型选择）

### 5. 客户管理
- 客户列表（表格）
- 搜索和筛选
- 客户详情（跟进记录）

### 6. 设置
- AI 模型配置
- 邮箱 SMTP 配置
- 每日限额设置
- 发布时间设置

## UI 设计要求
- 深色主题（专业感）
- 左侧固定导航栏
- 响应式布局
- 中文界面
- 卡片式布局展示数据

## 文件结构
```
frontend/
├── index.html          # 主页面（单页应用）
├── static/
│   ├── css/
│   │   └── style.css   # 自定义样式
│   └── js/
│       └── app.js      # 应用逻辑
└── templates/
    └── index.html      # Jinja2 模板（如果用 FastAPI 模板渲染）
```

## API 调用示例
```javascript
// 检查 LinkedIn 状态
fetch('/api/linkedin/status').then(r => r.json())

// 上传素材
fetch('/api/materials/upload', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({title, content, tags})
})

// 生成动态
fetch('/api/content/generate', {method: 'POST'})
```
