#!/bin/bash

# 开发环境启动脚本
# 同时启动 FastAPI 和 Spectator Server

set -e

if [ -f .env ]; then
    echo "加载 .env 文件中的环境变量..."
    set -a
    source .env
    set +a
else
    echo ".env 文件未找到，跳过加载环境变量。"
fi

echo "🚀 启动开发环境..."

# 启动 FastAPI 服务器
echo "启动 FastAPI 服务器..."
cd /workspaces/osu_lazer_api
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app/ &
FASTAPI_PID=$!

# 启动 Spectator Server
echo "启动 Spectator Server..."
cd /workspaces/osu_lazer_api/spectator-server
dotnet run --project osu.Server.Spectator --urls "http://0.0.0.0:8086" &
SPECTATOR_PID=$!

echo "✅ 服务已启动:"
echo "  - FastAPI: http://localhost:8000"
echo "  - Spectator Server: http://localhost:8086"
echo "  - Nginx (统一入口): http://localhost:8080"
echo ""
echo "按 Ctrl+C 停止所有服务"

# 等待用户中断
trap 'echo "🛑 正在停止服务..."; kill $FASTAPI_PID $SPECTATOR_PID; exit 0' INT

# 保持脚本运行
wait
