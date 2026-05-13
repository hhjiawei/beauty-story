"""
微信公众号文章创作工作流 - 状态定义 (State Definitions)

定义整个工作流中所有节点的状态模型，使用 Pydantic 进行强类型校验。
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from typing_extensions import TypedDict


# ═══════════════════════════════════════════════════════════
# 基础模型
# ═══════════════════════════════════════════════════════════

class DataComparison(BaseModel):
    """数据与对比信息"""
    model_config = ConfigDict(populate_by_name=True)

    key_specific_data: str = Field(
        ...,
        alias="keySpecificData",
        description="关键具象数据（如物业费上涨20%、涉及300户居民）"
    )
    horizontal_comparison: Optional[str] = Field(
        None,
        alias="horizontalComparison",
        description="横向对比（如与周边区域、往期情况对比，无则null）"
    )


class ExtendedContent(BaseModel):
    """延伸拔高素材"""
    model_config = ConfigDict(populate_by_name=True)

    macro_background: str = Field(
        ...,
        alias="macroBackground",
        description="宏观背景环境（社会、政策背景）"
    )
    deep_reasons: str = Field(
        ...,
        alias="deepReasons",
        description="深层原因（根本原因，不局限于表面现象）"
    )
    positive_focus: str = Field(
        ...,
        alias="positiveFocus",
        description="正向落点（积极举措、改进方向，提升账号质感）"
    )


# ═══════════════════════════════════════════════════════════
# 1. 单篇文章分析节点状态 (PerArticleAnalyseNode)
# ═══════════════════════════════════════════════════════════

class PerArticleAnalyseNode(BaseModel):
    """
    热点公众号文章创作输入模型 - 单篇文章分析结果

    用于结构化描述热点事件及创作指导参数，
    可直接作为 LLM Prompt 的上下文数据源。
    """
    model_config = ConfigDict(populate_by_name=True)

    # ── 基础信息 ──
    hotspot_title: str = Field(
        ...,
        alias="hotspotTitle",
        description="热点标题/话题（精准概括事件核心，贴合公众号标题调性）"
    )
    vertical_track: str = Field(
        ...,
        alias="verticalTrack",
        description="垂直赛道"
    )
    core_demand: str = Field(
        ...,
        alias="coreDemand",
        description="核心诉求/摘要（概括热点本质，明确事件核心问题）"
    )
    emotional_tendency: Literal["positive", "negative", "neutral"] = Field(
        ...,
        alias="emotionalTendency",
        description="情感倾向（positive/negative/neutral）"
    )
    writing_style: str = Field(
        ...,
        alias="writingStyle",
        description="文风建议（口语化大白话/严肃科普/共情引导及适配理由）"
    )
    writing_structure: str = Field(
        ...,
        alias="writingStructure",
        description="行文结构建议（总分总/观点前置/案例穿插/情绪递进及理由）"
    )
    event_line: List[str] = Field(
        default_factory=list,
        alias="eventLine",
        description="事件发展经历阶段"
    )
    region_scope: str = Field(
        ...,
        alias="regionScope",
        description="精准地域范围（城市/区县/街道/小区/路段）"
    )
    public_complaints: str = Field(
        ...,
        alias="publicComplaints",
        description="民间高频吐槽点"
    )
    data_comparison: DataComparison = Field(
        ...,
        alias="dataComparison",
        description="数据&对比信息"
    )
    extended_content: ExtendedContent = Field(
        ...,
        alias="extendedContent",
        description="延伸拔高素材"
    )
    creation_ideas: List[str] = Field(
        default_factory=list,
        alias="creationIdeas",
        description="切入点与创作思路（核心字段，如普通人维权技巧、官方处置效率、痛点反思等）"
    )

    # ── 补充字段：文章特有的洗稿素材 ──
    original_quotes: List[str] = Field(
        default_factory=list,
        alias="originalQuotes",
        description="原文精彩引述（可直接引用或改编的金句、对话、评论）"
    )
    key_characters: List[str] = Field(
        default_factory=list,
        alias="keyCharacters",
        description="关键人物（事件中的核心人物及其立场、言论）"
    )
    visual_elements: List[str] = Field(
        default_factory=list,
        alias="visualElements",
        description="可视化素材建议（图片、视频、数据图表等视觉元素建议）"
    )
    emotional_highlights: List[str] = Field(
        default_factory=list,
        alias="emotionalHighlights",
        description="情绪高点（原文中最能引发读者共鸣的段落或情节）"
    )
    unique_angle: Optional[str] = Field(
        None,
        alias="uniqueAngle",
        description="独特视角（该文章独有的切入角度或观点）"
    )
    source_url: Optional[str] = Field(
        None,
        alias="sourceUrl",
        description="文章来源URL"
    )


# ═══════════════════════════════════════════════════════════
# 2. 文章汇总分析节点状态 (TotalArticleAnalyseNode)
# ═══════════════════════════════════════════════════════════

class ArticleSummary(BaseModel):
    """文章汇总摘要"""
    model_config = ConfigDict(populate_by_name=True)

    total_count: int = Field(
        ...,
        alias="totalCount",
        description="文章总数"
    )
    common_themes: List[str] = Field(
        default_factory=list,
        alias="commonThemes",
        description="共同主题（多篇文章都涉及的核心话题）"
    )
    conflicting_views: List[str] = Field(
        default_factory=list,
        alias="conflictingViews",
        description="观点冲突（不同文章之间的观点分歧）"
    )
    information_gaps: List[str] = Field(
        default_factory=list,
        alias="informationGaps",
        description="信息缺口（需要进一步搜索补充的信息）"
    )


class TotalArticleAnalyseNode(BaseModel):
    """
    多篇文章汇总分析结果

    将 List[PerArticleAnalyseNode] 进行汇总，
    提取共性、差异和补充信息。
    """
    model_config = ConfigDict(populate_by_name=True)

    summary: ArticleSummary = Field(
        ...,
        alias="summary",
        description="文章汇总摘要"
    )
    merged_event_line: List[str] = Field(
        default_factory=list,
        alias="mergedEventLine",
        description="合并后的事件时间线（按时间顺序整合所有文章的事件线）"
    )
    all_creation_ideas: List[str] = Field(
        default_factory=list,
        alias="allCreationIdeas",
        description="所有创作思路汇总（去重后的完整思路列表）"
    )
    all_key_characters: List[str] = Field(
        default_factory=list,
        alias="allKeyCharacters",
        description="所有关键人物汇总"
    )
    all_original_quotes: List[str] = Field(
        default_factory=list,
        alias="allOriginalQuotes",
        description="所有原文引述汇总"
    )
    priority_topics: List[str] = Field(
        default_factory=list,
        alias="priorityTopics",
        description="优先话题（根据热度、争议性排序的话题列表）"
    )
    raw_analysis_text: Optional[str] = Field(
        None,
        alias="rawAnalysisText",
        description="AI原始分析文本（用于调试和参考）"
    )


# ═══════════════════════════════════════════════════════════
# 3. 网络搜索补充节点状态 (ArticleSearchNode)
# ═══════════════════════════════════════════════════════════

class SearchSource(BaseModel):
    """搜索来源信息"""
    model_config = ConfigDict(populate_by_name=True)

    platform: str = Field(
        ...,
        alias="platform",
        description="来源平台（知乎/今日头条/微博/百度等）"
    )
    url: Optional[str] = Field(
        None,
        alias="url",
        description="来源链接"
    )
    author: Optional[str] = Field(
        None,
        alias="author",
        description="作者/发布者"
    )
    heat_score: Optional[int] = Field(
        None,
        alias="heatScore",
        description="热度/点赞数"
    )


class PublicOpinion(BaseModel):
    """舆论观点"""
    model_config = ConfigDict(populate_by_name=True)

    viewpoint: str = Field(
        ...,
        alias="viewpoint",
        description="观点内容"
    )
    stance: Literal["support", "oppose", "neutral", "question"] = Field(
        ...,
        alias="stance",
        description="立场（支持/反对/中立/质疑）"
    )
    source: Optional[SearchSource] = Field(
        None,
        alias="source",
        description="观点来源"
    )
    likes: Optional[int] = Field(
        None,
        alias="likes",
        description="点赞数/支持数"
    )


class ArticleSearchNode(BaseModel):
    """
    热点事件网络调研产出模型

    基于搜索引擎、官方信源、社交媒体等渠道，
    对热点事件进行事实补充、角度挖掘、素材整理与争议梳理的结构化产出。
    """
    model_config = ConfigDict(populate_by_name=True)

    # ── 基础补充 ──
    cause_process_result: str = Field(
        ...,
        alias="causeProcessResult",
        description="事件起因、经过、结果补充（完善时间线，明确事件定性，补充一线现场细节）"
    )
    topic_angle: str = Field(
        ...,
        alias="topicAngle",
        description="创作角度补充（3-5个贴合的爆款角度，结合痛点与用户需求）"
    )
    topic_material: str = Field(
        ...,
        alias="topicMaterial",
        description="支撑材料补充（官方文件、权威报道、真实案例、数据，确保可追溯）"
    )
    controversial_points: str = Field(
        ...,
        alias="controversialPoints",
        description="争议焦点梳理（网友评论、多方回应、媒体解读、高频吐槽、遗留争议）"
    )
    creation_inspiration: str = Field(
        ...,
        alias="creationInspiration",
        description="创作灵感补充（热点趋势、爆款逻辑、话题延伸、关键词优化）"
    )

    # ── 新增：搜索必要信息 ──
    key_figures_update: List[str] = Field(
        default_factory=list,
        alias="keyFiguresUpdate",
        description="关键人物最新动态（搜索中发现的人物最新发声或行动）"
    )
    related_events: List[str] = Field(
        default_factory=list,
        alias="relatedEvents",
        description="关联事件（与主事件相关的其他热点事件）"
    )
    official_response: Optional[str] = Field(
        None,
        alias="officialResponse",
        description="官方回应（政府、企业、机构的正式回应或公告）"
    )
    latest_progress: Optional[str] = Field(
        None,
        alias="latestProgress",
        description="最新进展（事件的最新动态或处理结果）"
    )
    public_opinions: List[PublicOpinion] = Field(
        default_factory=list,
        alias="publicOpinions",
        description="舆论观点汇总（来自不同平台的高赞观点）"
    )
    data_verification: List[str] = Field(
        default_factory=list,
        alias="dataVerification",
        description="数据验证（对原文数据的交叉验证结果）"
    )
    image_video_materials: List[str] = Field(
        default_factory=list,
        alias="imageVideoMaterials",
        description="图片/视频素材（可用的视觉素材链接或描述）"
    )

    # ── 搜索元信息 ──
    search_queries_used: List[str] = Field(
        default_factory=list,
        alias="searchQueriesUsed",
        description="实际使用的搜索关键词（用于追踪和优化搜索策略）"
    )
    sources: List[SearchSource] = Field(
        default_factory=list,
        alias="sources",
        description="所有信息来源汇总"
    )


# ═══════════════════════════════════════════════════════════
# 4. 写作蓝图节点状态 (ArticleBlueprintNode)
# ═══════════════════════════════════════════════════════════

class WritingAnalysis(BaseModel):
    """写作角度分析"""
    model_config = ConfigDict(populate_by_name=True)

    common_angles: List[str] = Field(
        default_factory=list,
        alias="commonAngles",
        description="他人常用写作角度（3-5个）"
    )
    mergeable_angles: List[str] = Field(
        default_factory=list,
        alias="mergeableAngles",
        description="可融合角度（2-3个，说明融合逻辑）"
    )
    opposing_angles: List[str] = Field(
        default_factory=list,
        alias="opposingAngles",
        description="可对立角度（2-3个，说明对立点）"
    )
    controversial_angles: List[str] = Field(
        default_factory=list,
        alias="controversialAngles",
        description="争议角度（2-3个，说明争议焦点）"
    )
    thought_provoking_angles: List[str] = Field(
        default_factory=list,
        alias="thoughtProvokingAngles",
        description="引发深思角度（2-3个，说明思考方向）"
    )
    recommended_angle: Optional[str] = Field(
        None,
        alias="recommendedAngle",
        description="推荐角度（综合评估后的最佳写作角度）"
    )
    angle_risk_analysis: Optional[str] = Field(
        None,
        alias="angleRiskAnalysis",
        description="角度风险分析（每个角度的风险等级评估）"
    )


class WritingStyle(BaseModel):
    """写作风格定义"""
    model_config = ConfigDict(populate_by_name=True)

    final_style: str = Field(
        ...,
        alias="finalStyle",
        description="最终确定的写作风格（口语化大白话/严肃科普/共情引导）"
    )
    style_reason: str = Field(
        ...,
        alias="styleReason",
        description="风格选择理由（结合事件特点、受众、传播目标）"
    )
    style_example: str = Field(
        ...,
        alias="styleExample",
        description="风格化表达示例（1-2个句子）"
    )
    taboo_words: List[str] = Field(
        default_factory=list,
        alias="tabooWords",
        description="禁忌词汇（该事件中应避免的敏感词汇）"
    )


class WritingTemplate(BaseModel):
    """写作模板框架"""
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(
        ...,
        alias="title",
        description="建议标题（吸引眼球，贴合热点）"
    )
    subtitle: str = Field(
        ...,
        alias="subtitle",
        description="副标题（补充说明，增强吸引力）"
    )
    introduction: str = Field(
        ...,
        alias="introduction",
        description="引言模板（引子设计，吸引读者阅读）"
    )
    body_structure: List[str] = Field(
        default_factory=list,
        alias="bodyStructure",
        description="主体段落结构（每段核心内容、逻辑关系）"
    )
    conclusion: str = Field(
        ...,
        alias="conclusion",
        description="结尾模板（升华主题，引导互动）"
    )
    suggested_cover: Optional[str] = Field(
        None,
        alias="suggestedCover",
        description="封面图建议（封面图风格、元素建议）"
    )


class WritingPlan(BaseModel):
    """写作执行计划"""
    model_config = ConfigDict(populate_by_name=True)

    core_idea: str = Field(
        ...,
        alias="coreIdea",
        description="核心创作思路（文章核心观点，贯穿全文）"
    )
    lead_in: str = Field(
        ...,
        alias="leadIn",
        description="引子设计（如何开头，吸引读者注意力）"
    )
    clues: List[str] = Field(
        default_factory=list,
        alias="clues",
        description="文章线索（3-5个关键线索，串联全文）"
    )
    reference_materials: List[str] = Field(
        default_factory=list,
        alias="referenceMaterials",
        description="参考资料清单（需收集的权威资料来源）"
    )
    writing_direction: List[str] = Field(
        default_factory=list,
        alias="writingDirection",
        description="写作方向（2-3个重点方向，确保内容聚焦）"
    )
    target_emotions: List[str] = Field(
        default_factory=list,
        alias="targetEmotions",
        description="目标情绪（希望读者在阅读过程中产生的情绪变化）"
    )
    hook_strategy: Optional[str] = Field(
        None,
        alias="hookStrategy",
        description="钩子策略（如何在开头3秒抓住读者）"
    )
    viral_potential: Optional[str] = Field(
        None,
        alias="viralPotential",
        description="传播潜力分析（为什么这篇文章可能会火）"
    )


class ArticleBlueprintNode(BaseModel):
    """
    文章写作蓝图模型

    基于热点调研与角度分析，输出完整的写作策略、风格定位、
    模板框架与执行计划，为后续文章生成提供可直接落地的创作方案。
    """
    model_config = ConfigDict(populate_by_name=True)

    writing_analysis: WritingAnalysis = Field(
        ...,
        alias="writingAnalysis",
        description="写作角度分析（常用/融合/对立/争议/深思角度）"
    )
    writing_style: WritingStyle = Field(
        ...,
        alias="writingStyle",
        description="写作风格定义（最终风格、选择理由、表达示例）"
    )
    writing_template: WritingTemplate = Field(
        ...,
        alias="writingTemplate",
        description="写作模板框架（标题/副标题/引言/主体/结尾）"
    )
    writing_plan: WritingPlan = Field(
        ...,
        alias="writingPlan",
        description="写作执行计划（核心思路/引子/线索/资料/方向）"
    )

    # ── 新增：人机协同反馈 ──
    human_feedback: Optional[str] = Field(
        None,
        alias="humanFeedback",
        description="人工反馈（修改意见）"
    )
    revision_count: int = Field(
        0,
        alias="revisionCount",
        description="修改轮次"
    )
    revision_history: List[str] = Field(
        default_factory=list,
        alias="revisionHistory",
        description="修改历史记录"
    )


# ═══════════════════════════════════════════════════════════
# 5. 大纲节点状态 (ArticlePlotNode)
# ═══════════════════════════════════════════════════════════

class GlobalStyle(BaseModel):
    """全局风格定义"""
    model_config = ConfigDict(populate_by_name=True)

    tone: str = Field(
        ...,
        alias="tone",
        description="语调（如：辛辣讽刺、温情共鸣、极简硬核）"
    )
    language_requirement: str = Field(
        ...,
        alias="languageRequirement",
        description="语言约束（如：多用短句、杜绝成语、增加互动问句）"
    )
    example_sentences: List[str] = Field(
        default_factory=list,
        alias="exampleSentences",
        description="风格样板句"
    )


class WritingContext(BaseModel):
    """写作上下文"""
    model_config = ConfigDict(populate_by_name=True)

    article_title: str = Field(
        ...,
        alias="articleTitle",
        description="最终确定的爆款标题"
    )
    core_idea: str = Field(
        ...,
        alias="coreIdea",
        description="贯穿全文的核心观点"
    )
    target_audience: str = Field(
        ...,
        alias="targetAudience",
        description="目标受众画像（便于AI调整表达深度）"
    )
    global_style: GlobalStyle = Field(
        ...,
        alias="globalStyle",
        description="全局风格"
    )


class GoldSentenceRequirement(BaseModel):
    """金句要求"""
    model_config = ConfigDict(populate_by_name=True)

    position: Literal["end", "middle", "none"] = Field(
        ...,
        alias="position",
        description="金句预留位置（end/middle/none）"
    )
    theme: str = Field(
        ...,
        alias="theme",
        description="金句的灵魂/核心词"
    )


class WordCountRange(BaseModel):
    """字数范围"""
    model_config = ConfigDict(populate_by_name=True)

    min: int = Field(
        ...,
        alias="min",
        description="最小字数",
        ge=0
    )
    max: int = Field(
        ...,
        alias="max",
        description="最大字数",
        ge=0
    )


class ContentSegment(BaseModel):
    """
    内容段落

    文章由多个段落组成，每个段落有独立的逻辑、情绪、修辞目标。
    """
    model_config = ConfigDict(populate_by_name=True)

    segment_index: int = Field(
        ...,
        alias="segmentIndex",
        description="序列号",
        ge=0
    )
    segment_type: Literal["introduction", "body", "conclusion"] = Field(
        ...,
        alias="segmentType",
        description="段落类型（introduction/body/conclusion）"
    )
    section_title: Optional[str] = Field(
        None,
        alias="sectionTitle",
        description="本段小标题（如果有）"
    )
    core_logic: str = Field(
        ...,
        alias="coreLogic",
        description="本段必须要讲透的逻辑点"
    )
    key_information: List[str] = Field(
        default_factory=list,
        alias="keyInformation",
        description="必须包含的客观事实或线索（来自 clues/reference）"
    )
    emotional_objective: str = Field(
        ...,
        alias="emotionalObjective",
        description="读者情绪预期（如：认知失调、深表同情、恍然大悟）"
    )
    rhetorical_device: str = Field(
        ...,
        alias="rhetoricalDevice",
        description="建议使用的修辞（如：排比、反问、故事引入）"
    )
    gold_sentence_requirement: GoldSentenceRequirement = Field(
        ...,
        alias="goldSentenceRequirement",
        description="金句预留要求"
    )
    word_count_range: WordCountRange = Field(
        ...,
        alias="wordCountRange",
        description="字数范围"
    )
    transition_to_next: Optional[str] = Field(
        None,
        alias="transitionToNext",
        description="如何丝滑地引出下一段的内容暗示"
    )
    # ── 新增 ──
    required_materials: List[str] = Field(
        default_factory=list,
        alias="requiredMaterials",
        description="本段必须使用的素材（引用、数据、案例等）"
    )
    forbidden_content: List[str] = Field(
        default_factory=list,
        alias="forbiddenContent",
        description="本段应避免的内容（敏感点、重复信息等）"
    )


class ArticlePlotNode(BaseModel):
    """
    文章写作指令模型

    作为文章生成节点的直接输入，结构化描述标题、核心观点、
    目标受众、全局风格，以及逐段落的写作要求。
    """
    model_config = ConfigDict(populate_by_name=True)

    writing_context: WritingContext = Field(
        ...,
        alias="writingContext",
        description="写作上下文（标题、核心观点、受众、风格）"
    )
    content_segments: List[ContentSegment] = Field(
        default_factory=list,
        alias="contentSegments",
        description="内容段落列表（按顺序排列，每段独立定义逻辑、情绪、修辞）"
    )
    global_checklist: List[str] = Field(
        default_factory=list,
        alias="globalChecklist",
        description="写作完成后的自查准则"
    )

    # ── 新增：人机协同反馈 ──
    human_feedback: Optional[str] = Field(
        None,
        alias="humanFeedback",
        description="人工反馈（修改意见）"
    )
    revision_count: int = Field(
        0,
        alias="revisionCount",
        description="修改轮次"
    )
    revision_history: List[str] = Field(
        default_factory=list,
        alias="revisionHistory",
        description="修改历史记录"
    )
    overall_word_count: WordCountRange = Field(
        default_factory=lambda: WordCountRange(min=1500, max=3000),
        alias="overallWordCount",
        description="全文字数范围"
    )


# ═══════════════════════════════════════════════════════════
# 6. 文章写作节点状态 (ArticleOutputNode)
# ═══════════════════════════════════════════════════════════

class GoldenSentence(BaseModel):
    """金句标注"""
    model_config = ConfigDict(populate_by_name=True)

    position: str = Field(
        ...,
        alias="position",
        description="金句位置（如：第3段）"
    )
    text: str = Field(
        ...,
        alias="text",
        description="金句内容"
    )


class ArticlePart(BaseModel):
    """
    文章分段

    对应生成文章的一个独立段落/部分，包含完整内容、金句、
    转发语及阅读节奏说明。
    """
    model_config = ConfigDict(populate_by_name=True)

    part_index: int = Field(
        ...,
        alias="partIndex",
        description="段落编号",
        ge=1
    )
    title_alternatives: List[str] = Field(
        default_factory=list,
        alias="titleAlternatives",
        description="文章标题（主标题及1-2个备选）"
    )
    content: str = Field(
        ...,
        alias="content",
        description="正文（按 contentSegments 顺序输出，严格遵循节奏与留白要求）"
    )
    golden_sentences: List[GoldenSentence] = Field(
        default_factory=list,
        alias="goldenSentences",
        description="金句标注"
    )
    share_texts: List[str] = Field(
        default_factory=list,
        alias="shareTexts",
        description="转发语建议（2-3条适合朋友圈的简短文案）"
    )
    reading_time: str = Field(
        ...,
        alias="readingTime",
        description="预估阅读时间（如：5分钟）"
    )
    rhythm: str = Field(
        ...,
        alias="rhythm",
        description="整体节奏简述（如：开头钩子→中段铺陈与反转→结尾落点）"
    )
    # ── 新增 ──
    actual_word_count: int = Field(
        0,
        alias="actualWordCount",
        description="实际字数"
    )


class ArticleOutputNode(BaseModel):
    """
    文章生成输出模型

    基于 ArticlePlotNode 指令生成的完整文章输出，
    按段落分块组织。
    """
    model_config = ConfigDict(populate_by_name=True)

    parts: List[ArticlePart] = Field(
        default_factory=list,
        alias="parts",
        description="文章分段输出列表"
    )
    full_text: Optional[str] = Field(
        None,
        alias="fullText",
        description="完整文章文本（所有段落拼接）"
    )
    summary: Optional[str] = Field(
        None,
        alias="summary",
        description="文章摘要（100字以内）"
    )
    keywords: List[str] = Field(
        default_factory=list,
        alias="keywords",
        description="关键词标签"
    )

    # ── 人机协同 ──
    human_feedback: Optional[str] = Field(
        None,
        alias="humanFeedback",
        description="人工反馈（修改意见）"
    )
    revision_count: int = Field(
        0,
        alias="revisionCount",
        description="修改轮次"
    )
    revision_history: List[str] = Field(
        default_factory=list,
        alias="revisionHistory",
        description="修改历史记录"
    )


# ═══════════════════════════════════════════════════════════
# 7. 排版节点状态 (CompositionNode)
# ═══════════════════════════════════════════════════════════

class CompositionElement(BaseModel):
    """排版元素"""
    model_config = ConfigDict(populate_by_name=True)

    element_type: Literal["title", "subtitle", "paragraph", "image", "blockquote", "divider", "highlight"] = Field(
        ...,
        alias="elementType",
        description="元素类型"
    )
    content: str = Field(
        ...,
        alias="content",
        description="元素内容"
    )
    style_notes: Optional[str] = Field(
        None,
        alias="styleNotes",
        description="样式说明（颜色、字号、对齐方式等）"
    )


class CompositionNode(BaseModel):
    """
    排版结果模型

    包含排版后的内容，以及排版样式说明。
    """
    model_config = ConfigDict(populate_by_name=True)

    elements: List[CompositionElement] = Field(
        default_factory=list,
        alias="elements",
        description="排版元素列表"
    )
    formatted_html: Optional[str] = Field(
        None,
        alias="formattedHtml",
        description="排版后的HTML内容"
    )
    markdown_text: Optional[str] = Field(
        None,
        alias="markdownText",
        description="Markdown格式文本"
    )
    layout_suggestions: List[str] = Field(
        default_factory=list,
        alias="layoutSuggestions",
        description="版面布局建议（图文穿插位置、留白位置等）"
    )
    cover_image_suggestion: Optional[str] = Field(
        None,
        alias="coverImageSuggestion",
        description="封面图建议"
    )

    # ── 人机协同 ──
    human_feedback: Optional[str] = Field(
        None,
        alias="humanFeedback",
        description="人工反馈（修改意见）"
    )
    revision_count: int = Field(
        0,
        alias="revisionCount",
        description="修改轮次"
    )
    revision_history: List[str] = Field(
        default_factory=list,
        alias="revisionHistory",
        description="修改历史记录"
    )


# ═══════════════════════════════════════════════════════════
# 8. 合规检查节点状态 (LegalityNode)
# ═══════════════════════════════════════════════════════════

class LegalityIssue(BaseModel):
    """合规问题"""
    model_config = ConfigDict(populate_by_name=True)

    issue_type: Literal["sensitive_word", "fact_error", "copyright_risk", "extreme_emotion", "political_risk", "privacy_risk", "ai_flavor"] = Field(
        ...,
        alias="issueType",
        description="问题类型（敏感词/事实错误/版权风险/极端情绪/政治风险/隐私风险/AI味过重）"
    )
    location: str = Field(
        ...,
        alias="location",
        description="问题位置（如：第2段第3行）"
    )
    original_text: str = Field(
        ...,
        alias="originalText",
        description="原始文本"
    )
    suggestion: str = Field(
        ...,
        alias="suggestion",
        description="修改建议"
    )
    severity: Literal["high", "medium", "low"] = Field(
        ...,
        alias="severity",
        description="严重程度"
    )


class LegalityNode(BaseModel):
    """
    合规性检查结果模型

    包含错别字检查、AI感检测、敏感内容审查等。
    """
    model_config = ConfigDict(populate_by_name=True)

    is_passed: bool = Field(
        False,
        alias="isPassed",
        description="是否通过检查"
    )
    overall_score: int = Field(
        0,
        alias="overallScore",
        description="综合评分（0-100）",
        ge=0,
        le=100
    )
    issues: List[LegalityIssue] = Field(
        default_factory=list,
        alias="issues",
        description="发现的问题列表"
    )
    typo_check: List[str] = Field(
        default_factory=list,
        alias="typoCheck",
        description="错别字检查结果"
    )
    ai_flavor_analysis: Optional[str] = Field(
        None,
        alias="aiFlavorAnalysis",
        description="AI味分析报告"
    )
    ai_flavor_score: int = Field(
        0,
        alias="aiFlavorScore",
        description="AI味评分（0-100，越低越好）",
        ge=0,
        le=100
    )
    suggestions: List[str] = Field(
        default_factory=list,
        alias="suggestions",
        description="优化建议"
    )
    corrected_text: Optional[str] = Field(
        None,
        alias="correctedText",
        description="修正后的完整文本"
    )
    check_items: List[str] = Field(
        default_factory=list,
        alias="checkItems",
        description="检查项清单（已完成的检查项目）"
    )


# ═══════════════════════════════════════════════════════════
# 9. 发布节点状态 (PublishNode)
# ═══════════════════════════════════════════════════════════

class PublishPlatform(BaseModel):
    """发布平台配置"""
    model_config = ConfigDict(populate_by_name=True)

    platform_name: str = Field(
        ...,
        alias="platformName",
        description="平台名称"
    )
    is_enabled: bool = Field(
        True,
        alias="isEnabled",
        description="是否启用"
    )
    publish_time: Optional[str] = Field(
        None,
        alias="publishTime",
        description="定时发布时间"
    )
    category: Optional[str] = Field(
        None,
        alias="category",
        description="文章分类/栏目"
    )
    tags: List[str] = Field(
        default_factory=list,
        alias="tags",
        description="文章标签"
    )


class PublishNode(BaseModel):
    """
    发布节点模型

    包含发布配置和发布结果。
    """
    model_config = ConfigDict(populate_by_name=True)

    platforms: List[PublishPlatform] = Field(
        default_factory=lambda: [PublishPlatform(platform_name="微信公众号")],
        alias="platforms",
        description="发布平台列表"
    )
    final_title: str = Field(
        ...,
        alias="finalTitle",
        description="最终发布标题"
    )
    final_content: str = Field(
        ...,
        alias="finalContent",
        description="最终发布内容"
    )
    summary: Optional[str] = Field(
        None,
        alias="summary",
        description="文章摘要"
    )
    cover_image_url: Optional[str] = Field(
        None,
        alias="coverImageUrl",
        description="封面图URL"
    )
    is_published: bool = Field(
        False,
        alias="isPublished",
        description="是否已发布"
    )
    publish_url: Optional[str] = Field(
        None,
        alias="publishUrl",
        description="发布后的文章链接"
    )
    publish_time: Optional[str] = Field(
        None,
        alias="publishTime",
        description="实际发布时间"
    )
    original_draft_path: Optional[str] = Field(
        None,
        alias="originalDraftPath",
        description="原始草稿保存路径"
    )


# ═══════════════════════════════════════════════════════════
# 10. 全局图状态 (GraphState)
# ═══════════════════════════════════════════════════════════

class GraphState(TypedDict):
    """
    全局图状态 - 贯穿整个工作流的状态容器

    使用 TypedDict 以便 LangGraph 进行状态传递。
    """

    # ── 输入层 ──
    input_path: str                                    # 文章所在目录或文件路径（工作流入口）

    # ── 文章分析层 ──
    per_article_results: List[dict]                    # 单篇文章分析结果（PerArticleAnalyseNode 的字典形式）
    total_article_results: Optional[dict]              # 汇总分析结果（TotalArticleAnalyseNode 的字典形式）

    # ── 节点产出层（按工作流顺序） ──
    search_result: Optional[dict]                      # 热点调研结果（ArticleSearchNode 的字典形式）
    blueprint_result: Optional[dict]                   # 写作蓝图结果（ArticleBlueprintNode 的字典形式）
    plot_result: Optional[dict]                        # 写作大纲结果（ArticlePlotNode 的字典形式）
    article_output: Optional[dict]                     # 写作内容结果（ArticleOutputNode 的字典形式）
    composition_result: Optional[dict]                 # 排版结果（CompositionNode 的字典形式）
    legality_result: Optional[dict]                    # 合规检查结果（LegalityNode 的字典形式）
    publish_result: Optional[dict]                     # 发布结果（PublishNode 的字典形式）

    # ── 工作流控制层 ──
    current_node: str                                  # 当前执行节点
    human_feedback: Optional[str]                      # 人工反馈（通用）
    awaiting_human: bool                               # 是否等待人工输入
    revision_count: int                                # 当前节点修改轮次
    should_continue: bool                              # 是否继续工作流
    error_message: Optional[str]                       # 错误信息

    # ── 记忆与进化层 ──
    user_memories: List[str]                           # 用户习惯记忆（从 deepagents 记忆系统读取）
    revision_memories: List[dict]                      # 修改意见记忆（用于自动进化）
