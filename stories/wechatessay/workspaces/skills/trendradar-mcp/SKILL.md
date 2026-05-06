# Skill: trendradar-mcp

## 概述

TrendRadar MCP技能提供了对TrendRadar项目的MCP（Model Context Protocol）服务器功能的集成支持。TrendRadar是一个AI驱动的舆情监控与热点分析工具，支持多平台热点聚合、RSS订阅、智能推送和深度分析。通过MCP服务器，AI助手可以自然语言交互方式查询新闻数据、分析趋势、获取洞察、发送通知等。

本技能旨在帮助用户通过opencode代理高效使用TrendRadar的MCP功能，包括新闻查询、趋势分析、情感分析、文章阅读和通知推送等。

## 触发条件

当用户提到以下关键词或场景时使用此技能：

- TrendRadar、舆情监控、热点分析、新闻趋势、趋势雷达
- MCP、Model Context Protocol、AI新闻分析、MCP服务器
- 查询最新新闻、搜索热点、分析趋势、新闻情感分析
- 舆情分析、热点预测、RSS订阅查询、文章内容阅读
- 发送通知到飞书、钉钉、Telegram、微信、邮件等渠道
- 新闻聚合、跨平台热点、热点话题统计

**代码检测**：当检测到导入`fastmcp`或项目结构包含`mcp_server`目录时，也应触发此技能。

## 前置要求

1. **已部署TrendRadar MCP服务器**：需要运行TrendRadar的MCP服务器（可通过Docker或本地运行）
2. **MCP客户端配置**：在opencode中配置MCP客户端连接至TrendRadar MCP服务器
3. **数据准备**：确保TrendRadar已收集新闻数据（可通过定时任务或手动抓取）
4. **Python环境**：Python 3.12+，已安装TrendRadar依赖

## 工具概览

TrendRadar MCP服务器提供27个工具，分为以下9个类别：

### 📅 日期解析工具（推荐优先调用）
- `resolve_date_range` - 解析自然语言日期表达式（如"本周"、"最近7天"）为标准日期格式

### 📊 基础数据查询（P0核心）
- `get_latest_news` - 获取最新新闻
- `get_news_by_date` - 按日期查询新闻（支持自然语言）
- `get_trending_topics` - 获取趋势话题（支持自动提取）

### 📰 RSS 数据查询
- `get_latest_rss` - 获取最新 RSS 订阅数据
- `search_rss` - 搜索 RSS 数据
- `get_rss_feeds_status` - 获取 RSS 源状态

### 🔍 智能检索工具
- `search_news` - 统一新闻搜索（关键词/模糊/实体，可含RSS）
- `find_related_news` - 相关新闻查找（支持历史数据）

### 📈 高级数据分析
- `analyze_topic_trend` - 统一话题趋势分析（热度/生命周期/爆火/预测）
- `analyze_data_insights` - 统一数据洞察分析（平台对比/活跃度/关键词共现）
- `analyze_sentiment` - 情感倾向分析
- `aggregate_news` - 跨平台新闻聚合去重
- `compare_periods` - 时期对比分析（周环比/月环比）
- `generate_summary_report` - 每日/每周摘要生成

### ⚙️ 配置与系统管理
- `get_current_config` - 获取当前系统配置
- `get_system_status` - 获取系统运行状态
- `check_version` - 检查版本更新（对比本地与远程版本）
- `trigger_crawl` - 手动触发爬取任务

### 💾 存储同步工具
- `sync_from_remote` - 从远程存储拉取数据到本地
- `get_storage_status` - 获取存储配置和状态
- `list_available_dates` - 列出本地/远程可用日期

### 📖 文章内容读取
- `read_article` - 读取单篇文章内容（Markdown格式）
- `read_articles_batch` - 批量读取多篇文章（自动限速，最多5篇）

### 📢 通知推送工具
- `get_channel_format_guide` - 获取渠道格式化策略指南（提示词）
- `get_notification_channels` - 获取已配置的通知渠道状态
- `send_notification` - 向通知渠道发送消息（自动适配格式）

## ⚙️ 默认设置说明

为了节省AI token消耗，工具采用以下默认优化策略：

