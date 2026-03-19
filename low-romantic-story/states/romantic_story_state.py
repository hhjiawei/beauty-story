from typing import TypedDict, List, Dict, Any, Optional, Literal, NotRequired


# ----------------------------------------------------------------------
# 1. 策划层 · 故事架构师
# ----------------------------------------------------------------------
class OriginStoryInfo(TypedDict):
    how_they_met: str  # 相识方式（≤50字，一笔带过）
    once_relationship: str  # 初识关系
    current_relationship: str  # 当前关系状态（如：分手三年/契约婚姻）


class ThreeLinesInfo(TypedDict):
    """ 三线构建  | 输出事件线、感情线、背景线的起承转合 | 每线≤200字 |"""
    event_line: str  # 主角成长轨迹（职场/生存/复仇等）
    emotion_line: str  # 感情阶段（试探→拉扯→破冰→危机→结局）
    background_line: str  # 幕后推手事件（家族/阴谋/时代）


class PlanState(TypedDict):
    """策划组输出状态"""

    # 故事摘要（800字）
    story_summary: str

    # 开篇爆点 开篇通过爆点吸引读者 通常是一句总结的、炸裂的话
    hook: str

    # 交代背景 例如如何相识 曾经如何 目前如何
    origin_story: OriginStoryInfo

    #  **双线蓝图** | 明确感情线与副线（事业/生存/复仇等）的3个交汇点 | 每点≤30字
    dual_line_intersections: List[str]

    # ** 三线构建 ** | 输出事件线、感情线、背景线的起承转合 | 每线≤200字 |
    three_lines_info: ThreeLinesInfo

    # **核心矛盾** | 定义贯穿全文的1个主矛盾+2个副矛盾 | 矛盾必须可拆解为具体事件   [{main:xxx},{sub1:xxx},{sub2:xxx}]
    core_conflicts: List[Dict]

    # **时间地理** | 确定故事时间跨度（建议≤7天或3个月两个极端）和主场景 | 精确到城市区域 |
    key_locations: List[Dict]  # 关键地点列表
    timeline: List[Dict]  # 时间线

# ----------------------------------------------------------------------
# 2. 人物关系部 · 角色架构师
# ----------------------------------------------------------------------

class CharacterBasic(TypedDict):
    name: str
    age: int
    career_tag: str  # 职业标签（仅名称，无细节）
    income_level: str # 收入层级（底层/中层/上层）
    living_space: str  # 居住空间（仅类型，如：合租公寓）

class CharacterDNA(TypedDict):
    surface_personality: List[str]  # 外在表现（3个关键词）
    inner_essence: str  # 内在本质（核心恐惧+核心渴望）
    character_flaw: str  # 性格缺陷（驱动冲突的关键，如：逃避型依恋） !! 重点性格描述
    defense_mechanism: str  # 防御机制（如：用冷漠掩饰脆弱）

class CharacterSecret(TypedDict):
    content: str # 隐藏秘密（影响剧情）
    revealed_at: str  # 预计揭露节点（段落编号）

class RelationshipDynamics(TypedDict):
    initial_state: str # 初始关系状态
    turning_points: List[str]  # 每章的发展状态
    final_state: str    # 最终关系状态

class CharacterProfile(TypedDict):
    character_id: str
    basic: CharacterBasic
    dna: CharacterDNA
    secret: CharacterSecret
    relationship_dynamics: RelationshipDynamics
    physical_markers: List[str]  # 身体特征状态

class NetworkNode(TypedDict):
    from_char: str
    to_char: str
    relationship: str
    emotional_current: str
    motivation: NotRequired[str]  # 仅配角需要
    independence: NotRequired[str]  # 仅助攻者需要

class CharacterState(TypedDict):
    """人物组输出状态"""
    character_a: CharacterProfile
    character_b: CharacterProfile
    network: List[NetworkNode]  # 关系网络图

# 不能体现动态变化啊





