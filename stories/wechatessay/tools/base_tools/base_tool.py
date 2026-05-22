"""
wechatessay.tools.base_tools.base_tool

基础工具集（异步版）：文件操作、Shell 执行、网页搜索等。
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Literal, Optional

from langchain.tools import tool


# ── 文件操作（全部改为 async + asyncio.to_thread） ──

@tool
async def read_file(path: str) -> str:
    """Read file content (used to read SKILL.md or any text file)."""
    def _read():
        try:
            return Path(path).read_text(encoding="gbk")
        except Exception:
            return Path(path).read_text(encoding="utf-8")
    try:
        return await asyncio.to_thread(_read)
    except Exception as e:
        return f"Error: {e}"


@tool
async def create_file(file_name: str, file_contents: str) -> str:
    """Create a text file."""
    def _create():
        file_path = os.path.join(os.getcwd(), file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_contents)
        return f"Created: {file_path}"
    try:
        return await asyncio.to_thread(_create)
    except Exception as e:
        return f"Error: {e}"


@tool
async def write_file(path: str, content: str) -> str:
    """Write content to a file (overwrite if exists)."""
    def _write():
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written: {file_path}"
    try:
        return await asyncio.to_thread(_write)
    except Exception as e:
        return f"Error: {e}"


@tool
async def edit_file(path: str, old_string: str, new_string: str) -> str:
    """Edit a file by replacing old_string with new_string."""
    def _edit():
        file_path = Path(path)
        content = file_path.read_text(encoding="utf-8")
        if old_string not in content:
            return f"Warning: old_string not found in {path}"
        content = content.replace(old_string, new_string, 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Edited: {file_path}"
    try:
        return await asyncio.to_thread(_edit)
    except Exception as e:
        return f"Error: {e}"


@tool
async def list_files(directory: str = ".") -> str:
    """List files in a directory."""
    def _list():
        path = Path(directory)
        files = [f.name for f in path.iterdir()]
        return "\n".join(files)
    try:
        return await asyncio.to_thread(_list)
    except Exception as e:
        return f"Error: {e}"


# ── Shell 执行（改用 asyncio.create_subprocess_shell，彻底非阻塞） ──

@tool
async def shell_exec(command: str) -> str:
    """Windows CMD/PowerShell executor (only tool for open browser/screenshot)."""
    blacklist = ["del", "rm", "format", "rd", "mkfs", "dd"]
    if any(x in command.lower() for x in blacklist):
        return "❌ Blocked dangerous command"
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
        out = stdout.decode("gbk", errors="replace")
        err = stderr.decode("gbk", errors="replace")
        return f"OUT:\n{out}\nERR:\n{err}".strip()
    except Exception as e:
        return f"Exec error: {e}"


# ── 获取所有基础工具的列表 ──

async def get_base_tools() -> list:
    """返回所有基础工具的列表，用于拼接 total_tools。
    注：工具本身已是 async def，LangChain 在 ainvoke 时会自动调用 arun。
    """
    return [
        read_file,
        create_file,
        write_file,
        edit_file,
        list_files,
        shell_exec,
    ]