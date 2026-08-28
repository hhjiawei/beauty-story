#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
风格施工包格式校验脚本
用法: python validate_style.py <style-package.md>

校验项：
1. 是否包含风格名与核心气质
2. 是否包含叙事模板
3. 是否包含语气示例句（至少3句）
4. 是否包含施工要点
5. 是否包含禁忌清单
6. 是否包含适用性说明
7. 风格名是否在库内（周星驰/昆汀/诺兰/当年明月）
"""

import re
import sys
from pathlib import Path

VALID_STYLES = {"周星驰", "昆汀", "诺兰", "当年明月"}


def validate_title(text: str) -> list[str]:
    """校验标题"""
    errors = []
    if not re.search(r"^# 风格施工包 ·", text, re.MULTILINE):
        errors.append("缺少标题，格式应为：# 风格施工包 · {集名}")
    return errors


def validate_meta(text: str) -> list[str]:
    """校验元信息"""
    errors = []
    if not re.search(r"风格：", text):
        errors.append("缺少风格元信息")
    if not re.search(r"题材：", text):
        errors.append("缺少题材元信息")
    if not re.search(r"对象：", text):
        errors.append("缺少对象元信息")
    return errors


def validate_style_name(text: str) -> list[str]:
    """校验风格名是否在库内"""
    errors = []
    match = re.search(r"风格：([^｜\n]+)", text)
    if match:
        style = match.group(1).strip()
        if not any(s in style for s in VALID_STYLES):
            errors.append(f"风格名 '{style}' 不在库内（周星驰/昆汀/诺兰/当年明月）")
    else:
        errors.append("无法提取风格名")
    return errors


def validate_sections(text: str) -> list[str]:
    """校验必要章节"""
    errors = []
    required = [
        ("风格名与核心气质", r"## 一、风格名与核心气质"),
        ("叙事模板", r"## 二、叙事模板"),
        ("语气示例句", r"## 三、语气示例句"),
        ("施工要点", r"## 四、施工要点"),
        ("禁忌清单", r"## 五、禁忌清单"),
        ("适用性说明", r"## 六、适用性说明"),
    ]
    for name, pattern in required:
        if not re.search(pattern, text):
            errors.append(f"缺少必要章节：{name}")
    return errors


def validate_example_count(text: str) -> list[str]:
    """校验语气示例句数量"""
    errors = []
    section_match = re.search(r"## 三、语气示例句.*?(?=## |$)", text, re.DOTALL)
    if section_match:
        examples = re.findall(r"^\d+\.", section_match.group(), re.MULTILINE)
        if len(examples) < 3:
            errors.append(f"语气示例句不足：找到 {len(examples)} 句，需要至少 3 句")
    else:
        errors.append("未找到语气示例句章节")
    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python validate_style.py <style-package.md>")
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
    all_errors.extend(validate_style_name(text))
    all_errors.extend(validate_sections(text))
    all_errors.extend(validate_example_count(text))

    print(f"\n{'='*60}")
    print(f"风格施工包格式校验完成: {filepath.name}")
    print(f"{'='*60}")

    if not all_errors:
        print("✅ 风格施工包格式合规")
        sys.exit(0)
    else:
        print(f"❌ 发现 {len(all_errors)} 处问题:\n")
        for err in all_errors:
            print(f"  • {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
