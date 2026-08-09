#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件卡 JSON Schema 校验脚本
用法: python validate_cards.py <cards.json>

校验项：
1. 基础层字段完整性（11个必填字段）
2. 可信度枚举值合法性
3. 弹药潜质标签合法性
4. 模板适配格式合法性
5. 叙事角色枚举值合法性
6. 类型专属字段条件校验（根据题材类型检查必填字段）
"""

import json
import sys
import re
from pathlib import Path

# ---- 枚举值定义 ----

CREDIBILITY_LEVELS = {"正史", "诸子", "传说", "出土文献"}

NARRATIVE_ROLES = {"钩子", "锚定", "推进", "转折", "高潮", "收尾", "插件"}

AMMO_TAGS = {
    "钩子", "锚定", "转折", "情绪峰值", "侧写", "对照组", "拆账",
    "古文炸点", "心理推演", "因果缝合", "制度织入", "地图节点",
    "数据可视化", "蝴蝶效应", "环境氛围", "沙盘决策", "谜案证据",
    "造势", "博弈入场", "胜负手", "制度案例", "制度漏洞", "现代对照",
    "地理奠基", "地域演进", "战役沙盘", "意外变量", "士兵视角",
    "战后复盘", "节奏钩子", "节奏危机", "节奏高潮", "节奏留钩",
    "知识彩蛋", "收尾", "无"
}

TEMPLATE_NAMES = {
    "人物篇-A", "人物篇-B", "人物篇-C", "人物篇-D", "人物篇-E",
    "朝代篇-A", "朝代篇-B", "朝代篇-C", "朝代篇-D", "朝代篇-E",
    "事件篇-A", "事件篇-B", "事件篇-C", "事件篇-D", "事件篇-E"
}

CONFIDENCE_LEVELS = {"高", "中", "低"}

# 基础层必填字段
BASE_REQUIRED = [
    "卡号", "时间", "地点", "人物", "冲突", "史料出处",
    "可信度", "本集用不用", "弹药潜质", "模板适配", "叙事角色"
]

# 类型专属必填字段映射
TYPE_REQUIRED_FIELDS = {
    "人物": ["人生阶段", "颠覆印象度", "情绪类型", "弧光位置", "决策瞬间", "争议等级"],
    "朝代": ["因果位置", "制度名称", "制度角色", "朝代阶段", "势类型"],
    "事件": ["事件阶段", "多方视角", "争议等级"]
}

# ---- 校验函数 ----

def validate_base_fields(card: dict, idx: int) -> list[str]:
    """校验基础层字段完整性"""
    errors = []
    for field in BASE_REQUIRED:
        if field not in card or card[field] == "" or card[field] is None:
            errors.append(f"[卡 {idx}] 缺少基础层必填字段: {field}")
    return errors


def validate_credibility(card: dict, idx: int) -> list[str]:
    """校验可信度枚举值"""
    errors = []
    val = card.get("可信度", "")
    if val and val not in CREDIBILITY_LEVELS:
        errors.append(f"[卡 {idx}] 可信度非法值: '{val}'，必须为: {CREDIBILITY_LEVELS}")
    return errors


def validate_narrative_role(card: dict, idx: int) -> list[str]:
    """校验叙事角色枚举值"""
    errors = []
    val = card.get("叙事角色", "")
    if val and val not in NARRATIVE_ROLES:
        errors.append(f"[卡 {idx}] 叙事角色非法值: '{val}'，必须为: {NARRATIVE_ROLES}")
    return errors


def validate_ammo_tags(card: dict, idx: int) -> list[str]:
    """校验弹药潜质标签"""
    errors = []
    val = card.get("弹药潜质", "")
    if not val:
        return errors
    tags = [t.strip() for t in val.split("/")]
    for tag in tags:
        if tag not in AMMO_TAGS:
            errors.append(f"[卡 {idx}] 弹药潜质非法标签: '{tag}'")
    return errors


def validate_template_adapt(card: dict, idx: int) -> list[str]:
    """校验模板适配格式: 模板名:位置名[置信度]"""
    errors = []
    val = card.get("模板适配", "")
    if not val:
        return errors

    pattern = re.compile(r'^[^:]+:[^\[]+\[(高|中|低)\]$')
    items = [item.strip() for item in val.split("/")]

    for item in items:
        if not pattern.match(item):
            errors.append(f"[卡 {idx}] 模板适配格式错误: '{item}'，正确格式: '模板名:位置名[置信度]'")
            continue
        # 提取模板名
        template_name = item.split(":")[0]
        if template_name not in TEMPLATE_NAMES:
            errors.append(f"[卡 {idx}] 模板适配非法模板名: '{template_name}'")

    return errors


def validate_type_fields(card: dict, idx: int) -> list[str]:
    """根据模板适配推断题材类型，校验类型专属字段"""
    errors = []
    template_adapt = card.get("模板适配", "")
    if not template_adapt:
        return errors

    # 推断题材类型
    card_type = None
    if any(t in template_adapt for t in ["人物篇"]):
        card_type = "人物"
    elif any(t in template_adapt for t in ["朝代篇"]):
        card_type = "朝代"
    elif any(t in template_adapt for t in ["事件篇"]):
        card_type = "事件"

    if not card_type:
        errors.append(f"[卡 {idx}] 无法从模板适配推断题材类型")
        return errors

    required_fields = TYPE_REQUIRED_FIELDS.get(card_type, [])
    for field in required_fields:
        if field not in card or card[field] == "" or card[field] is None:
            # 对于布尔值和数字，0 和 False 是合法值
            if field in card and (card[field] == 0 or card[field] is False):
                continue
            errors.append(f"[卡 {idx}] {card_type}篇缺少专属必填字段: {field}")

    return errors


def validate_card(card: dict, idx: int) -> list[str]:
    """单卡全量校验"""
    errors = []
    errors.extend(validate_base_fields(card, idx))
    errors.extend(validate_credibility(card, idx))
    errors.extend(validate_narrative_role(card, idx))
    errors.extend(validate_ammo_tags(card, idx))
    errors.extend(validate_template_adapt(card, idx))
    errors.extend(validate_type_fields(card, idx))
    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python validate_cards.py <cards.json>")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"错误: 文件不存在: {filepath}")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        try:
            cards = json.load(f)
        except json.JSONDecodeError as e:
            print(f"JSON 解析错误: {e}")
            sys.exit(1)

    if not isinstance(cards, list):
        print("错误: 根对象必须是 JSON 数组")
        sys.exit(1)

    all_errors = []
    for idx, card in enumerate(cards, start=1):
        if not isinstance(card, dict):
            all_errors.append(f"[卡 {idx}] 不是对象类型")
            continue
        all_errors.extend(validate_card(card, idx))

    # 输出结果
    print(f"\n{'='*60}")
    print(f"校验完成: 共 {len(cards)} 张卡")
    print(f"{'='*60}")

    if not all_errors:
        print("✅ 全部通过，无错误")
        sys.exit(0)
    else:
        print(f"❌ 发现 {len(all_errors)} 处错误:\n")
        for err in all_errors:
            print(f"  • {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
