#!/bin/bash
# Fortune SCM - 一键部署到 GitHub
# 双击此文件即可自动完成所有操作

set -e

echo "🚀 Fortune SCM 一键部署脚本"
echo "================================"
echo ""

# 检查是否安装了 git
if ! command -v git &> /dev/null; then
    echo "❌ 需要先安装 Git"
    echo "请访问: https://git-scm.com/downloads"
    exit 1
fi

# 检查是否安装了 gh CLI
if ! command -v gh &> /dev/null; then
    echo "📦 正在安装 GitHub CLI..."
    brew install gh
fi

echo "🔐 请在浏览器中完成 GitHub 登录授权..."
echo ""

# 使用设备代码流登录（用户可以在手机上授权）
gh auth login --hostname github.com --git-protocol https --web

echo ""
echo "✅ GitHub 登录成功！"
echo ""

# 配置 git 用户信息
read -p "请输入你的 GitHub 用户名: " GITHUB_USERNAME
git config user.name "$GITHUB_USERNAME"
git config user.email "${GITHUB_USERNAME}@users.noreply.github.com"

echo ""
echo "📁 正在创建 GitHub 仓库..."

# 创建仓库
gh repo create fortune-scm-app --public --source=. --remote=origin --push

echo ""
echo "🔄 正在触发自动构建..."
echo ""

# 等待 Actions 启动
sleep 5

# 查看 Actions 状态
gh run list --limit 1

echo ""
echo "================================"
echo "✅ 部署完成！"
echo ""
echo "📊 构建状态: https://github.com/$GITHUB_USERNAME/fortune-scm-app/actions"
echo ""
echo "⏰ 构建大约需要 5-10 分钟"
echo "📦 构建完成后，在 Actions 页面下载 Windows 安装包"
echo ""
echo "按回车键退出..."
read
