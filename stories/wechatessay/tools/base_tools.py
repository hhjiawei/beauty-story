import os
import subprocess
from pathlib import Path
from typing import Literal

from langchain.tools import tool


@tool
def read_file(path: str) -> str:
    """Read file content (used to read SKILL.md)."""
    try:
        try:
            return Path(path).read_text(encoding="gbk")
        except:
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
def shell_exec(command: str) -> str:
    """Windows CMD/PowerShell executor (only tool for open browser/screenshot)."""
    blacklist = ["del", "rm", "format", "rd"]
    if any(x in command.lower() for x in blacklist):
        return "❌ Blocked dangerous command"
    try:
        res = subprocess.run(command, shell=True, capture_output=True, timeout=20, text=False)
        stdout = res.stdout.decode("gbk", errors="replace")
        stderr = res.stderr.decode("gbk", errors="replace")
        return f"OUT:\n{stdout}\nIN:\n{stderr}".strip()
    except Exception as e:
        return f"Exec error: {e}"

@tool
def tavily_web_search(query: str, max_results: int = 5, topic: Literal["general", "news"] = "news") -> dict:
    """Search the web for current information."""
    from tavily import TavilyClient
    client = TavilyClient(api_key="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")
    return client.search(query, max_results=max_results, topic=topic)














