# 问题: 现在总的state改为GraphState 我现在希望读取文章所在目录或文件路径的若干文章，但是担心都读取的话，上下文太长 有社么办法 例如总结等

#  方案对比
| 方案                      | 原理               | 优点          | 缺点              | 适用场景           |
| ----------------------- | ---------------- | ----------- | --------------- | -------------- |
| **① 智能分片 + Map-Reduce** | 每篇文章独立分析，再汇总     | 并行、可扩展、质量稳定 | 实现稍复杂           | **推荐首选**，文章数量多 |
| **② 摘要筛选 + 精选分析**       | 先快速摘要所有文章，筛选关键篇目 | 保留完整分析流程    | 可能遗漏冷门角度        | 文章数量中等（10-50篇） |
| **③ 增量聚合分析**            | 逐篇读取，动态更新分析结果    | 内存友好、可流式    | 顺序依赖、难并行        | 文章极多或流式输入      |
| **④ 向量化检索（RAG）**        | 文章向量化，按查询检索相关片段  | 精准、可跨文档关联   | 需向量数据库、检索质量依赖分块 | 文章库固定、需反复查询    |

## 推荐方案：① 智能分片 + Map-Reduce
核心思路：先单篇分析 → 再跨篇汇总，类似 LangChain 的 MapReduceDocumentsChain。
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  文章 A 全文    │────→│  ArticleAnalyse │────→│  分析结果 A     │
│  (独立上下文)   │     │  (单篇分析)     │     │  (热点追踪表)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
┌─────────────────┐     ┌─────────────────┐     ┌──────┴──────────┐
│  文章 B 全文    │────→│  ArticleAnalyse │────→│  分析结果 B     │
│  (独立上下文)   │     │  (单篇分析)     │     │  (热点追踪表)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                         │
                              ...                        │
                                                         ▼
                                              ┌─────────────────┐
                                              │  Merge Node     │
                                              │  (跨篇汇总)     │
                                              │                 │
                                              │  • 合并重复事件 │
                                              │  • 补充交叉信息 │
                                              │  • 统一情感倾向 │
                                              │  • 整合创作角度 │
                                              └─────────────────┘
                                                         │
                                                         ▼
                                              ┌─────────────────┐
                                              │  最终热点追踪表  │
                                              │  (去重+完整)    │
                                              └─────────────────┘

为什么选这个方案
    1 每篇文章独立分析：单篇上下文可控，LLM 能深入理解细节
    2 并行执行：所有文章可同时分析，速度快
    3 汇总阶段做"减法"：去重、补全、统一，避免信息碎片化
    4 与 LangGraph 天然契合：Map 阶段是并行 Node，Reduce 是汇总 Node


create_deep_agent 创建的每个 agent 是独立的 LLM 调用单元，天然适合并行化。你的 Map 阶段每篇文章的分析是完全独立的，没有状态依赖，这是典型的" embarrassing parallel" 场景。

## deep_agent创建sub-agent和for循环执行
| 维度        | for 循环顺序执行   | 并行创建 sub\_agent     |
| --------- | ------------ | ------------------- |
| **执行时间**  | O(n) 线性增长    | O(1) 近似常数（受并发限制）    |
| **资源利用**  | 单线程等待 LLM 返回 | 多路并发调用              |
| **代码复杂度** | 简单           | 需要 `asyncio.gather` |
| **适用场景**  | 快速原型、文章少     | 生产环境、文章多            |

    
    import asyncio
    from typing import List, Tuple
    
    async def _analyze_one(
        file_path: str,
        article_text: str,
        model: str,
        backend: FilesystemBackend,
        MAP_PROMPT: str,
    ) -> Tuple[str, ArticleAnalyseNode]:
        """单个文章的分析任务（作为 sub_agent 的独立单元）"""
        agent = create_deep_agent(
            model=model,
            backend=backend,
            response_format=ArticleAnalyseNode,
            system_prompt="你是一个专业的微信公众号文章分析助手。",
        )
        
        prompt = MAP_PROMPT.format(article_content=article_text[:15000])
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": prompt}]
        })
        
        # 解析逻辑...
        structured = result.get("structured_response")
        if isinstance(structured, dict):
            analysis = ArticleAnalyseNode.model_validate(structured)
        elif isinstance(structured, ArticleAnalyseNode):
            analysis = structured
        else:
            msgs = result.get("messages", [])
            parsed = json.loads(msgs[-1].content)
            analysis = ArticleAnalyseNode.model_validate(parsed)
        
        return file_path, analysis
    
    
    async def map_analyze_parallel(state: MapReduceState, MAP_PROMPT=None) -> MapReduceState:
        """Map 阶段：并行分析所有文章"""
        input_path = state["input_path"]
        articles_content = state.get("articles_content")
        MAP_PROMPT = MAP_PROMPT or SOURCE_MAP_PROMPT
    
        # 1. 准备文章列表（同原逻辑）
        if articles_content:
            articles = split_articles(articles_content)
            file_list = [f"inline_article_{i}" for i in range(len(articles))]
        else:
            file_list = scan_article_files(input_path)
            articles = [read_article(f) for f in file_list]
    
        valid_pairs = [(f, a) for f, a in zip(file_list, articles) if a.strip()]
        if not valid_pairs:
            return {**state, "error": "未找到有效文章内容"}
    
        logger.info(f"Map 阶段：共 {len(valid_pairs)} 篇文章，启动并行分析")
    
        # 2. 创建所有 sub_agent 任务并并行执行
        model = os.getenv("DEEPAGENTS_MODEL", "openai:gpt-4o")
        backend = FilesystemBackend(
            root_dir=Path(input_path).parent if input_path else Path.cwd()
        )
    
        tasks = [
            _analyze_one(file_path, article_text, model, backend, MAP_PROMPT)
            for file_path, article_text in valid_pairs
        ]
    
        # 并发执行，自动收集结果
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
        # 3. 处理结果（过滤异常）
        per_results: List[ArticleAnalyseNode] = []
        success_files: List[str] = []
    
        for (file_path, _), result in zip(valid_pairs, results):
            if isinstance(result, Exception):
                logger.error(f"  ✗ {file_path} 分析失败: {result}")
                continue
            
            _, analysis = result
            per_results.append(analysis)
            success_files.append(file_path)
            logger.info(f"  ✓ {file_path} -> {analysis.hotspot_title[:30]}...")
    
        if not per_results:
            return {**state, "error": "所有文章分析均失败"}
    
        return {
            **state,
            "article_files": success_files,
            "per_article_results": per_results,
        }







## 我的model是调用kimi api方式并只有一个api-key，请问可以选择这种await asyncio.gather方式吗
可以，但需要注意 Kimi API 的并发限制。

asyncio.gather 是客户端并发，但你的请求最终都打到同一个 API Key 的 Kimi 服务端。Kimi 对单 Key 有速率限制（RPM/TPM），无脑并发会触发 429 Too Many Requests。

Kimi API 的典型限制（参考）
| 模型           | RPM（请求/分钟） | TPM（令牌/分钟） | 并发请求数   |
| ------------ | ---------- | ---------- | ------- |
| kimi-k2-5 系列 | 3-30       | 几十万        | 通常 5-10 |










