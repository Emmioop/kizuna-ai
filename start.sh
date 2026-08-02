#!/usr/bin/env bash
# ============================================================
#  羁绊 AI · 一键启动脚本（Linux / macOS）
#  使用：chmod +x start.sh && ./start.sh
# ============================================================
set -e

ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"

GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
RESET="\033[0m"

echo -e "$CYAN━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$RESET"
echo -e "$CYAN  🌙 羁绊 AI · 启动中  $RESET"
echo -e "$CYAN━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$RESET"

# ------- 后端依赖安装 -------
if [ ! -d "backend/venv" ]; then
  echo -e "$YELLOW[1/4] 创建 Python 虚拟环境…$RESET"
  cd "$ROOT/backend"
  python3 -m venv venv
fi

echo -e "$YELLOW[2/4] 安装后端依赖…$RESET"
cd "$ROOT/backend"
source venv/bin/activate
pip install -q -r requirements.txt

# ------- 前端依赖安装 -------
if [ ! -d "frontend/node_modules" ]; then
  echo -e "$YELLOW[3/4] 安装前端依赖（首次会慢一点）…$RESET"
  cd "$ROOT/frontend"
  npm install --silent || npm install
fi

# ------- 构建前端（后端直接托管 dist）-------
if [ ! -d "frontend/dist" ]; then
  echo -e "$YELLOW[3.5/4] 首次构建前端…$RESET"
  cd "$ROOT/frontend"
  npm run build
fi

# ------- 启动 -------
echo -e "$YELLOW[4/4] 启动后端（端口 8000）…$RESET"
cd "$ROOT/backend"
source venv/bin/activate

echo ""
echo -e "$GREEN ✅ 启动完成！浏览器打开：$RESET"
echo -e "$GREEN    http://127.0.0.1:8000  $RESET"
echo ""
echo -e "$CYAN（首次使用请在「LLM 设置」里填入你的 API Key）$RESET"
echo ""

uvicorn app:app --host 0.0.0.0 --port 8000
