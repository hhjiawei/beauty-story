"""
JSON 工具函数

提供 JSON 解析、清理和格式化工具。
"""

import json
import re
from typing import Optional


def parse_json_response(content: str) -> dict:
    """
    从 LLM 响应中提取并解析 JSON。

    支持以下格式：
    1. 纯 JSON 字符串
    2. Markdown 代码块中的 JSON（```json ... ```）
    3. 混合文本中的 JSON（提取第一个 { 到最后一个 }）

    Args:
        content: LLM 返回的原始文本

    Returns:
        解析后的字典

    Raises:
        ValueError: 无法解析 JSON 时
    """
    if not content or not content.strip():
        raise ValueError("Empty content")

    content = content.strip()

    # 尝试 1: 直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 尝试 2: 提取 Markdown 代码块
    code_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?\s*```'
    matches = re.findall(code_block_pattern, content, re.DOTALL)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # 尝试 3: 提取第一个 { 到最后一个 }
    try:
        start = content.index('{')
        end = content.rindex('}') + 1
        return json.loads(content[start:end])
    except (ValueError, json.JSONDecodeError):
        pass

    # 尝试 4: 提取第一个 [ 到最后一个 ]
    try:
        start = content.index('[')
        end = content.rindex(']') + 1
        return json.loads(content[start:end])
    except (ValueError, json.JSONDecodeError):
        pass

    # 尝试 5: 清理常见 JSON 格式问题后重试
    cleaned = _clean_json_string(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        raise ValueError(f"Unable to parse JSON from content: {content[:200]}...")


def _clean_json_string(content: str) -> str:
    """清理 JSON 字符串中的常见问题"""
    # 移除 BOM
    content = content.lstrip('\ufeff')
    # 替换中文引号
    content = content.replace('"', '"').replace('"', '"')
    content = content.replace(''', ''').replace(''', ''')
    # 移除尾部逗号
    content = re.sub(r',(\s*[}\]])', r'\1', content)
    return content


def safe_json_dumps(obj, ensure_ascii: bool = False, indent: int = 2) -> str:
    """安全地将对象序列化为 JSON 字符串"""
    return json.dumps(obj, ensure_ascii=ensure_ascii, indent=indent, default=str)


def extract_json_from_text(text: str) -> Optional[dict]:
    """
    从文本中提取 JSON 对象（不抛出异常）

    Args:
        text: 可能包含 JSON 的文本

    Returns:
        解析后的字典，如果失败则返回 None
    """
    try:
        return parse_json_response(text)
    except ValueError:
        return None
