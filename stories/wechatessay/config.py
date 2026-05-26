"""
wechatessay 项目全局配置

集中管理所有路径、模型参数、MCP 配置、Memory 配置等。
"""
import os
from pathlib import Path
from dotenv import find_dotenv
from langchain_openai import ChatOpenAI
import logging
import sys

# ── 项目根目录 ──
_ENV_PATH = find_dotenv()
if _ENV_PATH:
    ROOT = Path(_ENV_PATH).parent
else:
    ROOT = Path(__file__).parent

# ── 子目录 ──
MEMORY_DIR = ROOT / "backends" / "memories"
SKILLS_DIR = ROOT / "backends" / "skills"
SOURCES_DIR = ROOT / "backends" / "sources"
WORKSPACES_DIR = ROOT / "backends" / "workspaces"

# ── 确保目录存在 ──
for _d in [MEMORY_DIR, SKILLS_DIR, SOURCES_DIR, WORKSPACES_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── DeepAgents Backend 配置 ──
BACKEND_CONFIG = {
    "root_dir": ROOT.as_posix(),
    "virtual_mode": True,
    "routes": {
        "/memories/": {
            "root_dir": MEMORY_DIR.as_posix(),
            "virtual_mode": True,
        },
        "/skills/": {
            "root_dir": SKILLS_DIR.as_posix(),
            "virtual_mode": True,
        },
        "/workspaces/": {
            "root_dir": WORKSPACES_DIR.as_posix(),
            "virtual_mode": True,
        },
    },
}


# 配置 API
# OPENAI_API_KEY = "468d6aba-3c9e-407f-ad91-d5f904662742"
# OPENAI_API_BASE = "https://ark.cn-beijing.volces.com/api/v3"
# MODEL_NAME = "doubao-seed-2-0-pro-260215"

# deepseek-reasoner
OPENAI_API_KEY = "sk-0638b83c1e6a47eca1aeade34c493f6a"
OPENAI_API_BASE = "https://api.deepseek.com"
MODEL_NAME = "deepseek-reasoner"


# # qwen  sk-5fd1dda940aa46d282873be7e02fcd82
# OPENAI_API_KEY = "sk-5fd1dda940aa46d282873be7e02fcd82"
# OPENAI_API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# MODEL_NAME = "qwen3.6-plus"

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE

model = ChatOpenAI(
    model=MODEL_NAME,
    temperature=1.5,
)


# ── 模型配置 ──
MODEL_CONFIG = {
    # 使用 provider:model 格式，便于切换
    "default_model": model,
    "analysis_model": model,
    "search_model": model,
    "writing_model": model,
    "review_model": model,
}

# ── Memory 配置 ──
MEMORY_CONFIG = {
    # 短期记忆 FIFO 容量（消息条数）
    "short_term_capacity": 50,
    # 长期记忆文件路径
    "long_term_file": MEMORY_DIR / "long_term_memory.json",
    # BM25 权重
    "bm25_weight": 0.4,
    # 语义相似度权重
    "semantic_weight": 0.4,
    # 代码块类型加权（此处用于文章类型识别）
    "type_weight": 0.2,
    # 双命中奖励
    "dual_hit_bonus": 0.1,
    # 注入系统提示词的记忆条数上限
    "max_injected_memories": 5,
    # 记忆相似度阈值
    "memory_threshold": 0.6,
}

# ── RAG 配置 ──
RAG_CONFIG = {
    # 向量数据库路径（SQLite）
    "vector_db_path": (MEMORY_DIR / "vector_db.sqlite").as_posix(),
    # 嵌入模型（通过 Ollama 或远程 API）
    "embedding_model": "nomic-embed-text",
    # 向量维度
    "vector_dimension": 768,
    # 检索 top-k
    "retrieve_top_k": 5,
    # 分块大小
    "chunk_size": 500,
    # 分块重叠
    "chunk_overlap": 50,
}

# ── MCP 配置文件路径 ──
MCP_CONFIG_PATH = ROOT / "tools" / "mcp_tools" / "mcp_config.json"

# ── 人机协同配置 ──
HITL_CONFIG = {
    # 是否需要人工确认
    "require_human_approval": True,
    # 最多重试次数
    "max_retry": 3,
    # 节点需要人工确认的工具
    "interrupt_tools": {
        "write_file": True,
        "edit_file": True,
    },
}

# ── 文章写作默认参数 ──
WRITING_DEFAULTS = {
    "default_word_count": 2000,
    "min_word_count": 800,
    "max_word_count": 5000,
    "default_style": "口语化大白话",
    "target_platform": "微信公众号",
}

# ── 合规检查配置 ──
LEGALITY_CONFIG = {
    # 敏感词列表（可自行扩展）
    "sensitive_keywords": [
        "政治", "色情", "暴力", "赌博", "毒品",
        "翻墙", "VPN", "非法", "违法",
    ],
    # AI 感检测关键词
    "ai_markers": [
        "首先", "其次", "再次", "最后", "综上所述",
        "值得注意的是", "总而言之", "简而言之",
        "让我们", "不难发现", "显而易见",
        "在当今社会", "随着科技的发展",
        "这是一个", "我们需要",
    ],
    # 最大 AI 感得分
    "max_ai_score": 0.3,
}

# ── 发布配置 ──
PUBLISH_CONFIG = {
    # 微信公众号相关配置占位
    "wechat_app_id": "",
    "wechat_app_secret": "",
    "default_author": "AI 写作助手",
}




LOG_LEVEL = logging.DEBUG  # 开发用 DEBUG，生产用 INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d — %(message)s"

def setup_logging():
    """配置全局日志"""
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),  # 控制台输出
            logging.FileHandler("wechatessay.log", encoding="utf-8"),  # 文件记录
        ],
    )