@echo off
REM TrendRadar MCP 服务器启动脚本 (Windows)
REM 用法：start-mcp-server.bat [--transport stdio|http] [--port PORT]

setlocal enabledelayedexpansion

REM 设置项目根目录（如果未设置环境变量）
if "%TRENDRADAR_PROJECT_ROOT%"=="" (
    set "PROJECT_ROOT=%~dp0..\..\..\..\..\..\..\TrendRadar"
    REM 注意：这是默认路径，根据实际安装位置调整
    echo [INFO] 使用默认项目路径: %PROJECT_ROOT%
    if not exist "%PROJECT_ROOT%\mcp_server\server.py" (
        echo [ERROR] 找不到 TrendRadar 项目，请设置 TRENDRADAR_PROJECT_ROOT 环境变量
        echo [ERROR] 或修改脚本中的 PROJECT_ROOT 变量
        pause
        exit /b 1
    )
) else (
    set "PROJECT_ROOT=%TRENDRADAR_PROJECT_ROOT%"
)

REM 参数解析
set "TRANSPORT=stdio"
set "PORT=3333"
set "HOST=0.0.0.0"

:parse_args
if "%~1"=="" goto end_parse
if "%~1"=="--transport" (
    set "TRANSPORT=%~2"
    shift
    shift
    goto parse_args
)
if "%~1"=="--port" (
    set "PORT=%~2"
    shift
    shift
    goto parse_args
)
if "%~1"=="--host" (
    set "HOST=%~2"
    shift
    shift
    goto parse_args
)
if "%~1"=="--help" (
    echo 用法: %~n0.bat [选项]
    echo 选项:
    echo   --transport stdio^|http   传输模式 (默认: stdio)
    echo   --host HOST               HTTP 监听地址 (默认: 0.0.0.0)
    echo   --port PORT               HTTP 监听端口 (默认: 3333)
    echo   --help                    显示此帮助信息
    exit /b 0
)
shift
goto parse_args

:end_parse

echo ========================================
echo TrendRadar MCP 服务器启动
echo ========================================
echo 项目路径: %PROJECT_ROOT%
echo 传输模式: %TRANSPORT%
if "%TRANSPORT%"=="http" (
    echo 监听地址: %HOST%
    echo 监听端口: %PORT%
)
echo.

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] 未找到 Python，请确保 Python 3.12+ 已安装并添加到 PATH
    pause
    exit /b 1
)

REM 检查 TrendRadar 安装
cd /d "%PROJECT_ROOT%"
if not exist "mcp_server\server.py" (
    echo [ERROR] 在 %PROJECT_ROOT% 中找不到 TrendRadar MCP 服务器
    echo [ERROR] 请确认项目路径是否正确
    pause
    exit /b 1
)

REM 启动服务器
echo [INFO] 启动 MCP 服务器...
echo [INFO] 按 Ctrl+C 停止服务器
echo.

if "%TRANSPORT%"=="stdio" (
    REM stdio 模式
    echo [INFO] 使用 stdio 传输模式
    echo [INFO] 等待 MCP 客户端连接...
    trendradar-mcp --transport=stdio
) else if "%TRANSPORT%"=="http" (
    REM HTTP 模式
    echo [INFO] 使用 HTTP 传输模式
    echo [INFO] 服务器地址: http://%HOST%:%PORT%/mcp
    echo [INFO] 等待 HTTP 客户端连接...
    trendradar-mcp --transport=http --host=%HOST% --port=%PORT%
) else (
    echo [ERROR] 不支持的传输模式: %TRANSPORT%
    echo [ERROR] 支持的传输模式: stdio, http
    pause
    exit /b 1
)

echo.
echo [INFO] MCP 服务器已停止
pause