# Fortune SCM 安装说明

## 系统要求
- Python 3.8+
- macOS / Windows / Linux

## 安装步骤

### macOS / Linux
```bash
# 1. 解压文件
unzip fortune-scm-app.zip
cd fortune-scm-app

# 2. 一键启动（自动安装依赖）
python3 start.py
```

### Windows
```powershell
# 1. 解压文件
# 2. 双击 start.py 或命令行运行
python start.py
```

## 首次启动
1. 自动创建虚拟环境
2. 自动安装依赖
3. 自动启动服务器
4. 自动打开浏览器 → http://localhost:8765

## 功能说明
- **控制台**：今日统计、快速操作
- **LinkedIn 自动化**：搜索客户、自动加好友、发消息
- **素材库**：上传/管理素材、标签分类
- **AI 动态**：从素材生成动态、预览、发布
- **客户管理**：客户列表、跟进记录
- **设置**：AI 模型配置、邮箱 SMTP

## 后续更新
开发者会定期推送新版本，只需：
1. 替换文件
2. 重新运行 `python3 start.py`

## 注意事项
- 需要代理（VPN）访问 LinkedIn
- AI 动态生成需要配置模型 API
- 邮件发送需要配置 SMTP
