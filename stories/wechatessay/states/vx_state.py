
# --------------- ArticleAnalyseNode --------------------
from typing import List, Literal, Optional, TypedDict
from pydantic import BaseModel, Field, ConfigDict


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


class ArticleAnalyseNode(BaseModel):
    """
    热点公众号文章创作输入模型

    用于结构化描述热点事件及创作指导参数，
    可直接作为 LLM Prompt 的上下文数据源。
    """
    model_config = ConfigDict(populate_by_name=True)

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

# ---------------- ArticleSearchNode ------------------

class ArticleSearchNode(BaseModel):
    """
    热点事件网络调研产出模型

    基于搜索引擎、官方信源、社交媒体等渠道，
    对热点事件进行事实补充、角度挖掘、素材整理与争议梳理的结构化产出。
    通常作为 ArticleSearchNode 的前置研究节点，为创作提供弹药。
    """
    model_config = ConfigDict(populate_by_name=True)

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


class ArticleBlueprintNode(BaseModel):
    """
    文章写作蓝图模型

    基于热点调研与角度分析，输出完整的写作策略、风格定位、
    模板框架与执行计划，为后续文章生成提供可直接落地的创作方案。
    """
    model_config = ConfigDict(populate_by_name=True)
    # 在 Pydantic 里，...（三个点，叫 Ellipsis）表示这个字段是必填的，没有默认值。
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

# -------------------- PlotNode ----------------------

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


# -------------------- Write Node -----------------------------------

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
        alias="title_alternatives",
        description="文章标题（主标题及1-2个备选）"
    )
    content: str = Field(
        ...,
        alias="content",
        description="正文（按 contentSegments 顺序输出，严格遵循节奏与留白要求）"
    )
    golden_sentences: List[GoldenSentence] = Field(
        default_factory=list,
        alias="golden_sentences",
        description="金句标注"
    )
    share_texts: List[str] = Field(
        default_factory=list,
        alias="share_texts",
        description="转发语建议（2-3条适合朋友圈的简短文案）"
    )
    reading_time: str = Field(
        ...,
        alias="reading_time",
        description="预估阅读时间（如：5分钟）"
    )
    rhythm: str = Field(
        ...,
        alias="rhythm",
        description="整体节奏简述（如：开头钩子→中段铺陈与反转→结尾落点）"
    )


class ArticleOutputNode(BaseModel):
    """
    文章生成输出模型

    基于 ArticleWritingInstruction 指令生成的完整文章输出，
    按段落分块组织。若原始数据为数组，建议用 ArticlePart 直接解析；
    若包装为对象形式，使用本模型。
    """
    model_config = ConfigDict(populate_by_name=True)

    parts: List[ArticlePart] = Field(
        default_factory=list,
        alias="parts",
        description="文章分段输出列表"
    )


# ----------------- COMPOSITION_NODE --------------------------





