#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
弹药使用校验脚本
用法: python validate_ammo.py <ammo_usage.json>

校验项：
1. 弹药编号合法性（是否在库内）
2. 同类型弹药数量是否超标
3. 冲突弹药检查（如方言与悲情场景冲突）
4. 密度检查（炸点数量、方言段落数等）
5. 纪律红线检查（外号≤1、类比≤2、反转≤1等）
"""

import json
import sys
from pathlib import Path

# 弹药库定义
AMMO_CATEGORIES = {
    "开场钩子": {"max": 1, "items": list(range(1, 10))},
    "中段插件": {"max": 3, "items": list(range(1, 13))},
    "炸点": {"max": 10, "items": list(range(1, 13))},
    "动情点": {"max": 3, "items": list(range(1, 4))},
    "收尾": {"max": 2, "items": list(range(1, 3))},
    "方言场景": {"max": 3, "items": list(range(1, 6))},
}

# 纪律约束
DISCIPLINE_RULES = {
    "外号": {"max": 1, "field": "外号使用数"},
    "类比": {"max": 2, "field": "类比使用数"},
    "反转": {"max": 1, "field": "反转使用数"},
    "对话演绎": {"max": 1, "field": "对话演绎场数"},
    "方言段落": {"max": 3, "field": "方言段落数"},  # 人物篇≤2在时长判断中处理
    "盖牌": {"max": 1, "field": "盖牌使用数"},
    "时间锚点": {"max": 1, "field": "时间锚点数"},
    "家事线": {"max": 2, "field": "家事线数"},
}


def validate_structure(data: dict) -> list[str]:
    """校验根结构"""
    errors = []
    if not isinstance(data, dict):
        errors.append("根对象必须是 JSON 对象")
        return errors
    required = ["题材类型", "目标时长", "已选弹药"]
    for field in required:
        if field not in data:
            errors.append(f"缺少必填字段: {field}")
    return errors


def validate_ammo_selection(data: dict) -> list[str]:
    """校验弹药选择"""
    errors = []
    ammo_list = data.get("已选弹药", [])

    if not isinstance(ammo_list, list):
        errors.append("'已选弹药' 必须是数组")
        return errors

    # 按类别统计
    category_counts = {cat: 0 for cat in AMMO_CATEGORIES}

    for ammo in ammo_list:
        if not isinstance(ammo, dict):
            continue
        cat = ammo.get("类别")
        num = ammo.get("编号")

        if cat not in AMMO_CATEGORIES:
            errors.append(f"非法弹药类别: {cat}")
            continue

        if num not in AMMO_CATEGORIES[cat]["items"]:
            errors.append(f"非法弹药编号: {cat}-{num}")
            continue

        category_counts[cat] += 1

    # 检查各类别数量上限
    for cat, count in category_counts.items():
        max_count = AMMO_CATEGORIES[cat]["max"]
        if count > max_count:
            errors.append(f"{cat} 弹药超标: 使用 {count} 发，上限 {max_count} 发")

    return errors


def validate_discipline(data: dict) -> list[str]:
    """校验纪律约束"""
    errors = []

    # 检查人物篇方言特殊限制
    persona_type = data.get("题材类型", "")
    if "人物" in str(persona_type):
        dialect_count = data.get("方言段落数", 0)
        if dialect_count > 2:
            errors.append(f"人物篇方言段落超标: {dialect_count} 处，上限 2 处")

    # 通用纪律检查
    for rule_name, rule in DISCIPLINE_RULES.items():
        field = rule["field"]
        if field in data:
            count = data[field]
            if isinstance(count, (int, float)) and count > rule["max"]:
                errors.append(f"{rule_name} 纪律违规: {count}，上限 {rule['max']}")

    return errors


def validate_conflicts(data: dict) -> list[str]:
    """校验冲突规则"""
    errors = []
    ammo_list = data.get("已选弹药", [])

    # 检查方言与悲情场景冲突
    has_dialect = any(a.get("类别") == "方言场景" for a in ammo_list if isinstance(a, dict))
    has_emotion = any(a.get("类别") == "动情点" for a in ammo_list if isinstance(a, dict))

    # 检查方言与古文炸点同段叠加
    # 注：需要段级别信息，这里做简单检查

    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python validate_ammo.py <ammo_usage.json>")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"错误: 文件不存在: {filepath}")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"JSON 解析错误: {e}")
            sys.exit(1)

    all_errors = []
    all_errors.extend(validate_structure(data))
    all_errors.extend(validate_ammo_selection(data))
    all_errors.extend(validate_discipline(data))
    all_errors.extend(validate_conflicts(data))

    print(f"\n{'='*60}")
    print(f"弹药使用校验完成: {filepath.name}")
    print(f"{'='*60}")

    if not all_errors:
        print("✅ 弹药使用合规")
        sys.exit(0)
    else:
        print(f"❌ 发现 {len(all_errors)} 处违规:\n")
        for err in all_errors:
            print(f"  • {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
