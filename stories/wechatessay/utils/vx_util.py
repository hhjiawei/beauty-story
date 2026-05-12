import json
from pathlib import Path
from typing import List
import logging

from wechatessay.utils.vx_web_util import web_crawler_search

import asyncio
import os
from datetime import datetime
from urllib.parse import urlparse
import re


logger = logging.getLogger(__name__)

# =============================================================================
# 四、工具函数
# =============================================================================

def scan_article_files(txt_file_path: str, output_dir: str = None) -> list:
    """
    扫描 txt 文件中的微信公众号文章地址列表，爬取文章内容并保存到本地。

    Args:
        txt_file_path: 包含微信公众号文章 URL 列表的 txt 文件路径
        output_dir: 文章保存目录，默认为项目 wechatessay/backends/sources 目录

    Returns:
        保存成功的文件地址列表（相对于 output_dir 的相对路径）
    """

    # ===== 1. 确定输出目录 =====
    if output_dir is None:
        # 根据项目结构自动定位 sources 目录
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backends', 'sources')

    # 计算 wechatessay 根目录（用于生成相对路径）
    wechatessay_root = os.path.dirname(os.path.dirname(output_dir))  # 向上回退两级到 wechatessay

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # ===== 2. 读取 URL 列表 =====
    if not os.path.exists(txt_file_path):
        return []

    with open(txt_file_path, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    if not urls:
        return []

    saved_files = []

    # ===== 3. 定义异步爬取任务 =====
    async def crawl_and_save(url: str, index: int) -> str | None:
        """爬取单个文章并保存，返回相对文件路径或 None"""

        try:
            # 使用 web_crawler_search 爬取全文（query 为空表示全文模式）
            content = await web_crawler_search(
                start_url=url,
                query="",           # 空 query，获取全文
                max_pages=1,        # 公众号文章单页即可
                max_depth=1,        # 不深入爬取
                delay=1.0,          # 适当延迟，避免被封
                max_concurrent=2,
                timeout=15.0,
                snippet_mode="paragraph",
                min_snippet_length=20,
            )

            # 解析内容，提取标题
            lines = content.split("\n")
            title = None

            for line in lines:
                # 尝试从内容中提取标题
                if not title and line.strip() and not line.startswith(("=", "📄", "🔍", "📊", "⚠️", "❌")):
                    candidate = line.strip().replace(" ", "_")
                    candidate = re.sub(r'[\\/:*?"<>|]', "", candidate)
                    if len(candidate) > 5:
                        title = candidate[:100]

            # 如果无法提取标题，使用 URL 中的路径
            if not title:
                parsed = urlparse(url)
                path_part = os.path.basename(parsed.path) or "untitled"
                title = f"article_{index}_{path_part[:50]}"

            # 生成文件名：序号_标题_时间戳.txt
            timestamp = datetime.now().strftime("%m%d_%H%M%S")
            safe_title = re.sub(r'[\\/:*?"<>|]', "", title)[:80]
            filename = f"{index:03d}_{safe_title}_{timestamp}.txt"
            file_path = os.path.join(output_dir, filename)

            # 构建保存内容
            save_content = f"""原文链接: {url}
            爬取时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            文章标题: {title}
            {'=' * 60}

            {content}

            {'=' * 60}
            """

            # 保存到文件
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(save_content)

            # 返回相对于 wechatessay 根目录的相对路径
            rel_path = os.path.relpath(file_path, wechatessay_root)
            # 统一使用正斜杠（跨平台兼容）
            rel_path = rel_path.replace(os.sep, "/")
            return rel_path

        except Exception:
            return None

    # ===== 4. 执行批量爬取 =====
    async def batch_crawl():
        results = []
        for idx, url in enumerate(urls, 1):
            rel_path = await crawl_and_save(url, idx)
            if rel_path:
                results.append(rel_path)
            # 文章间额外延迟，降低被封风险
            await asyncio.sleep(2)
        return results

    saved_files = asyncio.run(batch_crawl())

    # # ===== 5. 保存扫描报告（可选） =====
    # if saved_files:
    #     report_lines = [
    #         f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    #         f"输入文件: {txt_file_path}",
    #         f"输出目录: {output_dir}",
    #         f"总 URL 数: {len(urls)}",
    #         f"成功保存: {len(saved_files)}",
    #         "",
    #         "已保存文件列表:",
    #     ]
    #     for fp in saved_files:
    #         report_lines.append(f"  {fp}")
    #
    #     report_path = os.path.join(
    #         output_dir,
    #         f"_scan_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    #     )
    #     with open(report_path, "w", encoding="utf-8") as f:
    #         f.write("\n".join(report_lines))

    return saved_files


def read_article(file_path: str) -> str:
    """读取单篇文章"""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"读取文件失败 {file_path}: {e}")
        return ""


