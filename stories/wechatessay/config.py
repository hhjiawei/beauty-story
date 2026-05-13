"""
微信公众号文章创作工作流 - 全局配置
"""

from pathlib import Path
from dotenv import find_dotenv
import os

# 项目根目录
ROOT = Path(find_dotenv()).parent if find_dotenv() else Path(__file__).parent

# ── 工作空间目录 ──
MEMORY_DIR = (ROOT / "backends" / "memories").as_posix()
SKILLS_DIR = (ROOT / "backends" / "skills").as_posix()
SOURCES_DIR = (ROOT / "backends" / "sources").as_posix()
WORKSPACE_DIR = (ROOT / "backends" / "workspaces").as_posix()

# ── LLM 配置 ──
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
COLLECT_LLM_MODEL = os.getenv("COLLECT_LLM_MODEL", "gpt-4o")
ANALYSE_LLM_MODEL = os.getenv("ANALYSE_LLM_MODEL", "gpt-4o")
PLOT_LLM_MODEL = os.getenv("PLOT_LLM_MODEL", "gpt-4o")
WRITE_LLM_MODEL = os.getenv("WRITE_LLM_MODEL", "gpt-4o")

# ── 人机协同配置 ──
HUMAN_IN_THE_LOOP = os.getenv("HUMAN_IN_THE_LOOP", "true").lower() == "true"
MAX_REVISION_ROUNDS = int(os.getenv("MAX_REVISION_ROUNDS", "5"))

# ── 搜索配置 ──
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "8"))
SEARCH_TOPIC = os.getenv("SEARCH_TOPIC", "news")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "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")

# ── MCP 服务器配置 ──
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:3333/mcp")

# ── 文章配置 ──
DEFAULT_WORD_COUNT_MIN = int(os.getenv("WORD_COUNT_MIN", "1500"))
DEFAULT_WORD_COUNT_MAX = int(os.getenv("WORD_COUNT_MAX", "3000"))

# ── DeepAgents Backend 配置 ──
# CompositeBackend 虚拟文件系统根目录
BACKEND_ROOT = ROOT
BACKEND_VIRTUAL_MODE = True

# 记录存储路径 (CompositeBackend 的 records 子目录)
RECORDS_DIR = (ROOT / "backends" / "workspaces" / "records").as_posix()

# ── Memory 配置 ──
MEMORY_CONTEXT_ENABLED = True        # 上下文记忆
MEMORY_RAG_ENABLED = True            # 向量检索记忆
MEMORY_SUMMARIZATION_ENABLED = True  # 自动摘要记忆
MEMORY_RAG_TOP_K = int(os.getenv("MEMORY_RAG_TOP_K", "5"))  # RAG 召回数量
MEMORY_SUMMARY_TRIGGER_MSG = int(os.getenv("MEMORY_SUMMARY_TRIGGER_MSG", "20"))  # 摘要触发消息数

# ── Skill 配置 ──
AUTO_LOAD_SKILLS = True  # 启动时自动加载 skills 目录下的所有 skill
