# TrendRadar MCP 常见工作流示例

本文档展示 TrendRadar MCP 工具的常见使用场景和工作流，帮助快速上手。

## 1. 基础查询工作流

### 1.1 查看今日热点
```
用户: "查看今天的新闻"
AI 调用: get_latest_news()
用户: "需要包含链接"
AI 调用: get_latest_news(include_url=True)
用户: "只显示前10条"
AI 调用: get_latest_news(limit=10, include_url=True)
```

### 1.2 查询历史新闻
```
用户: "查看昨天的新闻"
AI 调用: get_news_by_date(date="yesterday")
用户: "查看上周的新闻"
AI 调用: 
1. resolve_date_range("last week")
2. get_news_by_date(start_date=..., end_date=...)
```

### 1.3 按平台筛选
```
用户: "查看知乎和微博的新闻"
AI 调用: get_latest_news(platforms=["zhihu", "weibo"])
```

## 2. 趋势分析工作流

### 2.1 话题趋势分析
```
用户: "分析'人工智能'在过去一周的趋势"
AI 调用:
1. resolve_date_range("last 7 days")
2. analyze_topic_trend(topic="人工智能", date_range=...)
```

### 2.2 热点话题发现
```
用户: "今天有哪些热点话题"
AI 调用: get_trending_topics(extract_mode="auto_extract", top_n=20)
用户: "我关注的词出现了多少次"
AI 调用: get_trending_topics(mode="current")  # 使用预设关注词
```

### 2.3 跨平台热点聚合
```
用户: "看看哪些新闻被多个平台报道"
AI 调用: aggregate_news(date="today")
用户: "显示聚合后的前10条"
AI 调用: aggregate_news(date="today", limit=10)
```

## 3. 深度分析工作流

### 3.1 情感分析
```
用户: "分析今天新闻的情感倾向"
AI 调用: analyze_sentiment(date="today")
用户: "分析'特斯拉'相关新闻的情感"
AI 调用: 
1. search_news(keyword="特斯拉", include_url=True)
2. analyze_sentiment(news_items=搜索结果)
```

### 3.2 时期对比
```
用户: "对比这周和上周的热点变化"
AI 调用:
1. resolve_date_range("this week")
2. resolve_date_range("last week")
3. compare_periods(period1=..., period2=..., mode="overview")
```

### 3.3 数据洞察
```
用户: "哪个平台最活跃"
AI 调用: analyze_data_insights(mode="activity_stats")
用户: "不同平台对'AI'的关注度对比"
AI 调用: analyze_data_insights(keyword="AI", mode="platform_compare")
```

## 4. RSS 订阅工作流

### 4.1 查看最新 RSS
```
用户: "查看 Hacker News 的最新文章"
AI 调用: get_latest_rss(feeds=["hacker-news"])
用户: "查看最近3天的RSS内容"
AI 调用: get_latest_rss(days=3)
```

### 4.2 RSS 搜索
```
用户: "在RSS中搜索'机器学习'相关内容"
AI 调用: search_rss(keyword="机器学习")
用户: "在Hacker News中搜索'Python'"
AI 调用: search_rss(keyword="Python", feeds=["hacker-news"])
```

### 4.3 RSS 状态检查
```
用户: "RSS源状态如何"
AI 调用: get_rss_feeds_status()
```

## 5. 文章阅读工作流

### 5.1 阅读单篇文章
```
用户: "阅读这篇新闻的详细内容"
AI 工作流:
1. 先搜索新闻获取链接: search_news(keyword="...", include_url=True)
2. 选择特定链接: read_article(url="https://...")
```

### 5.2 批量阅读文章
```
用户: "阅读关于'iPhone 16'的所有文章内容"
AI 工作流:
1. 搜索相关新闻: search_news(keyword="iPhone 16", include_url=True, limit=5)
2. 提取链接列表
3. 批量阅读: read_articles_batch(urls=[...])
```

## 6. 系统管理工作流

### 6.1 系统状态检查
```
用户: "系统运行正常吗"
AI 调用序列:
1. get_system_status()
2. get_storage_status()
3. list_available_dates()
```

### 6.2 配置查看
```
用户: "当前配置是什么"
AI 调用: get_current_config()
用户: "支持哪些平台"
AI 调用: get_current_config(section="platforms")
```

### 6.3 手动触发抓取
```
用户: "抓取最新的知乎新闻"
AI 调用: trigger_crawl(platforms=["zhihu"], save_data=true)
用户: "临时查询微博热点（不保存）"
AI 调用: trigger_crawl(platforms=["weibo"], save_data=false)
```

## 7. 存储同步工作流

### 7.1 数据同步
```
用户: "从远程同步最近7天数据"
AI 调用:
1. resolve_date_range("last 7 days")
2. sync_from_remote(days=7)
```

### 7.2 存储状态检查
```
用户: "本地有多少数据"
AI 调用: list_available_dates(source="local")
用户: "远程有哪些数据"
AI 调用: list_available_dates(source="remote")
```

## 8. 通知推送工作流

### 8.1 检查通知渠道
```
用户: "已配置哪些通知渠道"
AI 调用: get_notification_channels()
```

### 8.2 发送通知
```
用户: "把今天的热点摘要发到飞书"
AI 工作流:
1. generate_summary_report(type="daily")
2. send_notification(message=报告内容, channels=["feishu"])
用户: "发送测试消息到所有渠道"
AI 调用: send_notification(message="测试消息", channels="all")
```

## 9. 组合工作流示例

### 9.1 完整热点分析报告
```
用户: "给我一份今天的完整热点分析报告"
AI 工作流:
1. get_latest_news(limit=50, include_url=true)
2. get_trending_topics(extract_mode="auto_extract", top_n=15)
3. aggregate_news(date="today")
4. analyze_sentiment(date="today")
5. 整合结果生成报告
```

### 9.2 话题追踪
```
用户: "追踪'新能源汽车'话题一周的变化"
AI 工作流:
1. resolve_date_range("last 7 days")
2. 每天数据: for date in date_range: get_news_by_date(date=date, keyword="新能源汽车")
3. analyze_topic_trend(topic="新能源汽车", date_range=...)
4. compare_periods(...)
```

### 9.3 多源信息聚合
```
用户: "汇总今天的所有信息来源"
AI 工作流:
1. 热榜新闻: get_latest_news(include_url=true)
2. RSS内容: get_latest_rss(include_summary=true)
3. 聚合分析: aggregate_news(date="today")
4. 生成综合摘要
```

## 最佳实践提示

### 日期解析优先
- 始终优先使用 `resolve_date_range` 解析自然语言日期
- 确保所有日期相关工具使用一致的日期范围

### 分页与限制
- 明确指定 `limit` 参数控制返回数据量
- 使用 `include_url` 和 `include_summary` 控制 token 消耗

### 错误处理
- 先检查 `get_system_status()` 确保系统正常
- 使用 `list_available_dates()` 确认查询日期有数据

### 性能优化
- 批量操作使用 `read_articles_batch` 而非多次 `read_article`
- 需要链接时再设置 `include_url=true`，默认 false 节省 token

### 渠道适配
- 发送通知前使用 `get_notification_channels()` 检查可用渠道
- 使用 `get_channel_format_guide()` 了解各渠道格式要求