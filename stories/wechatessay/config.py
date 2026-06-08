"""
wechatessay 项目全局配置

集中管理所有路径、模型参数、MCP 配置、Memory 配置等。
所有模型通过 langchain_openai.ChatOpenAI 直接实例化（OpenAI 兼容接口）。
"""

import os
import logging
import sys
from pathlib import Path
from dotenv import find_dotenv
from langchain_openai import ChatOpenAI

# ── 项目根目录 ──
_ENV_PATH = find_dotenv()
if _ENV_PATH:
    ROOT = Path(_ENV_PATH).parent
else:
    ROOT = Path(__file__).parent

# ── 日志配置 ──
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d — %(message)s"


def setup_logging():
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


# ═══════════════════════════════════════════════
# 模型实例定义（OpenAI 兼容接口）
# ═══════════════════════════════════════════════
#
# 所有模型统一使用 ChatOpenAI 包装（OpenAI 兼容格式）。
# 如需新增模型：直接添加 ChatOpenAI 实例，然后在 WRITER_CONFIG / REVIEW_CONFIG 中引用。

# ── DeepSeek ──
deepseek_model = ChatOpenAI(
    model="deepseek-v4-flash",
    base_url="https://api.deepseek.com",
    api_key="sk-c619888c986041ba9646db331483d4c6",
    temperature=1.0,
)

# ── 豆包 / 火山方舟 ──
doubao_model = ChatOpenAI(
    model="doubao-seed-2-0-pro-260215",
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key="468d6aba-3c9e-407f-ad91-d5f904662742",
    temperature=1.0,
    max_tokens=18192,  # 显式设置，输出不再截断

)

# ── Qwen（如需启用，取消注释） ──
# qwen_model = ChatOpenAI(
#     model="qwen3.6-plus",
#     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
#     api_key="sk-...",
#     temperature=1.0,
# )


# ═══════════════════════════════════════════════
# 模型选择配置
# ═══════════════════════════════════════════════

# 所有可用模型名称 → 实例的映射
# 代码中通过名称（如 "deepseek"、"doubao"）引用模型
MODEL_REGISTRY = {
    "deepseek": deepseek_model,
    "doubao": doubao_model,
    # "qwen": qwen_model,
}


IMAGE_KEY = {
    "OPENAI_API_KEY": "468d6aba-3c9e-407f-ad91-d5f904662742",
}

# Inject GEMINI_API_KEY into environment for image generation tools
os.environ["GEMINI_API_KEY"] = IMAGE_KEY["OPENAI_API_KEY"]
os.environ["IMGBB_API_KEY"] = IMAGE_KEY["OPENAI_API_KEY"]




# 各节点默认使用的模型（写名称，从 MODEL_REGISTRY 解析）
MODEL_CONFIG = {
    "default_model": "deepseek",
    "analysis_model": "deepseek",
    "search_model": "deepseek",
    "writing_model": "deepseek",
    "review_model": "doubao",
}

# write_node 可用写作模型（列表，串行轮询）
WRITER_CONFIG = {
    "models": ["deepseek", "doubao"],
}

# review_node 可用评审模型（列表，随机选≠写作模型的）
REVIEW_CONFIG = {
    "models": ["deepseek", "doubao"],
    "pass_score_threshold": 85,
}


# ═══════════════════════════════════════════════
# 其他配置（保持不变）
# ═══════════════════════════════════════════════

# ── 子目录 ──
MEMORY_DIR = ROOT / "backends" / "memories"
SKILLS_DIR = ROOT / "backends" / "skills"
SOURCES_DIR = ROOT / "backends" / "sources"
WORKSPACES_DIR = ROOT / "backends" / "workspaces"