| 默认设置 | 说明 | 调整方法 |
|---------|------|----------|
| **限制条数** | 默认返回50条新闻 | 对话中说"返回前10条"或"给我100条" |
| **时间范围** | 默认查询今天数据 | 说"查询昨天"、"最近一周"或"1月1日到7日" |
| **URL链接** | 默认不包含链接（每条节省约160token） | 说"需要链接"或"包含URL" |
| **关键词列表** | 默认不使用frequency_words.txt过滤新闻 | 仅在调用"热点话题"工具时使用 |

**重要提示**：AI模型的选择直接影响工具调用效果。模型越智能，调用越准确。当移除上述限制时（例如从查询今天到查询一周），首先需要本地有一周的数据，其次token消耗可能成倍增加。

**💡 提示**：本项目提供了专门的日期解析工具`resolve_date_range`，可以准确解析"最近7天"、"本周"等自然语言日期表达式，确保所有AI模型获得一致的日期范围。
**💡 提示**：当用户查询信息后没有查到消息，可以触发trigger_crawl来爬取新闻。

## 典型工作流示例

### 1. 基础新闻查询
```
用户：查看今天的新闻
代理：调用 get_latest_news()
用户：需要包含链接
代理：调用 get_latest_news(include_url=True)
```

### 2. 深度话题分析
```
用户：分析"人工智能"在过去一周的趋势
代理：
1. 调用 resolve_date_range("最近7天") 获取日期范围
2. 调用 analyze_topic_trend(topic="人工智能", date_range=...)
```

### 3. 跨平台热点发现
```
用户：看看哪些新闻被多个平台报道
代理：调用 aggregate_news(date="today")
```

### 4. 情感分析
```
用户：分析今天新闻的情感倾向
代理：调用 analyze_sentiment(date="today")
```

### 5. RSS订阅查询
```
用户：查看Hacker News的最新文章
代理：调用 get_latest_rss(feeds=['hacker-news'])
```

### 6. 文章内容阅读
```
用户：阅读这篇新闻的详细内容
代理：
1. 先通过 search_news(include_url=True) 找到新闻链接
2. 调用 read_article(url=...)
```

### 7. 通知推送
```
用户：把今天的热点摘要推送到飞书
代理：
1. 调用 generate_summary_report(type="daily")
2. 调用 send_notification(message=摘要内容, channels=["feishu"])
```

### 8. 数据同步
```
用户：从远程存储同步最近7天数据
代理：
1. 调用 resolve_date_range("最近7天") 获取日期范围
2. 调用 sync_from_remote(days=7)
```

## 配置指南

### MCP服务器部署

#### 方式一：本地Python运行（开发测试）
```bash
# 进入TrendRadar项目目录
cd D:/TrendRadar

# 安装依赖（如果使用uv）
uv sync

# 启动MCP服务器（stdio模式，默认）
trendradar-mcp

# 或启动HTTP服务器（生产推荐）
trendradar-mcp --transport=http --host=0.0.0.0 --port=3333
```

#### 方式二：Docker部署（生产推荐）
```bash
# 拉取镜像
docker pull wantcat/trendradar-mcp

# 运行容器
docker run -p 3333:3333 \
  -v /path/to/config:/app/config \
  -v /path/to/data:/app/output \
  wantcat/trendradar-mcp
```

#### 方式三：GitHub Actions自动部署
参考项目中的`.github/workflows/crawler.yml`和`.github/workflows/docker.yml`

### opencode MCP客户端配置

在opencode的MCP配置中添加TrendRadar服务器：

#### stdio模式（本地运行）：
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

#### HTTP模式（远程服务器）：
```json
{
  "mcpServers": {
    "trendradar": {
      "url": "http://localhost:3333/mcp"
    }
  }
}
```

### 环境变量配置

MCP服务器支持以下环境变量：

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `TRENDRADAR_PROJECT_ROOT` | 项目根目录路径 | 当前目录 |
| `TRENDRADAR_CONFIG_PATH` | 配置文件路径 | `config/config.yaml` |
| `TRENDRADAR_DATA_DIR` | 数据存储目录 | `output` |

## 最佳实践

### 1. 日期解析优先
在处理涉及时间范围的查询时，优先使用 `resolve_date_range` 工具确保日期一致性。

### 2. 分步查询策略
对于复杂分析，采用分步策略：
- 先搜索相关新闻
- 再分析趋势
- 最后进行情感分析

