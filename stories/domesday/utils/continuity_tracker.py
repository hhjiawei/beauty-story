"""
连贯性追踪工具 - 确保时间、地点、人物、道具的连续性
"""
from typing import Dict, List, Any


class ContinuityTracker:
    """连贯性追踪器类"""

    def __init__(self):
        """初始化追踪器"""
        self.timeline: List[Dict] = []  # 时间线记录
        self.locations: List[Dict] = []  # 地点转换记录
        self.character_states: Dict[str, List] = {}  # 人物状态字典
        self.prop_inventory: Dict[str, List] = {}  # 道具清单
        self.plot_causality: List[Dict] = []  # 剧情因果链

    def update_time(self, time_point: str, event: str):
        """
        更新时间线

        Args:
            time_point: 时间点（如：末日爆发前 30 天）
            event: 关键事件
        """
        self.timeline.append({
            "time": time_point,
            "event": event,
            "order": len(self.timeline)
        })

    def update_location(self, character: str, from_loc: str, to_loc: str, transition: str = ""):
        """
        更新地点转换

        Args:
            character: 人物名称
            from_loc: 起始地点
            to_loc: 目标地点
            transition: 转换方式（如：驱车前往、步行等）
        """
        self.locations.append({
            "character": character,
            "from": from_loc,
            "to": to_loc,
            "transition": transition,
            "order": len(self.locations)
        })

    def update_character_state(self, character: str, state_change: Dict):
        """
        更新人物状态

        Args:
            character: 人物名称
            state_change: 状态变化字典（如：{"health": "受伤", "emotion": "愤怒"}）
        """
        if character not in self.character_states:
            self.character_states[character] = []

        self.character_states[character].append({
            "change": state_change,
            "order": len(self.character_states[character])
        })

    def update_prop(self, prop_name: str, action: str, owner: str, quantity: int = 1):
        """
        更新道具状态

        Args:
            prop_name: 道具名称
            action: 动作（获取/使用/消耗/丢失）
            owner: 持有者
            quantity: 数量
        """
        if prop_name not in self.prop_inventory:
            self.prop_inventory[prop_name] = []

        self.prop_inventory[prop_name].append({
            "action": action,
            "owner": owner,
            "quantity": quantity,
            "order": len(self.prop_inventory[prop_name])
        })

    def add_causality(self, cause: str, effect: str, characters: List[str]):
        """
        添加剧情因果链

        Args:
            cause: 原因
            effect: 结果
            characters: 相关人物
        """
        self.plot_causality.append({
            "cause": cause,
            "effect": effect,
            "characters": characters,
            "order": len(self.plot_causality)
        })

    def check_consistency(self) -> List[str]:
        """
        检查连贯性，返回问题列表

        Returns:
            问题列表，空列表表示无问题
        """
        issues = []

        # 检查时间是否倒流
        for i in range(1, len(self.timeline)):
            # 这里可以添加更复杂的时间逻辑检查
            pass

        # 检查地点是否瞬移（简化版）
        for loc in self.locations:
            if not loc.get("transition") and loc.get("from") != loc.get("to"):
                issues.append(f"地点转换缺少过渡：{loc.get('from')} → {loc.get('to')}")

        # 检查人物状态是否突变（简化版）
        for char, states in self.character_states.items():
            if len(states) > 1:
                # 可以添加状态冲突检查
                pass

        # 检查道具是否凭空出现
        for prop, actions in self.prop_inventory.items():
            if actions and actions[0].get("action") not in ["获取", "初始拥有"]:
                issues.append(f"道具{prop}来源不明")

        return issues

    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "timeline": self.timeline,
            "locations": self.locations,
            "character_states": self.character_states,
            "prop_inventory": self.prop_inventory,
            "plot_causality": self.plot_causality
        }

    def get_summary(self) -> str:
        """生成连贯性摘要"""
        summary = []
        summary.append(f"时间线：{len(self.timeline)} 个节点")
        summary.append(f"地点转换：{len(self.locations)} 次")
        summary.append(f"人物状态追踪：{len(self.character_states)} 人")
        summary.append(f"道具追踪：{len(self.prop_inventory)} 个")
        summary.append(f"剧情因果：{len(self.plot_causality)} 条")
        return " | ".join(summary)
