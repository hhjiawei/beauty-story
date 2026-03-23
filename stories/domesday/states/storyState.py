"""
状态定义 - 所有智能体共享的状态结构
包含主状态、子状态和连贯性追踪状态
"""
from typing import TypedDict, List, Dict, Any, Optional

# ================= 前期中台状态 =================

class WorldBuildingState(TypedDict):
    """世界观设定状态"""
    apocalypse_name: str              # 末日名称
    apocalypse_source: str            # 末日来源详细描述
    outbreak_date: str                # 爆发具体日期时间
    key_locations: List[Dict]         # 关键地点列表
    timeline: List[Dict]              # 时间线
    special_rules: str                # 特殊设定及限制
    qa_status: str                    # 品控状态
    qa_feedback: str                  # 品控反馈

class GoldenFingerState(TypedDict):
    """金手指配置状态"""
    ability_type: str                 # 能力类型
    activation_condition: str         # 激活条件详细描述
    functions: List[Dict]             # 功能列表
    limitations: str                  # 总体限制说明
    revenge_advantages: List[str]     # 复仇优势列表
    growth_path: str                  # 成长路径说明
    qa_status: str
    qa_feedback: str

class CharacterState(TypedDict):
    """人物关系状态"""
    protagonist: Dict                 # 主角档案
    villains: List[Dict]              # 仇人列表
    allies: List[Dict]                # 盟友列表
    relationship_timeline: List[Dict] # 关系变化时间线
    qa_status: str
    qa_feedback: str

class PlotState(TypedDict):
    """剧情策划状态"""
    beat_sheet: List[Dict]                    # 6 段情节大纲
    hook_points: List[str]                    # 爽点位置
    transition_design: str                    # 过渡设计
    opening_hook: str                         # 开篇设计
    ending_hook: str                          # 结尾设计
    timeline_summary: str                     # 完整时间线摘要
    revision_count: int                       # 返修次数（新增）
    revision_notes: str                       # 返修说明
    qa_status: str
    qa_feedback: str

# ================= 生产流水线状态 =================

class SegmentState(TypedDict):
    """段落写作状态"""
    segment_index: int                # 段落索引
    content: str                      # 段落内容
    summary: str                      # 段落摘要
    word_count: int                   # 字数
    time: str                         # 时间
    location: str                     # 地点
    characters: List[str]             # 在场人物
    character_states: Dict            # 人物状态
    key_props: List[str]              # 关键道具
    qa_status: str
    qa_feedback: str

class ContinuityState(TypedDict):
    """连贯性整合状态"""
    full_draft: str                   # 连贯初稿
    # continuity_report: Dict           # 连贯性检查报告
    transition_records: List[str]     # 过渡修改记录
    # logic_continuity: float           # 逻辑连续性评分
    qa_status: str
    qa_feedback: str

class RhythmState(TypedDict):
    """节奏控制状态"""
    optimized_draft: str              # 节奏优化稿
    rhythm_report: Dict               # 节奏分析报告
    short_sentence_ratio: float       # 短句占比
    paragraph_density: float          # 段落密度
    qa_status: str
    qa_feedback: str

# ================= 后期工坊状态 =================

class SensoryState(TypedDict):
    """感官修饰状态"""
    sensory_enhanced: str             # 感官增强稿
    sensory_report: Dict              # 感官描写报告
    sensory_count: int                # 描写数量
    compliance_check: bool            # 合规检查
    qa_status: str
    qa_feedback: str

class HumorState(TypedDict):
    """幽默注入状态"""
    humor_enhanced: str               # 幽默增强稿
    humor_report: Dict                # 幽默注入报告
    humor_count: int                  # 笑点数量
    style_consistency: float          # 风格一致性
    qa_status: str
    qa_feedback: str

class FormatState(TypedDict):
    """格式标准化状态"""
    final_draft: str                  # 标准格式终稿
    md_content: str                   # MD 文件内容
    json_content: str                 # JSON 状态内容
    metadata: Dict                    # 元数据
    file_paths: Dict                  # 文件路径
    qa_status: str
    qa_feedback: str

# ================= 品控中心状态 =================

class NodeQAState(TypedDict):
    """节点品控状态"""
    node_name: str                    # 节点名称
    check_result: str                 # 检查结果 PASS/REJECT
    completeness_score: float         # 完整性评分
    format_score: float               # 格式评分
    quality_score: float              # 质量评分
    continuity_score: float           # 连贯性评分
    issues: List[str]                 # 问题列表
    suggestions: List[str]            # 修改建议
    timestamp: str                    # 检查时间

class FinalQAState(TypedDict):
    """终稿质检状态"""
    six_feature_scores: Dict          # 六大特征评分
    total_score: float                # 总分
    continuity_check: Dict            # 连贯性检查
    compliance_issues: List[str]      # 合规问题
    word_count: int                   # 字数
    final_status: str                 # PASS/REJECT
    feedback: str                     # 详细修改建议

# ================= 连贯性追踪状态 =================

class ContinuityTrackerState(TypedDict):
    """连贯性追踪器状态"""
    timeline: List[Dict]              # 时间线记录
    locations: List[Dict]             # 地点转换记录
    character_states: Dict[str, List] # 人物状态字典
    prop_inventory: Dict[str, List]   # 道具清单
    plot_causality: List[Dict]        # 剧情因果链

# ================= 主状态（汇总所有） =================

class MainState(TypedDict):
    """主状态 - 包含所有部门和流程信息"""
    # 输入
    user_input: str

    # 前期中台
    world_building: WorldBuildingState
    golden_finger: GoldenFingerState
    character: CharacterState
    plot: PlotState

    # 连贯性检测（新增）
    plot_continuity_report: Dict  # 大纲连贯性检测报告
    plot_continuity_status: str  # 大纲连贯性状态（PASS/FAIL）

    # 生产流水线
    segments: List[SegmentState]
    continuity: ContinuityState
    rhythm: RhythmState

    # 后期工坊
    sensory: SensoryState
    humor: HumorState
    format: FormatState

    # 品控中心
    final_qa: FinalQAState

    # 流程控制
    iteration_count: int
    current_stage: str
    current_segment_index: int