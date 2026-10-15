#!/bin/bash
# Aviation Briefing 一键启动 (macOS)
# 双击本文件即可启动服务器并打开浏览器

cd "$(dirname "$0")"

echo "=============================================="
echo "  Aviation Briefing 启动中..."
echo "=============================================="

# 获取本机IP（供手机访问）
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "")

echo ""
echo "  本机访问:   http://localhost:8080"
if [ -n "$IP" ]; then
  echo "  手机访问:   http://$IP:8080  (需同一WiFi)"
fi
echo ""
echo "  手机添加主屏幕: Safari打开 → 分享 → 添加到主屏幕"
echo "  按 Ctrl+C 停止服务器"
echo "=============================================="
echo ""

# 延迟打开浏览器
( sleep 2 && open "http://localhost:8080" ) &

# 检查 python3
if ! command -v python3 >/dev/null 2>&1; then
  echo "  [错误] 未检测到 python3。"
  echo "  请在终端运行: xcode-select --install"
  echo "  或从 https://www.python.org/downloads/ 安装后重试。"
  echo ""
  read -n 1 -s -r -p "  按任意键退出..."
  exit 1
fi

# 无需安装任何第三方库，直接运行（纯标准库）
python3 server.py
