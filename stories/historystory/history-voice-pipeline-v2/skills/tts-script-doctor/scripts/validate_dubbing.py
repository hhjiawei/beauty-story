#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
画本 JSON 格式校验脚本
用法: python validate_dubbing.py <dubbing.json>

校验项：
1. JSON 结构合法性
2. 必填字段完整性（段号/对应成稿段/文本/拆分/情感/情感强度/语速/前停顿/后停顿）
3. 拆分单元字数 ≤80
4. 情感强度在 0.0-1.0 范围
5. 语速在 0.5-2.0 范围
6. 停顿时间在合理范围（0-5000ms）
7. 读音表格式正确
"""

import json
import sys
from pathlib import Path


REQUIRED_FIELDS = [
    "段号", "对应成稿段", "文本", "拆分", "情感",
    "情感强度", "语速", "前停顿_ms", "后停顿_ms"
]


def validate_structure(data: list) -> list[str]:
    """校验根结构"""
    errors = []
    if not isinstance(data, list):
        errors.append("根对象必须是 JSON 数组")
        return errors
    if len(data) == 0:
        errors.append("画本数组为空")
    return errors


def validate_card(card: dict, idx: int) -> list[str]:
    """校验单个画本对象"""
    errors = []

    # 必填字段
    for field in REQUIRED_FIELDS:
        if field not in card:
            errors.append(f"[段 {idx}] 缺少必填字段: {field}")

    # 拆分检查
    if "拆分" in card:
        if not isinstance(card["拆分"], list):
            errors.append(f"[段 {idx}] '拆分' 必须是数组")
        else:
            for i, unit in enumerate(card["拆分"]):
                if len(unit) > 80:
                    errors.append(f"[段 {idx} 单元 {i}] 字数超标: {len(unit)} 字（上限 80）")

    # 情感强度范围
    if "情感强度" in card:
        intensity = card["情感强度"]
        if not isinstance(intensity, (int, float)) or intensity < 0.0 or intensity > 1.0:
            errors.append(f"[段 {idx}] 情感强度非法: {intensity}（应在 0.0-1.0）")

    # 语速范围
    if "语速" in card:
        speed = card["语速"]
        if not isinstance(speed, (int, float)) or speed < 0.5 or speed > 2.0:
            errors.append(f"[段 {idx}] 语速非法: {speed}（应在 0.5-2.0）")

    # 停顿时间范围
    for field in ["前停顿_ms", "后停顿_ms"]:
        if field in card:
            pause = card[field]
            if not isinstance(pause, int) or pause < 0 or pause > 5000:
                errors.append(f"[段 {idx}] {field} 非法: {pause}（应在 0-5000ms）")

    # 读音表格式
    if "读音表" in card and card["读音表"] is not None:
        if not isinstance(card["读音表"], dict):
            errors.append(f"[段 {idx}] '读音表' 必须是对象")

    # 时长目标
    if "时长目标_s" in card and card["时长目标_s"] is not None:
        target = card["时长目标_s"]
        if not isinstance(target, (int, float)) or target <= 0:
            errors.append(f"[段 {idx}] 时长目标非法: {target}")

    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python validate_dubbing.py <dubbing.json>")
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
        for idx, card in enumerate(data, start=1):
            if not isinstance(card, dict):
                all_errors.append(f"[段 {idx}] 不是对象类型")
                continue
            all_errors.extend(validate_card(card, idx))

    print(f"\n{'='*60}")
    print(f"画本格式校验完成: {filepath.name}")
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
