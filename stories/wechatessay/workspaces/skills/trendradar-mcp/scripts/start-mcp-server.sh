#!/bin/bash
# TrendRadar MCP 服务器启动脚本 (Linux/Mac)
# 用法: ./start-mcp-server.sh [--transport stdio|http] [--port PORT]

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 设置项目根目录（如果未设置环境变量）
if [ -z "$TRENDRADAR_PROJECT_ROOT" ]; then
    # 尝试常见安装位置
    if [ -d "/opt/TrendRadar" ]; then
        PROJECT_ROOT="/opt/TrendRadar"
    elif [ -d "$HOME/TrendRadar" ]; then
        PROJECT_ROOT="$HOME/TrendRadar"
    elif [ -d "$(pwd)/TrendRadar" ]; then
        PROJECT_ROOT="$(pwd)/TrendRadar"
    else
        echo -e "${RED}[ERROR] 找不到 TrendRadar 项目，请设置 TRENDRADAR_PROJECT_ROOT 环境变量${NC}"
        echo -e "${YELLOW}例如: export TRENDRADAR_PROJECT_ROOT=\"/path/to/TrendRadar\"${NC}"
        exit 1
    fi
    echo -e "${YELLOW}[INFO] 使用项目路径: $PROJECT_ROOT${NC}"
else
    PROJECT_ROOT="$TRENDRADAR_PROJECT_ROOT"
fi

# 参数解析
TRANSPORT="stdio"
PORT="3333"
HOST="0.0.0.0"

while [[ $# -gt 0 ]]; do
    case $1 in
        --transport)
            TRANSPORT="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --help)
            echo "用法: $0 [选项]"
            echo "选项:"
            echo "  --transport stdio|http   传输模式 (默认: stdio)"
            echo "  --host HOST              HTTP 监听地址 (默认: 0.0.0.0)"
            echo "  --port PORT              HTTP 监听端口 (默认: 3333)"
            echo "  --help                   显示此帮助信息"
            exit 0
            ;;
        *)
            echo -e "${RED}[ERROR] 未知参数: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}TrendRadar MCP 服务器启动${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "项目路径: $PROJECT_ROOT"
echo -e "传输模式: $TRANSPORT"
if [ "$TRANSPORT" = "http" ]; then
    echo -e "监听地址: $HOST"
    echo -e "监听端口: $PORT"
fi
echo

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] 未找到 Python3，请确保 Python 3.12+ 已安装${NC}"
    exit 1
fi

# 检查 Python 版本
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [[ $(echo "$PYTHON_VERSION < 3.12" | bc) -eq 1 ]]; then
    echo -e "${YELLOW}[WARNING] 当前 Python 版本: $PYTHON_VERSION，推荐使用 Python 3.12+${NC}"
    read -p "是否继续? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 检查 TrendRadar 安装
if [ ! -f "$PROJECT_ROOT/mcp_server/server.py" ]; then
    echo -e "${RED}[ERROR] 在 $PROJECT_ROOT 中找不到 TrendRadar MCP 服务器${NC}"
    echo -e "${YELLOW}请确认项目路径是否正确${NC}"
    exit 1
fi

# 检查依赖安装
if [ ! -f "$PROJECT_ROOT/uv.lock" ] && [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo -e "${YELLOW}[WARNING] 未找到依赖文件，可能需要安装依赖${NC}"
    echo -e "${YELLOW}运行: cd \"$PROJECT_ROOT\" && uv sync${NC}"
fi

# 进入项目目录
cd "$PROJECT_ROOT"

# 检查是否已安装 trendradar-mcp 命令
if ! command -v trendradar-mcp &> /dev/null; then
    echo -e "${YELLOW}[INFO] 未找到全局 trendradar-mcp 命令，尝试使用 Python 模块运行${NC}"
    MCP_CMD="python -m mcp_server.server"
else
    MCP_CMD="trendradar-mcp"
fi

# 启动服务器
echo -e "${GREEN}[INFO] 启动 MCP 服务器...${NC}"
echo -e "${YELLOW}[INFO] 按 Ctrl+C 停止服务器${NC}"
echo

if [ "$TRANSPORT" = "stdio" ]; then
    # stdio 模式
    echo -e "${GREEN}[INFO] 使用 stdio 传输模式${NC}"
    echo -e "${YELLOW}[INFO] 等待 MCP 客户端连接...${NC}"
    $MCP_CMD --transport=stdio
elif [ "$TRANSPORT" = "http" ]; then
    # HTTP 模式
    echo -e "${GREEN}[INFO] 使用 HTTP 传输模式${NC}"
    echo -e "${GREEN}[INFO] 服务器地址: http://$HOST:$PORT/mcp${NC}"
    echo -e "${YELLOW}[INFO] 等待 HTTP 客户端连接...${NC}"
    $MCP_CMD --transport=http --host="$HOST" --port="$PORT"
else
    echo -e "${RED}[ERROR] 不支持的传输模式: $TRANSPORT${NC}"
    echo -e "${YELLOW}支持的传输模式: stdio, http${NC}"
    exit 1
fi

echo
echo -e "${GREEN}[INFO] MCP 服务器已停止${NC}"