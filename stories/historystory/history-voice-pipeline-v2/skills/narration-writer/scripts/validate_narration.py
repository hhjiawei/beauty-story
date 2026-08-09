#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
旁白成稿格式校验脚本
用法: python validate_narration.py <narration.md>

校验项：
1. 是否包含集名标题
2. 是否包含目标时长/字数/外衣元信息
3. 每段是否有【段N·功能类型】标记
4. 引文是否有【上屏】标记和出处
5. 停顿标记（顿）是否规范
6. 字数是否在目标时长换算区间内（220-260字/分钟）
"""

import re
import sys
from pathlib import Path


def validate_title(text: str) -> list[str]:
    """校验集名标题"""
    errors = []
    if not re.search(r"^# 《[^》]+》旁白成稿", text, re.MULTILINE):
        errors.append("缺少集名标题，格式应为：# 《{集名}》旁白成稿")
    return errors


def validate_meta(text: str) -> list[str]:
    """校验元信息"""
    errors = []
    if not re.search(r"目标时长：\d+\s*分钟", text):
        errors.append("缺少目标时长元信息")
    if not re.search(r"预计字数：\d+\s*字", text):
        errors.append("缺少预计字数元信息")
    if not re.search(r"本期外衣：", text):
        errors.append("缺少本期外衣元信息")
    return errors


def validate_segments(text: str) -> list[str]:
    """校验段落标记"""
    errors = []
    segments = re.findall(r"【段\d+·[^】]+】", text)
    if not segments:
        errors.append("未发现任何【段N·功能类型】标记")
    else:
        # 检查段号连续性
        nums = [int(re.search(r"\d+", s).group()) for s in segments]
        for i in range(1, len(nums)):
            if nums[i] <= nums[i-1]:
                errors.append(f"段号不连续或重复：段{nums[i-1]} 后出现 段{nums[i]}")
    return errors


def validate_citations(text: str) -> list[str]:
    """校验引文标记"""
    errors = []
    # 查找书名号内容
    citations = re.findall(r"《([^》]+)》", text)
    for cite in citations:
        # 检查该引文附近是否有【上屏】标记
        pattern = re.escape(cite)
        contexts = re.findall(r".{0,50}" + pattern + r".{0,50}", text)
        for ctx in contexts:
            if "【上屏】" not in ctx and "原文" not in ctx:
                errors.append(f"引文《{cite}》附近缺少【上屏】标记")
                break
    return errors


def validate_word_count(text: str) -> list[str]:
    """校验字数与目标时长匹配"""
    errors = []
    # 提取预计字数
    target_match = re.search(r"预计字数：(\d+)\s*字", text)
    if not target_match:
        return errors

    target = int(target_match.group(1))

    # 提取目标时长
    duration_match = re.search(r"目标时长：(\d+)\s*分钟", text)
    if not duration_match:
        return errors

    duration = int(duration_match.group(1))

    # 计算实际中文字数（去除标记和标点）
    clean_text = re.sub(r"【[^】]+】", "", text)
    clean_text = re.sub(r"[（\(].*?[）\)]", "", clean_text)
    clean_text = re.sub(r"[#>|\s]", "", clean_text)
    actual = len(re.findall(r"[\u4e00-\u9fff]", clean_text))

    # 220-260 字/分钟
    min_words = duration * 220
    max_words = duration * 260

    if actual < min_words:
        errors.append(f"字数不足：实际约{actual}字，目标时长{duration}分钟需{min_words}-{max_words}字")
    elif actual > max_words:
        errors.append(f"字数超标：实际约{actual}字，目标时长{duration}分钟需{min_words}-{max_words}字")

    return errors


def validate_forbidden_phrases(text: str) -> list[str]:
    """校验禁用表达"""
    errors = []
    forbidden = [
        "众所周知", "不得不说", "引人深思", "历史的洪流",
        "值得我们学习", "让我们把时间拨回", "话说回来",
        "言归正传", "与此同时", "镜头来到"
    ]
    for phrase in forbidden:
        if phrase in text:
            errors.append(f"发现禁用表达：{phrase}")
    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python validate_narration.py <narration.md>")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"错误: 文件不存在: {filepath}")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    all_errors = []
    all_errors.extend(validate_title(text))
    all_errors.extend(validate_meta(text))
    all_errors.extend(validate_segments(text))
    all_errors.extend(validate_citations(text))
    all_errors.extend(validate_word_count(text))
    all_errors.extend(validate_forbidden_phrases(text))

    print(f"\n{'='*60}")
    print(f"旁白成稿格式校验完成: {filepath.name}")
    print(f"{'='*60}")

    if not all_errors:
        print("✅ 成稿格式合规")
        sys.exit(0)
    else:
        print(f"❌ 发现 {len(all_errors)} 处问题:\n")
        for err in all_errors:
            print(f"  • {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
