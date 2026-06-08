# Fortune SCM App - 后端 API 规格

## 技术栈
- Python 3.9 + FastAPI + Uvicorn
- SQLite (本地存储)
- Playwright (内置浏览器)
- APScheduler (定时任务)

## API 端点

### LinkedIn 自动化
```
POST /api/linkedin/login          # 打开内置浏览器，用户手动登录
GET  /api/linkedin/status         # 检查登录状态
POST /api/linkedin/search         # 搜索目标客户
POST /api/linkedin/connect        # 发送加好友请求
POST /api/linkedin/message        # 发送消息
```

### 素材库
```
GET  /api/materials               # 获取素材列表
POST /api/materials/upload        # 上传素材（文件或文本）
DELETE /api/materials/{id}        # 删除素材
```

### AI 动态生成
```
POST /api/content/generate        # 从素材库生成动态
GET  /api/content/preview         # 预览待发布动态
POST /api/content/publish         # 发布动态到 LinkedIn
```

### 邮件
```
POST /api/email/configure         # 配置 SMTP
POST /api/email/send              # 发送 Cold Email
```

### 统计
```
GET  /api/stats/daily             # 每日统计
GET  /api/stats/customers         # 客户列表
```

### 设置
```
GET  /api/settings                # 获取设置
PUT  /api/settings                # 更新设置
```

## 数据库表
- customers (id, name, company, title, linkedin_url, email, status, notes, created_at)
- materials (id, title, content, type, tags, created_at)
- posts (id, content, status, published_at, engagement_stats)
- settings (key, value)

## 启动方式
```python
# main.py
import uvicorn
import webbrowser

if __name__ == "__main__":
    webbrowser.open("http://localhost:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765)
```

## 重要约束
- 不需要代理配置，用户自己有VPN
- LinkedIn 登录用 Playwright，Cookie 持久化到本地
- 所有数据存储在本地 SQLite
- AI 模型调用支持 OpenAI/Anthropic/自定义 API
