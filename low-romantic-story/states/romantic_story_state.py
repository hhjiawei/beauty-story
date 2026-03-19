from typing import TypedDict, List, Dict, Any, Optional


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









