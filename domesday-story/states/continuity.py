from typing import TypedDict, List, Dict, Any, Optional

# 连贯性追踪状态
class ContinuityTrackerState(TypedDict):
    timeline: List[Dict]              # 时间线记录
    locations: List[Dict]             # 地点转换记录
    character_states: Dict[str, List] # 人物状态字典
    prop_inventory: Dict[str, List]   # 道具清单
    plot_causality: List[Dict]        # 剧情因果链