for _d in [MEMORY_DIR, SKILLS_DIR, SOURCES_DIR, WORKSPACES_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ── DeepAgents Backend ──
BACKEND_CONFIG = {
    "root_dir": ROOT.as_posix(),
    "virtual_mode": True,
    "routes": {
        "/memories/": {"root_dir": MEMORY_DIR.as_posix(), "virtual_mode": True},
        "/skills/": {"root_dir": SKILLS_DIR.as_posix(), "virtual_mode": True},
        "/workspaces/": {"root_dir": WORKSPACES_DIR.as_posix(), "virtual_mode": True},
    },
}

# ── write→review 循环控制 ──
MAX_REVISION_ROUNDS = 3

# ── Memory 配置 ──
MEMORY_CONFIG = {
    "short_term_capacity": 50,
    "long_term_file": MEMORY_DIR / "long_term_memory.json",
    "thought_file": MEMORY_DIR / "thought.md",
    "bm25_weight": 0.4,
    "semantic_weight": 0.4,
    "type_weight": 0.2,
    "dual_hit_bonus": 0.1,
    "type_weights": {
        "user_preference": 2.0,
        "project_fact": 1.5,
        "style_guide": 1.3,
        "writing_rule": 1.2,
        "publish_record": 0.8,
        "general": 1.0,
    },
    "max_injected_memories": 5,
    "memory_threshold": 0.6,
    "decay_half_life_days": 30,
    "decay_weight": 0.3,
    "access_bonus_coefficient": 0.05,
    "forget_max_age_days": 180,
    "forget_min_access": 2,
}

# ── RAG 配置 ──
RAG_CONFIG = {
    "vector_db_path": (MEMORY_DIR / "vector_db.sqlite").as_posix(),
    "embedding_backend": "ollama",
    "embedding_model": "nomic-embed-text",
    "vector_dimension": 768,
    "ollama_base_url": "http://localhost:11434",
    "openai_api_key": "",
    "openai_embedding_model": "text-embedding-3-small",
    "remote_embedding_config": {
        "url": "https://your-embedding-api.example.com/embed",
        "headers": {"Authorization": "Bearer YOUR_TOKEN"},
        "response_field_path": "embedding",
    },
    "retrieve_top_k": 5,
    "chunk_size": 500,
    "chunk_overlap": 50,
}

# ── MCP 配置 ──
MCP_CONFIG_PATH = ROOT / "tools" / "mcp_tools" / "mcp_config.json"

# ── HITL 配置 ──
HITL_CONFIG = {
    "require_human_approval": True,
    "max_retry": 3,
    "interrupt_tools": {"write_file": True, "edit_file": True},
}

# ── 写作默认参数 ──
WRITING_DEFAULTS = {
    "default_word_count": 2000,
    "min_word_count": 800,
    "max_word_count": 5000,
    "default_style": "口语化大白话",
    "target_platform": "微信公众号",
}

# ── 合规检查 ──
LEGALITY_CONFIG = {
    "sensitive_keywords": ["政治", "色情", "暴力", "赌博", "毒品", "翻墙", "VPN", "非法", "违法"],
    "ai_markers": [
        "首先", "其次", "再次", "最后", "综上所述",
        "值得注意的是", "总而言之", "简而言之",
        "让我们", "不难发现", "显而易见",
        "在当今社会", "随着科技的发展",
    ],
    "max_ai_score": 0.3,
}

PUBLISH_CONFIG = {
    "theme_id": "default",  # wenyan-mcp 主题
    "wechat_app_id": "",    # 多号发布时指定
    "default_author": "AI写作助手",
}


# ═══════════════════════════════════════════════
# 模型解析工具函数
# ═══════════════════════════════════════════════

def get_model_instance(name: str) -> ChatOpenAI:
    """
    根据模型名称从 MODEL_REGISTRY 获取 ChatOpenAI 实例。

    用法：
        model = get_model_instance("deepseek")
        model = get_model_instance(MODEL_CONFIG["writing_model"])

    所有节点统一使用此函数，不再直接写 provider:model_id。
    """
    if name not in MODEL_REGISTRY:
        raise KeyError(
            f"模型 '{name}' 未在 MODEL_REGISTRY 中注册。"
            f"可用模型: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[name]


# 启动时打印模型注册状态
for _name, _inst in MODEL_REGISTRY.items():
    print(f"[config] 模型 '{_name}' ({_inst.model}) — 已就绪")