### 3. 合理控制数据量
- 明确指定数量限制（如"前20条"）
- 根据需要选择是否包含URL链接
- 使用增量查询避免重复数据

### 4. 错误处理与验证
- 检查数据可用性：使用 `list_available_dates` 确认查询日期有数据
- 验证配置状态：使用 `get_system_status` 确保系统正常运行
- 检查版本更新：使用 `check_version` 确保使用最新功能

### 5. 通知渠道管理
- 先使用 `get_notification_channels` 检查渠道状态
- 使用 `get_channel_format_guide` 了解各渠道格式要求
- 发送测试消息验证配置正确性

### 6. 数据同步策略
- 定期使用 `sync_from_remote` 同步远程数据到本地
- 使用 `get_storage_status` 监控存储状态
- 配置自动同步任务确保数据时效性

## 常见问题

### Q1: AI只显示部分结果怎么办？
**A**: 明确要求"显示所有结果，不要总结"或"列出全部50条新闻"。AI模型可能自动总结，需要明确指示完整展示。

### Q2: 如何获取文章详细内容？
**A**: 使用 `search_news(include_url=True)` 获取链接，然后使用 `read_article` 读取内容。批量阅读使用 `read_articles_batch`。

### Q3: 如何对比不同时期的热点？
**A**: 使用 `compare_periods` 工具，指定两个时期进行对比分析，支持周环比、月环比。

### Q4: 如何发送到多个通知渠道？
**A**: 在 `send_notification` 中指定多个渠道，或使用默认发送到所有已配置渠道。支持飞书、钉钉、微信、Telegram、邮件等9种渠道。

### Q5: 数据不同步怎么办？
**A**: 使用 `sync_from_remote` 从远程存储同步数据到本地。检查 `get_storage_status` 确认存储配置。

### Q6: 如何检查系统状态？
**A**: 使用 `get_system_status` 查看系统运行状态，`check_version` 检查更新，`get_current_config` 查看配置。

### Q7: 支持哪些RSS源？
**A**: 使用 `get_rss_feeds_status` 查看已配置的RSS源状态。支持自定义RSS源配置。

### Q8: 如何手动触发数据抓取？
**A**: 使用 `trigger_crawl` 工具手动触发抓取任务，支持临时查询和持久化存储两种模式。

## 示例文件

本技能提供以下示例文件，位于技能目录的相应子目录中：

### 配置文件示例
- `config/example-config.yaml` - 简化版配置文件，包含MCP服务器核心配置

### 启动脚本
- `scripts/start-mcp-server.bat` - Windows启动脚本
- `scripts/start-mcp-server.sh` - Linux/Mac启动脚本

### 使用示例
- `examples/common-workflows.md` - 常见工作流和使用模式示例
- `examples/python-client-example.py` - Python客户端调用示例
- `examples/quick-start-guide.md` - 快速开始指南

### 使用说明
- 启动脚本需要根据实际安装路径调整 `TRENDRADAR_PROJECT_ROOT`
- 配置文件可根据需要修改，支持环境变量覆盖
- 工作流示例展示了从简单查询到复杂分析的完整流程

## 资源与参考

### 项目文档
- **项目地址**：https://github.com/sansan0/TrendRadar
- **MCP FAQ中文**：`D:/TrendRadar/README-MCP-FAQ.md`
- **MCP FAQ英文**：`D:/TrendRadar/README-MCP-FAQ-EN.md`
- **Cherry Studio指南**：`D:/TrendRadar/README-Cherry-Studio.md`

### 配置文件
- **主配置**：`D:/TrendRadar/config/config.yaml`
- **时间线配置**：`D:/TrendRadar/config/timeline.yaml`
- **关键词配置**：`D:/TrendRadar/config/frequency_words.txt`

### Docker资源
- **Docker镜像**：wantcat/trendradar-mcp
- **Dockerfile**：`D:/TrendRadar/docker/`
- **Docker Compose示例**：参考项目docker目录

---

**注意**：使用本技能前请确保已正确配置TrendRadar MCP服务器并获取了相应的新闻数据。建议先运行`get_system_status`测试查询验证系统状态。

**本地项目路径**：`D:/TrendRadar`（根据实际安装位置调整）