def split_articles(content: str, delimiter: str = "===== 文件:") -> List[str]:
    """将合并的文章内容拆分为单篇"""
    parts = content.split(delimiter)
    return [p.strip() for p in parts if p.strip()]


import json
import re
from typing import Union


def clean_markdown(text: str) -> str:
    """移除 markdown 代码块标记"""
    text = re.sub(r'^```json\s*', '', text.strip())
    text = re.sub(r'^```\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def remove_comments(raw: str) -> str:
    """移除 JSON 中的注释（// 单行 和 /* */ 多行）"""
    # 移除单行注释
    raw = re.sub(r'//.*$', '', raw, flags=re.MULTILINE)
    # 移除多行注释
    raw = re.sub(r'/\*.*?\*/', '', raw, flags=re.DOTALL)
    return raw


def remove_trailing_commas(raw: str) -> str:
    """移除对象和数组末尾的多余逗号"""
    # 移除 }, 或 ] 前面的逗号
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    return raw


def normalize_whitespace(raw: str) -> str:
    """规范化空白字符，但保留字符串内部的"""
    # 只在字符串外部处理：将多个空白合并为单个空格
    result = []
    in_string = False
    prev_char = None
    i = 0

    while i < len(raw):
        char = raw[i]

        if char == '"' and prev_char != '\\':
            in_string = not in_string
            result.append(char)
        elif not in_string and char in ' \t\n\r':
            # 字符串外部：跳过连续空白，只保留一个空格
            if result and result[-1] != ' ':
                result.append(' ')
        else:
            result.append(char)

        prev_char = char
        i += 1

    return ''.join(result)


def escape_control_chars(raw: str) -> str:
    """
    转义 JSON 字符串值内部的控制字符。
    JSON 标准：字符串中不允许裸控制字符 (U+0000-U+001F)，必须转义。
    """
    output = []
    in_string = False
    prev_char = None
    i = 0

    CONTROL_CHARS = {
        0x08: '\\b',  # 退格
        0x09: '\\t',  # 制表符
        0x0A: '\\n',  # 换行
        0x0C: '\\f',  # 换页
        0x0D: '\\r',  # 回车
    }

    while i < len(raw):
        char = raw[i]
        code = ord(char)

        if char == '"' and prev_char != '\\':
            in_string = not in_string
            output.append(char)
        elif in_string and code in CONTROL_CHARS:
            output.append(CONTROL_CHARS[code])
        elif in_string and 0x00 <= code <= 0x1F:
            # 其他控制字符用 Unicode 转义
            output.append(f'\\u{code:04x}')
        else:
            output.append(char)

        prev_char = char
        i += 1

    return ''.join(output)


def fix_unescaped_quotes(raw: str) -> str:
    """
    修复 JSON 字符串值内部未转义的双引号。
    核心逻辑：通过向前看判断引号是字符串结束还是内容的一部分。
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
                    # 是字符串结束符
                    in_string = False
                    output.append('"')
                else:
                    # 是字符串内部的引号，需要转义
                    output.append('\\"')
            else:
                # 字符串开始
                in_string = True
                output.append('"')
        else:
            output.append(char)

        prev_char = char
        i += 1

    return ''.join(output)


def fix_single_quotes(raw: str) -> str:
    """将 JSON 中的单引号字符串转换为双引号"""
    # 简单场景：key 和 string value 都使用单引号
    # 注意：这个实现比较基础，复杂嵌套场景可能需要更完善的解析器
    result = []
    in_string = False
    string_char = None
    prev_char = None
    i = 0

    while i < len(raw):
        char = raw[i]

        if char in "'\"" and prev_char != '\\':
            if not in_string:
                in_string = True
                string_char = char
                result.append('"')  # 统一转为双引号
            elif string_char == char:
                in_string = False
                string_char = None
                result.append('"')
            else:
                # 字符串内部出现另一种引号，保持原样
                result.append(char)
        else:
            result.append(char)

        prev_char = char
        i += 1

    return ''.join(result)


def fix_bare_words(raw: str) -> str:
    """修复裸词（未加引号的 key 或 value）"""
    # 匹配未引号的标识符作为 key：word:
    # 注意：这个正则比较激进，可能误伤，谨慎使用
    raw = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', raw)
    # 修复未引号的字符串值（如 true, false, null 之外的单词）
    # 这个需要更精细的处理，简单场景可用
    return raw


def validate_and_report(raw: str) -> tuple[bool, list[str]]:
    """验证 JSON 并报告错误位置"""
    errors = []
    try:
        json.loads(raw)
        return True, []
    except json.JSONDecodeError as e:
        # 提取错误位置上下文
        pos = e.pos
        start = max(0, pos - 30)
        end = min(len(raw), pos + 30)
        context = raw[start:end].replace('\n', '\\n')
        pointer = ' ' * (pos - start) + '^'

        errors.append(f"位置 {pos} (行 {e.lineno}, 列 {e.colno}): {e.msg}")
        errors.append(f"上下文: ...{context}...")
        errors.append(f"         {pointer}")
        return False, errors


def robust_json_loads(text: str, verbose: bool = False) -> Union[dict, list, None]:
    """
    鲁棒的 JSON 解析器，自动处理各种脏数据。

    处理流程（按优先级）：
    1. 直接解析（最干净的情况）
    2. 清理 Markdown 代码块
    3. 移除注释
    4. 移除末尾逗号
    5. 转义控制字符
    6. 修复未转义引号
    7. 修复单引号
    8. 规范化空白
    """
    if not text or not text.strip():
        return None

    # 阶段 0：原始尝试
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 阶段 1：基础清理
    cleaned = clean_markdown(text)

    # 阶段 2：语法修复（不影响字符串内容）
    cleaned = remove_comments(cleaned)
    cleaned = remove_trailing_commas(cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 阶段 3：字符串内容修复（需要状态机）
    # 注意：执行顺序很重要！
    fixed = escape_control_chars(cleaned)  # 先处理控制字符
    fixed = fix_unescaped_quotes(fixed)  # 再处理引号（此时字符串边界已清晰）
    fixed = fix_single_quotes(fixed)  # 单引号转双引号
    fixed = normalize_whitespace(fixed)  # 最后规范化空白

    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        if verbose:
            print(f"[JSON 解析失败] {e}")
            is_valid, errors = validate_and_report(fixed)
            for err in errors:
                print(f"  {err}")
        return None


def parse_json_response(content: str) -> dict:
    """兼容原有接口的封装"""
    result = robust_json_loads(content, verbose=True)
    if result is None:
        return {}
    if isinstance(result, dict):
        return result
    # 如果顶层是列表，包装为字典
    return {"data": result}


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 测试各种脏数据场景
    test_cases = [
        # 场景 1：控制字符（你的原始问题）
        '''```json
        {
          "text": "第一行
第二行
第三行"
        }
        ```''',

        # 场景 2：未转义引号
        '''{"text": "他说"你好"世界"}''',

        # 场景 3：末尾逗号
        '''{"a": 1, "b": 2,}''',

        # 场景 4：注释
        '''{
            // 这是注释
            "a": 1,
            /* 多行
               注释 */
            "b": 2
        }''',

        # 场景 5：单引号
        """{'name': '张三', 'age': 25}""",

        # 场景 6：综合脏数据
        '''```json
        {
          "cause": "第一行
第二行有"引号"问题",
          "list": [1, 2, 3,],  // 末尾逗号
          'single': 'value'
        }
        ```''',
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n{'=' * 50}")
        print(f"测试场景 {i}")
        print(f"{'=' * 50}")
        result = robust_json_loads(case, verbose=True)
        print(f"结果: {result}")