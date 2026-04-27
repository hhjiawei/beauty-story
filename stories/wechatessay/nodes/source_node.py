# =============================================================================
# 五、Map 阶段 Node：单篇分析
# =============================================================================

async def map_analyze_single(state: MapReduceState) -> MapReduceState:
    """
    Map 阶段：读取所有文章文件，为每篇生成独立分析。
    注意：这里用顺序执行演示，生产环境建议用 asyncio.gather 并行。
    """
    input_path = state["input_path"]
    articles_content = state.get("articles_content")

    # 1. 获取文章列表
    if articles_content:
        articles = split_articles(articles_content)
        file_list = [f"inline_article_{i}" for i in range(len(articles))]
    else:
        file_list = scan_article_files(input_path)
        articles = [read_article(f) for f in file_list]

    # 过滤空内容
    valid_pairs = [(f, a) for f, a in zip(file_list, articles) if a.strip()]
    if not valid_pairs:
        return {**state, "error": "未找到有效文章内容"}

    logger.info(f"Map 阶段：共 {len(valid_pairs)} 篇文章待分析")

    # 2. 为每篇文章创建 DeepAgent 并分析
    model = os.getenv("DEEPAGENTS_MODEL", "openai:gpt-4o")
    backend = FilesystemBackend(root_dir=Path(input_path).parent if input_path else Path.cwd())

    per_results: List[ArticleAnalyseNode] = []

    for file_path, article_text in valid_pairs:
        try:
            agent = create_deep_agent(
                model=model,
                backend=backend,
                response_format=ArticleAnalyseNode,
                system_prompt="你是一个专业的微信公众号文章分析助手。",
            )

            prompt = MAP_PROMPT.format(article_content=article_text[:15000])  # 单篇截断保护
            result = await agent.ainvoke({
                "messages": [{"role": "user", "content": prompt}]
            })

            structured = result.get("structured_response")
            if isinstance(structured, dict):
                analysis = ArticleAnalyseNode.model_validate(structured)
            elif isinstance(structured, ArticleAnalyseNode):
                analysis = structured
            else:
                # 兜底解析
                msgs = result.get("messages", [])
                if msgs:
                    parsed = json.loads(msgs[-1].content)
                    analysis = ArticleAnalyseNode.model_validate(parsed)
                else:
                    raise ValueError("无结构化响应")

            per_results.append(analysis)
            logger.info(f"  ✓ {file_path} -> {analysis.hotspot_title[:30]}...")

        except Exception as e:
            logger.error(f"  ✗ {file_path} 分析失败: {e}")
            continue

    if not per_results:
        return {**state, "error": "所有文章分析均失败"}

    return {
        **state,
        "article_files": [f for f, _ in valid_pairs],
        "per_article_results": per_results,
    }


# =============================================================================
# 六、Reduce 阶段 Node：跨篇汇总
# =============================================================================

async def reduce_merge_results(state: MapReduceState) -> MapReduceState:
    """
    Reduce 阶段：将多篇分析结果汇总为一份统一的热点追踪表。
    """
    per_results = state.get("per_article_results", [])
    if not per_results:
        return {**state, "error": "Map 阶段无有效结果，无法汇总"}

    # 如果只有一篇文章，直接返回
    if len(per_results) == 1:
        return {
            **state,
            "analysis_result": per_results[0],
        }

    logger.info(f"Reduce 阶段：汇总 {len(per_results)} 篇分析结果")

    # 构建 Reduce 输入
    per_article_jsons = "\\n\\n---\\n\\n".join([
        f"【分析结果 {i + 1}】\\n{json.dumps(r.model_dump(by_alias=True), ensure_ascii=False, indent=2)}"
        for i, r in enumerate(per_results)
    ])

    model = os.getenv("DEEPAGENTS_MODEL", "openai:gpt-4o")
    backend = FilesystemBackend(root_dir=Path.cwd())

    try:
        agent = create_deep_agent(
            model=model,
            backend=backend,
            response_format=ArticleAnalyseNode,
            system_prompt="你是一个信息整合专家，擅长合并多源信息。",
        )

        prompt = REDUCE_PROMPT.format(per_article_jsons=per_article_jsons[:20000])  # 截断保护
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": prompt}]
        })

        structured = result.get("structured_response")
        if isinstance(structured, dict):
            merged = ArticleAnalyseNode.model_validate(structured)
        elif isinstance(structured, ArticleAnalyseNode):
            merged = structured
        else:
            msgs = result.get("messages", [])
            if msgs:
                parsed = json.loads(msgs[-1].content)
                merged = ArticleAnalyseNode.model_validate(parsed)
            else:
                raise ValueError("Reduce 阶段无结构化响应")

        logger.info(f"  ✓ 汇总完成: {merged.hotspot_title}")

        return {
            **state,
            "analysis_result": merged,
            "raw_response": merged.model_dump(by_alias=True),
        }

    except Exception as e:
        logger.error(f"Reduce 汇总失败: {e}")
        # 降级：返回第一篇的结果（避免完全失败）
        return {
            **state,
            "analysis_result": per_results[0],
            "error": f"Reduce 汇总失败，已降级返回首篇结果。错误: {str(e)}",
        }

