import os
import asyncio
import subprocess
from pathlib import Path
from typing import Literal

from langchain.tools import tool


@tool
async def read_file(path: str) -> str:
    """Read file content (used to read SKILL.md)."""

    def _read():
        try:
            return Path(path).read_text(encoding="gbk")
        except:
            return Path(path).read_text(encoding="utf-8")

    try:
        return await asyncio.to_thread(_read)
    except Exception as e:
        return f"Error: {e}"


@tool
async def create_file(file_name: str, file_contents: str) -> str:
    """Create a text file."""

    def _write():
        file_path = os.path.join(os.getcwd(), file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_contents)
        return f"Created: {file_path}"

    try:
        return await asyncio.to_thread(_write)
    except Exception as e:
        return f"Error: {e}"


@tool
async def shell_exec(command: str) -> str:
    """Windows CMD/PowerShell executor."""
    blacklist = ["del", "rm", "format", "rd"]
    if any(x in command.lower() for x in blacklist):
        return "❌ Blocked dangerous command"

    try:
        # 用 asyncio 原生 subprocess，彻底非阻塞
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=20
        )
        out = stdout.decode("gbk", errors="replace")
        err = stderr.decode("gbk", errors="replace")
        return f"OUT:\n{out}\nERR:\n{err}".strip()
    except Exception as e:
        return f"Exec error: {e}"


@tool
async def tavily_web_search(
        query: str,
        max_results: int = 5,
        topic: Literal["general", "news"] = "news"
) -> dict:
    """Search the web for current information."""
    # Tavily 官方提供 AsyncTavilyClient（需确认 SDK 版本）
    try:
        from tavily import AsyncTavilyClient
        client = AsyncTavilyClient(api_key="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")
        return await client.search(query, max_results=max_results, topic=topic)
    except ImportError:
        # 降级：用线程池包装同步客户端
        from tavily import TavilyClient
        def _search():
            client = TavilyClient(api_key="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")
            return client.search(query, max_results=max_results, topic=topic)

        return await asyncio.to_thread(_search)