"""
wechatessay.states.vx_state

所有节点共享的状态定义。
包含：
- 输入/输出层状态
- 各节点中间产物状态
- 人机协同评审状态
- 全局流程控制状态
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field


# ═══════════════════════════════════════════════
# 枚举类型
# ═══════════════════════════════════════════════

class EmotionalTendency(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class WritingStyle(str, Enum):
    """写作风格枚举"""
    CASUAL = "口语化大白话"
    SERIOUS = "严肃科普"
    EMPATHETIC = "共情引导"
    SATIRICAL = "讽刺犀利"
    STORYTELLING = "故事叙述"
    HARD_CORE = "极简硬核"


class WritingStructure(str, Enum):
    """行文结构枚举"""
    GENERAL = "总分总"
    OPINION_FIRST = "观点前置"
    CASE_DRIVEN = "案例穿插"
    EMOTION_PROGRESSION = "情绪递进"
    QUESTION_ANSWER = "问答式"
    TIMELINE = "时间线式"


class SegmentType(str, Enum):
    """段落类型枚举"""
    INTRODUCTION = "introduction"
    BODY = "body"
    CONCLUSION = "conclusion"


class GoldSentencePosition(str, Enum):
    """金句位置枚举"""
    END = "end"
    MIDDLE = "middle"
    NONE = "none"


class FlowStatus(str, Enum):
    """节点执行状态"""
    PENDING = "pending"           # 待执行
    RUNNING = "running"           # 执行中
    WAITING_HUMAN = "waiting_human"  # 等待人工审核
    APPROVED = "approved"         # 人工通过
    REJECTED = "rejected"         # 人工拒绝/需修改
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 执行失败


class ReviewDecision(str, Enum):
    """人工评审决策"""
    APPROVE = "approve"           # 通过，继续下一节点
    REJECT = "reject"             # 拒绝，返回上一节点
    REVISE = "revise"             # 需要修改，附带修改意见
    RETRY = "retry"               # 重试当前节点


# ═══════════════════════════════════════════════
# 基础子模型
# ═══════════════════════════════════════════════

class DataComparison(BaseModel):
    """数据与对比信息"""
    model_config = ConfigDict(populate_by_name=True)

    key_specific_data: str = Field(
        ...,
        alias="keySpecificData",
        description="关键具象数据（如物业费上涨20%、涉及300户居民）",
    )
    horizontal_comparison: Optional[str] = Field(
        None,
        alias="horizontalComparison",
        description="横向对比（如与周边区域、往期情况对比，无则null）",
    )


class ExtendedContent(BaseModel):
    """延伸拔高素材"""
    model_config = ConfigDict(populate_by_name=True)

    macro_background: str = Field(
        ...,
        alias="macroBackground",
        description="宏观背景环境（社会、政策背景）",
    )
    deep_reasons: str = Field(
        ...,
        alias="deepReasons",
        description="深层原因（根本原因，不局限于表面现象）",
    )
    positive_focus: str = Field(
        ...,
        alias="positiveFocus",
        description="正向落点（积极举措、改进方向，提升账号质感）",
    )


class SupplementaryMaterial(BaseModel):
    """
    补充素材字段

    提取每篇文章特有的、洗稿需要的额外素材。
    这些字段是可选的额外信息，用于丰富创作素材库。
    """
    model_config = ConfigDict(populate_by_name=True)

    key_quotes: List[str] = Field(
        default_factory=list,
        alias="keyQuotes",
        description="关键引用/金句（原文中可直接引用或改编的句子）",
    )
    vivid_details: List[str] = Field(
        default_factory=list,
        alias="vividDetails",
        description="生动细节（具体场景、对话、动作描写）",
    )
    unique_perspectives: List[str] = Field(
        default_factory=list,
        alias="uniquePerspectives",
        description="独特视角（该文章特有的切入角度或观点）",
    )
    emotional_triggers: List[str] = Field(
        default_factory=list,
        alias="emotionalTriggers",
        description="情绪触发点（容易引发读者共鸣或愤怒的段落）",
    )
    data_sources: List[str] = Field(
        default_factory=list,
        alias="dataSources",
        description="数据来源（文章中引用的报告、统计、专家等可追溯来源）",
    )
    contrast_materials: List[str] = Field(
        default_factory=list,
        alias="contrastMaterials",
        description="反差素材（前后对比、预期与现实的落差）",
    )
    follow_up_clues: List[str] = Field(
        default_factory=list,
        alias="followUpClues",
        description="后续追踪线索（值得深挖的未尽话题、悬而未决的问题）",
    )


# ═══════════════════════════════════════════════
# 节点1 产物：单篇/汇总文章分析
# ═══════════════════════════════════════════════

class PerArticleAnalyseNode(BaseModel):
    """
    热点公众号文章创作输入模型 — 单篇/汇总后的热点追踪表

    用于结构化描述热点事件及创作指导参数，
    可直接作为 LLM Prompt 的上下文数据源。
    """
    model_config = ConfigDict(populate_by_name=True)

    # ── 基础信息 ──
    hotspot_title: str = Field(
        ...,
        alias="hotspotTitle",
        description="热点标题/话题（精准概括事件核心，贴合公众号标题调性）",
    )
    vertical_track: str = Field(
        ...,
        alias="verticalTrack",
        description="垂直赛道",
    )
    core_demand: str = Field(
        ...,
        alias="coreDemand",
        description="核心诉求/摘要（概括热点本质，明确事件核心问题）",
    )
    emotional_tendency: Literal["positive", "negative", "neutral"] = Field(
        ...,
        alias="emotionalTendency",
        description="情感倾向（positive/negative/neutral）",
    )
    writing_style: str = Field(
        ...,
        alias="writingStyle",
        description="文风建议（口语化大白话/严肃科普/共情引导及适配理由）",
    )
    writing_structure: str = Field(
        ...,
        alias="writingStructure",
        description="行文结构建议（总分总/观点前置/案例穿插/情绪递进及理由）",
    )
    event_line: List[str] = Field(
        default_factory=list,
        alias="eventLine",
        description="事件发展经历阶段",
    )
    region_scope: str = Field(
        ...,
        alias="regionScope",
        description="精准地域范围（城市/区县/街道/小区/路段）",
    )
    public_complaints: str = Field(
        ...,
        alias="publicComplaints",
        description="民间高频吐槽点",
    )
    data_comparison: DataComparison = Field(
        ...,
        alias="dataComparison",
        description="数据&对比信息",
    )
    extended_content: ExtendedContent = Field(
        ...,
        alias="extendedContent",
        description="延伸拔高素材",
    )
    creation_ideas: List[str] = Field(
        default_factory=list,
        alias="creationIdeas",
        description="切入点与创作思路（核心字段，如普通人维权技巧、官方处置效率、痛点反思等）",
    )

    # ── 补充素材（额外提取的洗稿素材） ──
    supplementary: SupplementaryMaterial = Field(
        default_factory=SupplementaryMaterial,
        alias="supplementary",
        description="补充素材（关键引用、生动细节、独特视角等额外信息）",
    )

    # ── 元信息 ──
    source_url: Optional[str] = Field(
        None,
        alias="sourceUrl",
        description="文章来源 URL",
    )
    analyzed_at: Optional[str] = Field(
        None,
        alias="analyzedAt",
        description="分析时间（ISO 格式）",
    )


class TotalArticleAnalyseNode(BaseModel):
    """
    汇总后的热点分析结果

    将多篇文章的 PerArticleAnalyseNode 进行汇总整合，
    形成统一的创作素材库。
    """
    model_config = ConfigDict(populate_by_name=True)

    hotspot_title: str = Field(
        ...,
        alias="hotspotTitle",
        description="汇总后的热点标题（去重合并后的核心话题）",
    )
    vertical_track: str = Field(
        ...,
        alias="verticalTrack",
        description="统一垂直赛道",
    )
    core_demand: str = Field(
        ...,
        alias="coreDemand",
        description="核心诉求汇总（合并多篇文章的核心观点）",
    )
    emotional_tendency: Literal["positive", "negative", "neutral"] = Field(
        ...,
        alias="emotionalTendency",
        description="综合情感倾向",
    )
    writing_style: str = Field(
        ...,
        alias="writingStyle",
        description="推荐文风（综合评估）",
    )
    writing_structure: str = Field(
        ...,
        alias="writingStructure",
        description="推荐行文结构",
    )
    event_line: List[str] = Field(
        default_factory=list,
        alias="eventLine",
        description="合并去重后的事件时间线",
    )
    region_scope: str = Field(
        ...,
        alias="regionScope",
        description="地域范围汇总",
    )
    public_complaints: str = Field(
        ...,
        alias="publicComplaints",
        description="高频吐槽点汇总",
    )
    data_comparison: DataComparison = Field(
        ...,
        alias="dataComparison",
        description="数据对比汇总",
    )
    extended_content: ExtendedContent = Field(
        ...,
        alias="extendedContent",
        description="延伸素材汇总",
    )
    creation_ideas: List[str] = Field(
        default_factory=list,
        alias="creationIdeas",
        description="汇总创作思路（去重合并）",
    )

    # ── 汇总补充素材 ──
    all_key_quotes: List[str] = Field(
        default_factory=list,
        alias="allKeyQuotes",
        description="所有关键引用汇总",
    )
    all_vivid_details: List[str] = Field(
        default_factory=list,
        alias="allVividDetails",
        description="所有生动细节汇总",
    )
    all_unique_perspectives: List[str] = Field(
        default_factory=list,
        alias="allUniquePerspectives",
        description="所有独特视角汇总",
    )
    all_emotional_triggers: List[str] = Field(
        default_factory=list,
        alias="allEmotionalTriggers",
        description="所有情绪触发点汇总",
    )

    # ── 汇总元信息 ──
    source_count: int = Field(
        0,
        alias="sourceCount",
        description="源文章数量",
    )
    source_urls: List[str] = Field(
        default_factory=list,
        alias="sourceUrls",
        description="所有源文章 URL",
    )
    summary_version: str = Field(
        "1.0",
        alias="summaryVersion",
        description="汇总版本",
    )


# ═══════════════════════════════════════════════
# 节点2 产物：网络信息收集
# ═══════════════════════════════════════════════

class SearchSourceDetail(BaseModel):
    """单条搜索结果详情"""
    model_config = ConfigDict(populate_by_name=True)

    platform: str = Field(
        ...,
        alias="platform",
        description="来源平台（知乎/今日头条/微博/百度等）",
    )
    url: Optional[str] = Field(
        None,
        alias="url",
        description="原文链接",
    )
    title: str = Field(
        ...,
        alias="title",
        description="内容标题",
    )
    content_summary: str = Field(
        ...,
        alias="contentSummary",
        description="内容摘要（200字以内）",
    )
    engagement_metrics: Optional[str] = Field(
        None,
        alias="engagementMetrics",
        description="互动数据（如点赞数、评论数，可选）",
    )
    author_view: Optional[str] = Field(
        None,
        alias="authorView",
        description="作者观点或立场",
    )
    credibility_score: int = Field(
        3,
        alias="credibilityScore",
        description="可信度评分 1-5",
        ge=1,
        le=5,
    )


class PublicOpinion(BaseModel):
    """舆论分析"""
    model_config = ConfigDict(populate_by_name=True)

    overall_sentiment: str = Field(
        ...,
        alias="overallSentiment",
        description="整体舆论倾向（支持/反对/中立/撕裂）",
    )
    key_opinion_leaders: List[str] = Field(
        default_factory=list,
        alias="keyOpinionLeaders",
        description="关键意见领袖观点",
    )
    netizen_highlights: List[str] = Field(
        default_factory=list,
        alias="netizenHighlights",
        description="网友高赞观点/神评论",
    )
    debate_focus: str = Field(
        ...,
        alias="debateFocus",
        description="舆论争论焦点",
    )


class ArticleSearchNode(BaseModel):
    """
    热点事件网络调研产出模型

    基于搜索引擎、官方信源、社交媒体等渠道，
    对热点事件进行事实补充、角度挖掘、素材整理与争议梳理的结构化产出。
    """
    model_config = ConfigDict(populate_by_name=True)

    cause_process_result: str = Field(
        ...,
        alias="causeProcessResult",
        description="事件起因、经过、结果补充（完善时间线，明确事件定性，补充一线现场细节）",
    )
    topic_angle: str = Field(
        ...,
        alias="topicAngle",
        description="创作角度补充（3-5个贴合的爆款角度，结合痛点与用户需求）",
    )
    topic_material: str = Field(
        ...,
        alias="topicMaterial",
        description="支撑材料补充（官方文件、权威报道、真实案例、数据，确保可追溯）",
    )
    controversial_points: str = Field(
        ...,
        alias="controversialPoints",
        description="争议焦点梳理（网友评论、多方回应、媒体解读、高频吐槽、遗留争议）",
    )
    creation_inspiration: str = Field(
        ...,
        alias="creationInspiration",
        description="创作灵感补充（热点趋势、爆款逻辑、话题延伸、关键词优化）",
    )

    # ── 新增字段 ──
    search_sources: List[SearchSourceDetail] = Field(
        default_factory=list,
        alias="searchSources",
        description="搜索来源详情列表（每条结果的平台、标题、摘要、可信度等）",
    )
    public_opinion: Optional[PublicOpinion] = Field(
        None,
        alias="publicOpinion",
        description="舆论分析（整体倾向、KOL观点、网友高赞评论、争论焦点）",
    )
    related_cases: List[str] = Field(
        default_factory=list,
        alias="relatedCases",
        description="同类/关联案例（历史相似事件及处理结果）",
    )
    expert_quotes: List[str] = Field(
        default_factory=list,
        alias="expertQuotes",
        description="专家/权威观点引用",
    )
    data_supplements: List[str] = Field(
        default_factory=list,
        alias="dataSupplements",
        description="数据补充（新发现的统计数字、图表、调查报告）",
    )
    legal_policy_references: List[str] = Field(
        default_factory=list,
        alias="legalPolicyReferences",
        description="法律法规/政策文件引用",
    )
    visual_materials: List[str] = Field(
        default_factory=list,
        alias="visualMaterials",
        description="可视化素材建议（图片、视频、信息图、时间线图）",
    )
    seo_keywords: List[str] = Field(
        default_factory=list,
        alias="seoKeywords",
        description="SEO 关键词推荐（热搜词、长尾词、话题标签）",
    )

    # ── 元信息 ──
    search_queries_used: List[str] = Field(
        default_factory=list,
        alias="searchQueriesUsed",
        description="实际使用的搜索查询列表",
    )
    searched_at: Optional[str] = Field(
        None,
        alias="searchedAt",
        description="搜索时间",
    )


# ═══════════════════════════════════════════════
# 节点3 产物：写作蓝图/分析
# ═══════════════════════════════════════════════

class WritingAnalysis(BaseModel):
    """写作角度分析"""
    model_config = ConfigDict(populate_by_name=True)

    common_angles: List[str] = Field(
        default_factory=list,
        alias="commonAngles",
        description="他人常用写作角度（3-5个）",
    )
    mergeable_angles: List[str] = Field(
        default_factory=list,
        alias="mergeableAngles",
        description="可融合角度（2-3个，说明融合逻辑）",
    )
    opposing_angles: List[str] = Field(
        default_factory=list,
        alias="opposingAngles",
        description="可对立角度（2-3个，说明对立点）",
    )
    controversial_angles: List[str] = Field(
        default_factory=list,
        alias="controversialAngles",
        description="争议角度（2-3个，说明争议焦点）",
    )
    thought_provoking_angles: List[str] = Field(
        default_factory=list,
        alias="thoughtProvokingAngles",
        description="引发深思角度（2-3个，说明思考方向）",
    )


class WritingStyle(BaseModel):
    """写作风格定义"""
    model_config = ConfigDict(populate_by_name=True)

    final_style: str = Field(
        ...,
        alias="finalStyle",
        description="最终确定的写作风格（口语化大白话/严肃科普/共情引导）",
    )
    style_reason: str = Field(
        ...,
        alias="styleReason",
        description="风格选择理由（结合事件特点、受众、传播目标）",
    )
    style_example: str = Field(
        ...,
        alias="styleExample",
        description="风格化表达示例（1-2个句子）",
    )
    tone_keywords: List[str] = Field(
        default_factory=list,
        alias="toneKeywords",
        description="语气关键词（如犀利、温暖、克制等）",
    )


class WritingTemplate(BaseModel):
    """写作模板框架"""
    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(
        ...,
        alias="title",
        description="建议标题（吸引眼球，贴合热点）",
    )
    subtitle: str = Field(
        ...,
        alias="subtitle",
        description="副标题（补充说明，增强吸引力）",
    )
    introduction: str = Field(
        ...,
        alias="introduction",
        description="引言模板（引子设计，吸引读者阅读）",
    )
    body_structure: List[str] = Field(
        default_factory=list,
        alias="bodyStructure",
        description="主体段落结构（每段核心内容、逻辑关系）",
    )
    conclusion: str = Field(
        ...,
        alias="conclusion",
        description="结尾模板（升华主题，引导互动）",
    )


class WritingPlan(BaseModel):
    """写作执行计划"""
    model_config = ConfigDict(populate_by_name=True)

    core_idea: str = Field(
        ...,
        alias="coreIdea",
        description="核心创作思路（文章核心观点，贯穿全文）",
    )
    lead_in: str = Field(
        ...,
        alias="leadIn",
        description="引子设计（如何开头，吸引读者注意力）",
    )
    clues: List[str] = Field(
        default_factory=list,
        alias="clues",
        description="文章线索（3-5个关键线索，串联全文）",
    )
    reference_materials: List[str] = Field(
        default_factory=list,
        alias="referenceMaterials",
        description="参考资料清单（需收集的权威资料来源）",
    )
    writing_direction: List[str] = Field(
        default_factory=list,
        alias="writingDirection",
        description="写作方向（2-3个重点方向，确保内容聚焦）",
    )
    risk_notes: List[str] = Field(
        default_factory=list,
        alias="riskNotes",
        description="风险提示（需要规避的敏感点、可能争议）",
    )


class ArticleBlueprintNode(BaseModel):
    """
    文章写作蓝图模型

    基于热点调研与角度分析，输出完整的写作策略、风格定位、
    模板框架与执行计划。
    """
    model_config = ConfigDict(populate_by_name=True)

    writing_analysis: WritingAnalysis = Field(
        ...,
        alias="writingAnalysis",
        description="写作角度分析（常用/融合/对立/争议/深思角度）",
    )
    writing_style: WritingStyle = Field(
        ...,
        alias="writingStyle",
        description="写作风格定义（最终风格、选择理由、表达示例）",
    )
    writing_template: WritingTemplate = Field(
        ...,
        alias="writingTemplate",
        description="写作模板框架（标题/副标题/引言/主体/结尾）",
    )
    writing_plan: WritingPlan = Field(
        ...,
        alias="writingPlan",
        description="写作执行计划（核心思路/引子/线索/资料/方向）",
    )

    # ── 新增字段 ──
    target_audience_analysis: str = Field(
        ...,
        alias="targetAudienceAnalysis",
        description="目标受众画像分析（年龄/职业/痛点/阅读习惯）",
    )
    emotional_arc_design: str = Field(
        ...,
        alias="emotionalArcDesign",
        description="情绪曲线设计（开头→中段→结尾的情绪起伏规划）",
    )
    hook_strategy: List[str] = Field(
        default_factory=list,
        alias="hookStrategy",
        description="钩子的设计策略（标题钩、开头钩、转折钩、结尾钩）",
    )
    interactive_design: str = Field(
        ...,
        alias="interactiveDesign",
        description="互动设计（如何引导读者留言、转发、点赞）",
    )
    viral_prediction: str = Field(
        ...,
        alias="viralPrediction",
        description="传播预判（为什么这篇文章可能爆，预估传播路径）",
    )

    # ── 版本信息 ──
    version: str = Field(
        "1.0",
        alias="version",
        description="蓝图版本",
    )


# ═══════════════════════════════════════════════
# 节点4 产物：大纲
# ═══════════════════════════════════════════════

class GlobalStyle(BaseModel):
    """全局风格定义"""
    model_config = ConfigDict(populate_by_name=True)

    tone: str = Field(
        ...,
        alias="tone",
        description="语调（如：辛辣讽刺、温情共鸣、极简硬核）",
    )
    language_requirement: str = Field(
        ...,
        alias="languageRequirement",
        description="语言约束（如：多用短句、杜绝成语、增加互动问句）",
    )
    example_sentences: List[str] = Field(
        default_factory=list,
        alias="exampleSentences",
        description="风格样板句",
    )


class GoldSentenceRequirement(BaseModel):
    """金句要求"""
    model_config = ConfigDict(populate_by_name=True)

    position: Literal["end", "middle", "none"] = Field(
        ...,
        alias="position",
        description="金句预留位置（end/middle/none）",
    )
    theme: str = Field(
        ...,
        alias="theme",
        description="金句的灵魂/核心词",
    )


class WordCountRange(BaseModel):
    """字数范围"""
    model_config = ConfigDict(populate_by_name=True)

    min: int = Field(
        ...,
        alias="min",
        description="最小字数",
        ge=0,
    )
    max: int = Field(
        ...,
        alias="max",
        description="最大字数",
        ge=0,
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
        ge=0,
    )
    segment_type: Literal["introduction", "body", "conclusion"] = Field(
        ...,
        alias="segmentType",
        description="段落类型（introduction/body/conclusion）",
    )
    section_title: Optional[str] = Field(
        None,
        alias="sectionTitle",
        description="本段小标题（如果有）",
    )
    core_logic: str = Field(
        ...,
        alias="coreLogic",
        description="本段必须要讲透的逻辑点",
    )
    key_information: List[str] = Field(
        default_factory=list,
        alias="keyInformation",
        description="必须包含的客观事实或线索（来自 clues/reference）",
    )
    emotional_objective: str = Field(
        ...,
        alias="emotionalObjective",
        description="读者情绪预期（如：认知失调、深表同情、恍然大悟）",
    )
    rhetorical_device: str = Field(
        ...,
        alias="rhetoricalDevice",
        description="建议使用的修辞（如：排比、反问、故事引入）",
    )
    gold_sentence_requirement: GoldSentenceRequirement = Field(
        ...,
        alias="goldSentenceRequirement",
        description="金句预留要求",
    )
    word_count_range: WordCountRange = Field(
        ...,
        alias="wordCountRange",
        description="字数范围",
    )
    transition_to_next: Optional[str] = Field(
        None,
        alias="transitionToNext",
        description="如何丝滑地引出下一段的内容暗示",
    )

    # ── 新增字段 ──
    material_sources: List[str] = Field(
        default_factory=list,
        alias="materialSources",
        description="本段引用素材来源（标注来源编号或链接）",
    )
    visual_aids: List[str] = Field(
        default_factory=list,
        alias="visualAids",
        description="本段建议配图/排版（如插图位置、引用框、分割线）",
    )
    comment_guidance: Optional[str] = Field(
        None,
        alias="commentGuidance",
        description="本段引导读者评论的方向提示",
    )


class ArticlePlotNode(BaseModel):
    """
    文章写作指令模型

    作为文章生成节点的直接输入，结构化描述标题、核心观点、
    目标受众、全局风格，以及逐段落的写作要求。
    """
    model_config = ConfigDict(populate_by_name=True)

    writing_context: "WritingContext" = Field(
        ...,
        alias="writingContext",
        description="写作上下文（标题、核心观点、受众、风格）",
    )
    content_segments: List[ContentSegment] = Field(
        default_factory=list,
        alias="contentSegments",
        description="内容段落列表（按顺序排列，每段独立定义逻辑、情绪、修辞）",
    )
    global_checklist: List[str] = Field(
        default_factory=list,
        alias="globalChecklist",
        description="写作完成后的自查准则",
    )

    # ── 新增字段 ──
    article_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        alias="articleMetadata",
        description="文章元数据（预估字数、阅读时长、标签、封面图建议）",
    )
    seo_config: Dict[str, Any] = Field(
        default_factory=dict,
        alias="seoConfig",
        description="SEO 配置（关键词、摘要、话题标签）",
    )
    version: str = Field(
        "1.0",
        alias="version",
        description="大纲版本",
    )


class WritingContext(BaseModel):
    """写作上下文"""
    model_config = ConfigDict(populate_by_name=True)

    article_title: str = Field(
        ...,
        alias="articleTitle",
        description="最终确定的爆款标题",
    )
    core_idea: str = Field(
        ...,
        alias="coreIdea",
        description="贯穿全文的核心观点",
    )
    target_audience: str = Field(
        ...,
        alias="targetAudience",
        description="目标受众画像（便于AI调整表达深度）",
    )
    global_style: GlobalStyle = Field(
        ...,
        alias="globalStyle",
        description="全局风格",
    )


# ═══════════════════════════════════════════════
# 节点5 产物：文章输出
# ═══════════════════════════════════════════════

class GoldenSentence(BaseModel):
    """金句标注"""
    model_config = ConfigDict(populate_by_name=True)

    position: str = Field(
        ...,
        alias="position",
        description="金句位置（如：第3段）",
    )
    text: str = Field(
        ...,
        alias="text",
        description="金句内容",
    )
    highlight_type: str = Field(
        "default",
        alias="highlightType",
        description="高亮类型（default/bold/quote）",
    )


class ShareTextVariant(BaseModel):
    """转发语文案变体"""
    model_config = ConfigDict(populate_by_name=True)

    platform: str = Field(
        ...,
        alias="platform",
        description="目标平台（朋友圈/微信群/微博）",
    )
    text: str = Field(
        ...,
        alias="text",
        description="转发文案",
    )


class ArticlePart(BaseModel):
    """
    文章分段

    对应生成文章的一个独立段落/部分。
    """
    model_config = ConfigDict(populate_by_name=True)

    part_index: int = Field(
        ...,
        alias="partIndex",
        description="段落编号",
        ge=1,
    )
    title_alternatives: List[str] = Field(
        default_factory=list,
        alias="titleAlternatives",
        description="文章标题（主标题及1-2个备选）",
    )
    content: str = Field(
        ...,
        alias="content",
        description="正文（按 contentSegments 顺序输出，严格遵循节奏与留白要求）",
    )
    golden_sentences: List[GoldenSentence] = Field(
        default_factory=list,
        alias="goldenSentences",
        description="金句标注",
    )
    share_texts: List[ShareTextVariant] = Field(
        default_factory=list,
        alias="shareTexts",
        description="转发语建议（按平台区分）",
    )
    reading_time: str = Field(
        ...,
        alias="readingTime",
        description="预估阅读时间（如：5分钟）",
    )
    rhythm: str = Field(
        ...,
        alias="rhythm",
        description="整体节奏简述（如：开头钩子→中段铺陈与反转→结尾落点）",
    )

    # ── 新增字段 ──
    section_images: List[str] = Field(
        default_factory=list,
        alias="sectionImages",
        description="本段建议配图（图片位置及描述）",
    )
    internal_links: List[str] = Field(
        default_factory=list,
        alias="internalLinks",
        description="内链建议（相关文章链接位置）",
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
        description="文章分段输出列表",
    )

    # ── 新增字段 ──
    full_text: str = Field(
        "",
        alias="fullText",
        description="完整文本（所有段落拼接）",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        alias="metadata",
        description="文章元数据（字数、阅读时长、生成时间等）",
    )
    seo_info: Dict[str, Any] = Field(
        default_factory=dict,
        alias="seoInfo",
        description="SEO 信息（关键词密度、摘要、标签）",
    )
    version: str = Field(
        "1.0",
        alias="version",
        description="文章版本",
    )


# ═══════════════════════════════════════════════
# 节点6 产物：排版
# ═══════════════════════════════════════════════

class FormatSpec(BaseModel):
    """排版规范"""
    model_config = ConfigDict(populate_by_name=True)

    font_style: str = Field(
        ...,
        alias="fontStyle",
        description="字体样式",
    )
    paragraph_spacing: str = Field(
        ...,
        alias="paragraphSpacing",
        description="段落间距",
    )
    highlight_style: str = Field(
        ...,
        alias="highlightStyle",
        description="重点标注样式",
    )
    image_placement: List[str] = Field(
        default_factory=list,
        alias="imagePlacement",
        description="图片放置位置",
    )


class CompositionNode(BaseModel):
    """
    排版节点产物

    包含排版后的完整文章、排版规范、以及排版说明。
    """
    model_config = ConfigDict(populate_by_name=True)

    formatted_article: ArticleOutputNode = Field(
        ...,
        alias="formattedArticle",
        description="排版后的文章",
    )
    format_spec: FormatSpec = Field(
        ...,
        alias="formatSpec",
        description="排版规范说明",
    )
    composition_notes: List[str] = Field(
        default_factory=list,
        alias="compositionNotes",
        description="排版注意事项（视觉节奏、移动端适配等）",
    )
    preview_suggestions: List[str] = Field(
        default_factory=list,
        alias="previewSuggestions",
        description="预览检查建议（发送前需确认项）",
    )


# ═══════════════════════════════════════════════
# 节点7 产物：合规检查
# ═══════════════════════════════════════════════

class LegalityIssue(BaseModel):
    """合规问题"""
    model_config = ConfigDict(populate_by_name=True)

    issue_type: str = Field(
        ...,
        alias="issueType",
        description="问题类型（sensitive/ai_marker/grammar/factual）",
    )
    severity: Literal["critical", "warning", "info"] = Field(
        ...,
        alias="severity",
        description="严重程度",
    )
    location: str = Field(
        ...,
        alias="location",
        description="问题位置（段落/句子）",
    )
    original_text: str = Field(
        ...,
        alias="originalText",
        description="原文",
    )
    suggestion: str = Field(
        ...,
        alias="suggestion",
        description="修改建议",
    )


class LegalityCheckResult(BaseModel):
    """
    合规检查节点产物

    包含错别字检查、AI 感检测、敏感词检查等。
    """
    model_config = ConfigDict(populate_by_name=True)

    is_passed: bool = Field(
        ...,
        alias="isPassed",
        description="是否通过检查",
    )
    overall_score: int = Field(
        ...,
        alias="overallScore",
        description="综合评分 0-100",
        ge=0,
        le=100,
    )
    typo_issues: List[LegalityIssue] = Field(
        default_factory=list,
        alias="typoIssues",
        description="错别字/标点问题列表",
    )
    ai_flavor_issues: List[LegalityIssue] = Field(
        default_factory=list,
        alias="aiFlavorIssues",
        description="AI 感问题列表（模板化表达、八股文痕迹等）",
    )
    sensitive_issues: List[LegalityIssue] = Field(
        default_factory=list,
        alias="sensitiveIssues",
        description="敏感词/敏感内容问题列表",
    )
    factual_issues: List[LegalityIssue] = Field(
        default_factory=list,
        alias="factualIssues",
        description="事实性问题列表（数据矛盾、来源缺失等）",
    )
    style_issues: List[LegalityIssue] = Field(
        default_factory=list,
        alias="styleIssues",
        description="文风问题列表（与目标风格偏离）",
    )
    ai_flavor_score: float = Field(
        ...,
        alias="aiFlavorScore",
        description="AI 感得分 0-1（越低越好）",
    )
    readability_score: float = Field(
        ...,
        alias="readabilityScore",
        description="可读性得分 0-1",
    )
    correction_suggestions: List[str] = Field(
        default_factory=list,
        alias="correctionSuggestions",
        description="整体修改建议汇总",
    )
    corrected_article: Optional[ArticleOutputNode] = Field(
        None,
        alias="correctedArticle",
        description="修改后的文章（如已自动修正）",
    )


# ═══════════════════════════════════════════════
# 节点8 产物：发布
# ═══════════════════════════════════════════════

class PublishConfig(BaseModel):
    """发布配置"""
    model_config = ConfigDict(populate_by_name=True)

    platform: str = Field(
        ...,
        alias="platform",
        description="发布平台（wechat/wordpress/zhihu 等）",
    )
    scheduled_time: Optional[str] = Field(
        None,
        alias="scheduledTime",
        description="定时发布时间（ISO 格式，null 表示立即发布）",
    )
    tags: List[str] = Field(
        default_factory=list,
        alias="tags",
        description="文章标签",
    )
    category: Optional[str] = Field(
        None,
        alias="category",
        description="文章分类",
    )
    is_original: bool = Field(
        True,
        alias="isOriginal",
        description="是否声明原创",
    )


class PublishNode(BaseModel):
    """
    发布节点产物

    包含发布配置、发布状态、以及发布后的数据追踪。
    """
    model_config = ConfigDict(populate_by_name=True)

    publish_config: PublishConfig = Field(
        ...,
        alias="publishConfig",
        description="发布配置",
    )
    publish_status: str = Field(
        ...,
        alias="publishStatus",
        description="发布状态（pending/published/failed/draft）",
    )
    final_article_html: str = Field(
        ...,
        alias="finalArticleHtml",
        description="最终 HTML 格式文章（可直接粘贴到公众号编辑器）",
    )
    preview_link: Optional[str] = Field(
        None,
        alias="previewLink",
        description="预览链接",
    )
    published_url: Optional[str] = Field(
        None,
        alias="publishedUrl",
        description="发布后的文章链接",
    )
    publish_log: List[str] = Field(
        default_factory=list,
        alias="publishLog",
        description="发布操作日志",
    )


# ═══════════════════════════════════════════════
# 人机协同评审记录
# ═══════════════════════════════════════════════

class HumanReviewRecord(BaseModel):
    """人工评审记录"""
    model_config = ConfigDict(populate_by_name=True)

    node_name: str = Field(
        ...,
        alias="nodeName",
        description="被评审的节点名称",
    )
    decision: Literal["approve", "reject", "revise", "retry"] = Field(
        ...,
        alias="decision",
        description="评审决策",
    )
    comment: Optional[str] = Field(
        None,
        alias="comment",
        description="评审意见/修改建议",
    )
    reviewed_at: Optional[str] = Field(
        None,
        alias="reviewedAt",
        description="评审时间",
    )
    retry_count: int = Field(
        0,
        alias="retryCount",
        description="当前节点重试次数",
    )


# ═══════════════════════════════════════════════
# 总 Graph 状态
# ═══════════════════════════════════════════════

class GraphState(TypedDict):
    """
    LangGraph 全局状态

    贯穿整个工作流，各节点通过此状态传递数据。
    """

    # ── 输入层 ──
    input_path: str                    # 文章所在目录或文件路径（工作流入口）

    per_article_results: List[PerArticleAnalyseNode]  # 单篇分析结果列表

    total_article_results: TotalArticleAnalyseNode    # 汇总后的分析结果

    # ── 节点产出层（按工作流顺序） ──
    search_result: Optional[ArticleSearchNode]        # 热点调研结果

    blueprint_result: Optional[ArticleBlueprintNode]  # 写作蓝图结果

    plot_result: Optional[ArticlePlotNode]            # 大纲结果

    article_output: Optional[ArticleOutputNode]       # 写作内容

    composition_result: Optional[CompositionNode]     # 排版结果

    legality_result: Optional[LegalityCheckResult]    # 合规检查结果

    publish_result: Optional[PublishNode]             # 发布结果

    # ── 流程控制层 ──
    current_node: str                                 # 当前执行节点名称

    node_status: Dict[str, str]                       # 各节点执行状态

    # ── 人机协同层 ──
    human_reviews: List[HumanReviewRecord]            # 人工评审记录

    pending_human_review: Optional[Dict[str, Any]]    # 待人工评审的内容

    revision_notes: Optional[str]                     # 修改意见（人工反馈）

    retry_counts: Dict[str, int]                      # 各节点重试计数

    # ── 全局配置 ──
    writing_config: Dict[str, Any]                    # 写作配置覆盖项

    # ── 错误处理 ──
    error_message: Optional[str]                      # 错误信息

    error_node: Optional[str]                         # 出错节点
