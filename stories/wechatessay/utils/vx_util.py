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
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(current_file_dir, "backends", "sources")


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


def parse_json_response(content: str) -> dict:
    """解析 LLM 的 JSON 响应"""
    try:
        content = content.strip()
        content = re.sub(r'^```json\s*', '', content)
        content = re.sub(r'^```\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
        content = content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"[JSON 解析错误] {e}")
        return {}
