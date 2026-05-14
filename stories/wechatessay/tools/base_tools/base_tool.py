"""
wechatessay.tools.base_tools.base_tool

基础工具集：文件操作、Shell 执行、网页搜索等。
这些工具会拼接进 total_tools，供各节点的 Deep Agent 使用。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Literal, Optional

from langchain.tools import tool


# ── 文件操作 ──

@tool
def read_file(path: str) -> str:
    """Read file content (used to read SKILL.md or any text file)."""
    try:
        try:
            return Path(path).read_text(encoding="gbk")
        except Exception:
            return Path(path).read_text(encoding="utf-8")
    except Exception as e:
        return f"Error: {e}"


@tool
def create_file(file_name: str, file_contents: str) -> str:
    """Create a text file."""
    try:
        file_path = os.path.join(os.getcwd(), file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_contents)
        return f"Created: {file_path}"
    except Exception as e:
        return f"Error: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file (overwrite if exists)."""
    try:
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written: {file_path}"
    except Exception as e:
        return f"Error: {e}"


@tool
def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Edit a file by replacing old_string with new_string."""
    try:
        file_path = Path(path)
        content = file_path.read_text(encoding="utf-8")
        if old_string not in content:
            return f"Warning: old_string not found in {path}"
        content = content.replace(old_string, new_string, 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Edited: {file_path}"
    except Exception as e:
        return f"Error: {e}"


@tool
def list_files(directory: str = ".") -> str:
    """List files in a directory."""
    try:
        path = Path(directory)
        files = [f.name for f in path.iterdir()]
        return "\n".join(files)
    except Exception as e:
        return f"Error: {e}"


# ── Shell 执行 ──

@tool
def shell_exec(command: str) -> str:
    """Windows CMD/PowerShell executor (only tool for open browser/screenshot)."""
    blacklist = ["del", "rm", "format", "rd", "mkfs", "dd"]
    if any(x in command.lower() for x in blacklist):
        return "❌ Blocked dangerous command"
    try:
        res = subprocess.run(command, shell=True, capture_output=True, timeout=20, text=False)
        stdout = res.stdout.decode("gbk", errors="replace")
        stderr = res.stderr.decode("gbk", errors="replace")
        return f"OUT:\n{stdout}\nIN:\n{stderr}".strip()
    except Exception as e:
        return f"Exec error: {e}"


# ── 网页搜索 ──

@tool
def tavily_web_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news"] = "news",
) -> dict:
    """Search the web for current information using Tavily."""
    try:
        from tavily import TavilyClient
        api_key = os.environ.get("TAVILY_API_KEY", "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")
        client = TavilyClient(api_key=api_key)
        return client.search(query, max_results=max_results, topic=topic)
    except Exception as e:
        return {"error": str(e), "results": []}


@tool
def search_zhihu(query: str, max_results: int = 3) -> dict:
    """Search Zhihu for high-engagement answers and comments."""
    try:
        from tavily import TavilyClient
        api_key = os.environ.get("TAVILY_API_KEY", "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")
        client = TavilyClient(api_key=api_key)
        zhihu_query = f"site:zhihu.com {query} 高赞"
        return client.search(zhihu_query, max_results=max_results, topic="general")
    except Exception as e:
        return {"error": str(e), "results": []}


@tool
def search_toutiao(query: str, max_results: int = 3) -> dict:
    """Search Toutiao for trending opinions and high-engagement content."""
    try:
        from tavily import TavilyClient
        api_key = os.environ.get("TAVILY_API_KEY", "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")
        toutiao_query = f"site:toutiao.com {query}"
        return client.search(toutiao_query, max_results=max_results, topic="news")
    except Exception as e:
        return {"error": str(e), "results": []}


@tool
def search_related_topics(query: str, max_results: int = 3) -> dict:
    """Search for related topics, different opinions and controversies."""
    try:
        from tavily import TavilyClient
        api_key = os.environ.get("TAVILY_API_KEY", "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")
        client = TavilyClient(api_key=api_key)
        related_query = f"{query} 争议 观点 评论"
        return client.search(related_query, max_results=max_results, topic="general")
    except Exception as e:
        return {"error": str(e), "results": []}


# ── 文章读取工具 ──

@tool
def scan_article_files(txt_file_path: str) -> list:
    """
    扫描 txt 文件中的微信公众号文章地址列表。

    Args:
        txt_file_path: 包含微信公众号文章 URL 列表的 txt 文件路径

    Returns:
        文件地址列表
    """
    try:
        path = Path(txt_file_path)
        if not path.exists():
            return []
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        return lines
    except Exception as e:
        return []


@tool
def read_article_content(file_path: str) -> str:
    """
    读取单篇文章内容。

    支持直接读取 URL（自动爬取）或本地文件。
    """
    try:
        content = Path(file_path).read_text(encoding="utf-8")
        return content
    except Exception as e:
        return f"Error reading article: {e}"


# ── 获取所有基础工具的列表 ──

def get_base_tools() -> list:
    """返回所有基础工具的列表，用于拼接 total_tools。"""
    return [
        read_file,
        create_file,
        write_file,
        edit_file,
        list_files,
        shell_exec,
        tavily_web_search,
        search_zhihu,
        search_toutiao,
        search_related_topics,
        scan_article_files,
        read_article_content,
    ]
