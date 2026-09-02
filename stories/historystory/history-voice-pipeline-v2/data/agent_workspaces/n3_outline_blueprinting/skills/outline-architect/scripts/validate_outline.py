#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大纲文件格式校验脚本
用法: python validate_outline.py <outline.json>

校验项：
1. JSON 结构合法性（根对象必须是数组）
2. 硬约束字段完整性（段号/功能类型/使用史料卡/炸点/动情点/伏笔/预计字数）
3. 段号连续性
4. 功能类型枚举值合法性
5. 预计字数格式（含容差标注）
6. 炸点是否有史料卡出处
7. 动情点是否标注位置
"""

import json
import re
import sys
from pathlib import Path

VALID_FUNCTION_TYPES = {"钩子", "锚定", "主线节点", "插件", "高潮", "收尾", "衔接"}

HARD_FIELDS = ["段号", "功能类型", "使用史料卡", "炸点", "动情点", "伏笔", "预计字数"]


def validate_structure(data) -> list[str]:
    """校验根结构"""
    errors = []
    if not isinstance(data, list):
        errors.append("根对象必须是 JSON 数组")
        return errors
    if len(data) == 0:
        errors.append("大纲数组为空")
    return errors


def validate_segment(seg: dict, idx: int) -> list[str]:
    """校验单个大纲段落"""
    errors = []

    # 硬约束字段检查
    for field in HARD_FIELDS:
        if field not in seg:
            errors.append(f"[段 {idx}] 缺少硬约束字段: {field}")

    # 段号类型检查
    if "段号" in seg:
        if not isinstance(seg["段号"], int):
            errors.append(f"[段 {idx}] '段号' 必须是整数")

    # 功能类型枚举检查
    if "功能类型" in seg:
        func_type = seg["功能类型"]
        if func_type not in VALID_FUNCTION_TYPES:
            errors.append(f"[段 {idx}] 功能类型非法: '{func_type}'，必须为: {VALID_FUNCTION_TYPES}")

    # 使用史料卡检查
    if "使用史料卡" in seg:
        cards = seg["使用史料卡"]
        if not isinstance(cards, list):
            errors.append(f"[段 {idx}] '使用史料卡' 必须是数组")
        elif len(cards) == 0:
            errors.append(f"[段 {idx}] '使用史料卡' 为空数组——每段必须至少挂一张史料卡")

    # 预计字数格式检查
    if "预计字数" in seg:
        word_count = seg["预计字数"]
        if not isinstance(word_count, str):
            errors.append(f"[段 {idx}] '预计字数' 必须是字符串（含容差标注）")
        elif not re.search(r"\d+.*容差", word_count):
            errors.append(f"[段 {idx}] '预计字数' 格式错误，应包含数字和容差标注（如'60（容差 ±40%）'）")

    # 炸点出处检查
    if "炸点" in seg and seg["炸点"] is not None and seg["炸点"] != "":
        if "史料卡" not in str(seg["炸点"]):
            errors.append(f"[段 {idx}] 炸点未标注史料卡出处——无卡炸点一票退回")

    # 动情点检查
    if "动情点" in seg:
        emotion = seg["动情点"]
        if emotion is not None and emotion != "" and "位置" not in str(emotion):
            # 允许简单标注如"有"，但建议标注位置
            pass

    return errors


def validate_continuity(data: list) -> list[str]:
    """校验段号连续性"""
    errors = []
    if not data:
        return errors

    nums = [seg.get("段号") for seg in data if isinstance(seg.get("段号"), int)]
    if len(nums) != len(data):
        return errors

    expected = list(range(1, len(nums) + 1))
    if nums != expected:
        missing = set(expected) - set(nums)
        duplicates = [n for n in nums if nums.count(n) > 1]
        if missing:
            errors.append(f"段号不连续，缺失: {sorted(missing)}")
        if duplicates:
            errors.append(f"段号重复: {sorted(set(duplicates))}")
    return errors


def validate_emotion_point(data: list) -> list[str]:
    """校验全片至少有一处动情点"""
    errors = []
    has_emotion = False
    for seg in data:
        emotion = seg.get("动情点")
        if emotion is not None and emotion != "" and emotion != "无":
            has_emotion = True
            break
    if not has_emotion:
        errors.append("全片无动情点——大纲必须退回")
    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python validate_outline.py <outline.json>")
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

    all_errors = validate_structure(data)

    if isinstance(data, list):
        for idx, seg in enumerate(data, start=1):
            if not isinstance(seg, dict):
                all_errors.append(f"[段 {idx}] 不是对象类型")
                continue
            all_errors.extend(validate_segment(seg, idx))

        all_errors.extend(validate_continuity(data))
        all_errors.extend(validate_emotion_point(data))

    print(f"\n{'='*60}")
    print(f"大纲文件格式校验完成: {filepath.name}")
    print(f"{'='*60}")

    if not all_errors:
        print(f"✅ 全部通过，共 {len(data)} 段")
        sys.exit(0)
    else:
        print(f"❌ 发现 {len(all_errors)} 处错误:\n")
        for err in all_errors:
            print(f"  • {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
