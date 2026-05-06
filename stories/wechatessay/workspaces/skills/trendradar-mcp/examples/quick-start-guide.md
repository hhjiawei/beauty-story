# TrendRadar MCP 快速开始指南

本指南帮助您快速启动和运行 TrendRadar MCP 服务器，并通过 AI 助手进行新闻热点分析。

## 1. 环境准备

### 1.1 系统要求
- Python 3.12 或更高版本
- Git（用于克隆项目）
- 网络连接（用于抓取新闻数据）

### 1.2 获取 TrendRadar 项目
```bash
# 克隆项目
git clone https://github.com/sansan0/TrendRadar.git
cd TrendRadar

# 或使用您已有的本地副本（假设在 D:/TrendRadar）
```

### 1.3 安装依赖
```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -e .
```

## 2. 快速启动 MCP 服务器

### 2.1 方式一：使用启动脚本
```bash
# Windows
scripts\start-mcp-server.bat

# Linux/Mac
chmod +x scripts/start-mcp-server.sh
./scripts/start-mcp-server.sh
```

### 2.2 方式二：直接运行
```bash
# stdio 模式（默认，适合本地 AI 助手连接）
trendradar-mcp

# HTTP 模式（适合远程连接）
trendradar-mcp --transport=http --host=0.0.0.0 --port=3333
```

### 2.3 方式三：Python 模块运行
```bash
python -m mcp_server.server
```

## 3. 配置 AI 助手连接

### 3.1 opencode 配置
在 opencode 的 MCP 配置文件中添加：

```json
{
  "mcpServers": {
    "trendradar": {
      "command": "trendradar-mcp",
      "args": ["--transport=stdio"],
      "env": {
        "TRENDRADAR_PROJECT_ROOT": "D:/TrendRadar"
      }
    }
  }
}
```

### 3.2 环境变量设置
```bash
# Windows (命令提示符)
set TRENDRADAR_PROJECT_ROOT=D:\TrendRadar

# Windows (PowerShell)
$env:TRENDRADAR_PROJECT_ROOT="D:\TrendRadar"

# Linux/Mac
export TRENDRADAR_PROJECT_ROOT="/path/to/TrendRadar"
```

## 4. 首次运行和数据抓取

### 4.1 手动触发数据抓取
通过 AI 助手执行：
```
"抓取今天的新闻数据并保存"
```
或直接运行：
```bash
# 抓取所有平台数据
trendradar --crawl

# 抓取特定平台
trendradar --crawl --platforms zhihu,weibo
```

### 4.2 验证数据抓取
```bash
# 查看数据目录
ls output/

# 或通过 AI 助手查询
"查看系统状态"
"列出可用的数据日期"
```

## 5. 基础使用示例

### 5.1 查询今日热点
```
"查看今天的新闻"
"显示前10条新闻，需要包含链接"
"只看知乎和微博的新闻"
```

### 5.2 历史数据查询
```
"查询昨天的新闻"
"查看上周的热点"
"查询2025-01-15的新闻"
```

### 5.3 热点分析
```
"今天有哪些热点话题"
"分析'人工智能'的趋势"
"看看哪些新闻被多个平台报道"
```

## 6. 进阶功能

### 6.1 RSS 订阅查询
```
"查看 Hacker News 的最新文章"
"搜索 RSS 中关于'机器学习'的内容"
```

### 6.2 文章内容阅读
```
"阅读这篇新闻的详细内容"
"批量阅读关于'iPhone'的文章"
```

### 6.3 通知推送
```
"查看已配置的通知渠道"
"发送测试消息到飞书"
"推送今天的热点摘要到所有渠道"
```

## 7. 常见问题排查

### 7.1 连接失败
- 检查 MCP 服务器是否正在运行
- 验证 `TRENDRADAR_PROJECT_ROOT` 环境变量设置
- 确认 Python 版本 ≥ 3.12

### 7.2 无数据返回
- 确认已执行数据抓取：`"抓取今天的新闻"`
- 检查数据目录：`output/` 下应有 `.db` 文件
- 验证平台配置：`"查看当前配置"`

### 7.3 工具调用错误
- 检查系统状态：`"系统运行正常吗"`
- 确认日期格式：使用 `"解析最近7天"` 确保日期一致
- 查看工具列表：`"有哪些可用的工具"`

## 8. 配置自定义

### 8.1 修改平台配置
编辑 `config/config.yaml` 中的 `platforms.sources` 部分，启用/禁用所需平台。

### 8.2 添加 RSS 源
在 `config/config.yaml` 的 `rss.feeds` 部分添加自定义 RSS 源。

### 8.3 设置关键词过滤
编辑 `config/frequency_words.txt` 设置关注的关键词。

### 8.4 配置通知渠道
在 `config/config.yaml` 的 `notification.channels` 部分配置飞书、钉钉等通知渠道。

## 9. 生产环境部署

### 9.1 Docker 部署
```bash
# 拉取镜像
docker pull wantcat/trendradar-mcp

# 运行容器
docker run -p 3333:3333 \
  -v /path/to/config:/app/config \
  -v /path/to/data:/app/output \
  wantcat/trendradar-mcp
```

### 9.2 定时抓取
```bash
# 使用 crontab (Linux/Mac)
0 * * * * cd /path/to/TrendRadar && trendradar --crawl

# 使用计划任务 (Windows)
# 创建计划任务每小时运行: trendradar --crawl
```

### 9.3 反向代理配置（HTTP 模式）
```nginx
# Nginx 配置示例
location /mcp {
    proxy_pass http://localhost:3333;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

## 10. 获取帮助

### 10.1 内置帮助
```
"查看工具使用说明"
"显示配置示例"
"如何查询历史数据"
```

### 10.2 项目资源
- 项目地址: https://github.com/sansan0/TrendRadar
- MCP FAQ: `README-MCP-FAQ.md`
- 问题反馈: GitHub Issues

### 10.3 常用命令参考
```bash
# 查看版本
trendradar --version

# 查看帮助
trendradar --help
trendradar-mcp --help

# 测试连接
python -c "import mcp; print('MCP SDK 已安装')"
```

---

**提示**: 首次使用建议按顺序执行：
1. 启动 MCP 服务器
2. 配置 AI 助手连接
3. 抓取初始数据
4. 执行基础查询测试
5. 按需配置自定义选项