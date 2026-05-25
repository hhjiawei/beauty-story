"""
wechatessay.utils.json_utils

JSON 解析工具、文件读取工具等通用工具函数。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def clean_markdown(text: str) -> str:
    """移除 markdown 代码块标记（```json 和 ```）。"""
    text = re.sub(r'^```json\s*', '', text.strip(), flags=re.IGNORECASE)
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def extract_json_block(text: str) -> str:
    """
    从文本中提取 ```json ... ``` 或 ``` ... ``` 代码块内容。

    LLM 返回的内容常常是：
        "现在我已完成...（废话）
        ```json
        { ... }
        ```"
    本函数负责定位并提取代码块内部纯 JSON 文本。

    返回：代码块内的纯文本（已去掉 ``` 标记），如果没找到则返回原文本。
    """
    if not text:
        return ""

    # 匹配 ```json ... ``` 或 ``` ... ```（非贪婪，支持跨行）
    pattern = r'```(?:json)?\s*\n?(.*?)\n?\s*```'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

    if matches:
        # 取第一个匹配，去掉首尾空白
        extracted = matches[0].strip()
        return extracted

    # 没找到代码块，返回原文（让后续步骤尝试）
    return text.strip()


def fix_unescaped_quotes(raw: str) -> str:
    """
    修复 JSON 字符串值内部未转义的双引号。
    通过向前看判断引号是"字符串边界"还是"字符串内容"。
    """
    output = []
    in_string = False
    prev_char = None
    i = 0

    while i < len(raw):
        char = raw[i]

        if char == '"' and prev_char != '\\':
            if in_string:
                # 向前看：跳过空白，检查是否是 JSON 结构符
                j = i + 1
                while j < len(raw) and raw[j] in ' \t\n\r':
                    j += 1

                if j < len(raw) and raw[j] in [',', ':', '}', ']', '\n']:
                    in_string = False
                    output.append('"')
                else:
                    output.append('\\"')
            else:
                in_string = True
                output.append('"')
        else:
            output.append(char)

        prev_char = char
        i += 1

    return ''.join(output)


def remove_comments(raw: str) -> str:
    """移除 JSON 中的注释（// 单行 和 /* */ 多行）。"""
    raw = re.sub(r'//.*$', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'/\*.*?\*/', '', raw, flags=re.DOTALL)
    return raw


def remove_trailing_commas(raw: str) -> str:
    """移除对象和数组末尾的多余逗号。"""
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    return raw


def parse_json_response(content: str) -> Dict[str, Any]:
    """
    从 LLM 响应中解析 JSON（鲁棒版本）。

    处理流程：
    1. 从文本中提取 ```json ... ``` 代码块（跳过前面的废话）
    2. 去掉 ``` 标记
    3. 尝试直接解析
    4. 失败则修复未转义引号后重试
    5. 再失败则尝试去掉注释、尾部逗号后重试
    6. 最终 fallback：从文本中 brute-force 找 JSON 对象

    Args:
        content: LLM 返回的原始文本（可能含废话前缀）

    Returns:
        解析后的字典，失败返回 {}
    """
    if not content or not content.strip():
        return {}

    # ── 步骤 1: 提取代码块（跳过废话） ──
    extracted = extract_json_block(content)

    # ── 步骤 2: 清洗 markdown 标记 ──
    cleaned = clean_markdown(extracted)

    # ── 步骤 3: 第一次解析尝试 ──
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # ── 步骤 4: 修复未转义的引号 ──
    try:
        fixed = fix_unescaped_quotes(cleaned)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # ── 步骤 5: 移除注释 + 尾部逗号 ──
    try:
        sanitized = remove_comments(cleaned)
        sanitized = remove_trailing_commas(sanitized)
        return json.loads(sanitized)
    except json.JSONDecodeError:
        pass

    # ── 步骤 6: Brute-force 从文本中找 JSON 对象 ──
    # 匹配最外层 { ... }
    obj_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    obj_match = re.search(obj_pattern, cleaned, re.DOTALL)
    if obj_match:
        try:
            return json.loads(obj_match.group())
        except json.JSONDecodeError:
            pass

    # 匹配最外层 [ ... ]
    arr_pattern = r'\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]'
    arr_match = re.search(arr_pattern, cleaned, re.DOTALL)
    if arr_match:
        try:
            return {"_array_result": json.loads(arr_match.group())}
        except json.JSONDecodeError:
            pass

    # ── 最终 fallback ──
    print(f"[parse_json_response] 无法解析 JSON，返回空字典。原始内容前200字: {content[:200]}...")
    return {}


def scan_article_files(txt_file_path: str, output_dir: str = None) -> list:
    """
    扫描 txt 文件中的微信公众号文章地址列表。

    Args:
        txt_file_path: 包含微信公众号文章 URL 列表的 txt 文件路径
        output_dir: 文章保存目录（可选）

    Returns:
        文件地址列表（URL 列表）
    """
    try:
        path = Path(txt_file_path)
        if not path.exists():
            print(f"[scan_article_files] 文件不存在: {txt_file_path}")
            return []

        with open(path, "r", encoding="utf-8") as f:
            lines = [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]

        # 过滤出有效的 URL
        urls = [
            line for line in lines
            if line.startswith("http://") or line.startswith("https://")
        ]

        print(f"[scan_article_files] 从 {txt_file_path} 读取到 {len(urls)} 个 URL")
        return urls

    except Exception as e:
        print(f"[scan_article_files] 错误: {e}")
        return []


def read_article(file_path: str) -> str:
    """
    读取单篇文章内容。

    支持：
    1. 本地文件路径
    2. URL（自动下载）

    Args:
        file_path: 文件路径或 URL

    Returns:
        文章内容
    """
    try:
        # 检查是否为 URL
        if file_path.startswith("http://") or file_path.startswith("https://"):
            return _fetch_article_from_url(file_path)

        # 本地文件
        path = Path(file_path)
        if not path.exists():
            return f"Error: 文件不存在: {file_path}"

        # 尝试多种编码
        for encoding in ["utf-8", "gbk", "gb2312", "latin-1"]:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue

        return f"Error: 无法解码文件: {file_path}"

    except Exception as e:
        return f"Error: {e}"


def _fetch_article_from_url(url: str) -> str:
    """
    从 URL 获取文章内容。

    这是一个简化实现，实际应使用更强大的爬虫。
    """
    try:
        import urllib.request
        from urllib.error import URLError

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read()

        # 尝试多种编码解码
        for encoding in ["utf-8", "gbk", "gb2312"]:
            try:
                text = html.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = html.decode("utf-8", errors="replace")

        # 简单提取正文（去掉 HTML 标签）
        # 实际应用中应使用 BeautifulSoup 等库
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&\w+;', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        return text[:10000]  # 限制长度

    except URLError as e:
        return f"Error: 无法获取 URL: {url}, 原因: {e}"
    except Exception as e:
        return f"Error: {e}"


def safe_json_dump(obj: Any, indent: int = 2, ensure_ascii: bool = False) -> str:
    """安全地将对象序列化为 JSON 字符串。"""
    try:
        return json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii, default=str)
    except Exception as e:
        return f'{{"error": "JSON 序列化失败: {e}"}}'