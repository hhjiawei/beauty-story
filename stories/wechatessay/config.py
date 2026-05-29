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
ROOT = Path(__file__).parent

LOG_LEVEL = logging.INFO  # 开发用 DEBUG，生产用 INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d — %(message)s"

def setup_logging():
    """配置全局日志"""
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),  # 控制台输出
            # logging.FileHandler("wechatessay.log", encoding="utf-8"),  # 文件记录
        ],
    )

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

# ── 多模型写作配置 ──
# write_node 使用同一份写作 prompt，并行调用多个模型独立写作，择优输出。
# 每个模型独立生成完整文章，write_node 选评分最高的版本。
WRITER_CONFIG = {
    # 写作模型列表：每个模型独立写作，最后择优
    # 格式：provider:model_id
    "models": [
        "deepseek:deepseek-v4-flash",
        # "kimi:kimi-k2",
        # "qwen:qwen3.5-397B-A17B",
    ],
}

# ── 多模型评审配置 ──
# review_node 使用同一套评审提示词，轮询不同模型进行评审。
# 只评审不提修改（修改交给 write_node），输出评审意见和 passed 判断。
REVIEW_CONFIG = {
    # 评审模型：每次评审用一个模型（可轮询）
    "models": [
        "deepseek:deepseek-v4-flash",
    ],

    # 通过分数阈值（overallScore >= 此值 且 无重大问题 → passed）
    "pass_score_threshold": 85,
}

# ── write→review 循环控制 ──
# write_node 写作 → review_node 评审 → 如需修改 → 回到 write_node
# 达到最大轮次后强制通过，无论评审是否满意
MAX_REVISION_ROUNDS = 3

# ── Memory 配置 ──
MEMORY_CONFIG = {
    # ── 短期记忆 ──
    # 短期记忆 FIFO 容量（消息条数）
    "short_term_capacity": 50,

    # ── 长期记忆 ──
    # 长期记忆文件路径
    "long_term_file": MEMORY_DIR / "long_term_memory.json",

    # ── 混合检索权重 ──
    # BM25 关键词匹配权重
    "bm25_weight": 0.4,
    # 语义相似度权重
    "semantic_weight": 0.4,
    # 类型加权权重
    "type_weight": 0.2,
    # 双命中奖励（BM25 和语义同时命中时的额外加分）
    "dual_hit_bonus": 0.1,

    # ── 类型权重映射（不同类型记忆的权重系数） ──
    "type_weights": {
        "user_preference": 2.0,     # 用户偏好 — 最高优先级
        "project_fact": 1.5,        # 项目事实 — 高优先级
        "style_guide": 1.3,         # 风格指南 — 较高优先级
        "writing_rule": 1.2,        # 写作规则
        "publish_record": 0.8,      # 发布记录
        "general": 1.0,             # 一般记忆 — 默认
    },

    # ── 注入控制 ──
    # 注入系统提示词的记忆条数上限
    "max_injected_memories": 5,
    # 记忆相似度阈值（低于此值的记忆不返回）
    "memory_threshold": 0.6,

    # ── 遗忘衰减 ──
    # 时间衰减半衰期（天数）：30 天后权重衰减到约 50%
    "decay_half_life_days": 30,
    # 衰减惩罚权重系数（0~1，控制衰减的影响力）
    "decay_weight": 0.3,
    # 访问频率奖励系数
    "access_bonus_coefficient": 0.05,
    # 主动遗忘：超过此天数的记忆可能被清理
    "forget_max_age_days": 180,
    # 主动遗忘：访问次数低于此值的过期记忆将被清理
    "forget_min_access": 2,
}

# ── RAG 配置 ──
RAG_CONFIG = {
    # 向量数据库路径（SQLite）
    "vector_db_path": (MEMORY_DIR / "vector_db.sqlite").as_posix(),

    # ── Embedding 后端配置 ──
    # 可选: "ollama" | "openai" | "remote" | "mock"
    "embedding_backend": "ollama",
    # 嵌入模型名称（根据后端不同含义不同）
    "embedding_model": "nomic-embed-text",
    # 向量维度（需与模型输出维度一致）
    # nomic-embed-text: 768, text-embedding-3-small: 1536, text-embedding-3-large: 3072
    "vector_dimension": 768,

    # ── Ollama 后端配置 ──
    "ollama_base_url": "http://localhost:11434",

    # ── OpenAI 后端配置 ──
    # API Key 优先从环境变量 OPENAI_API_KEY 读取
    "openai_api_key": "",
    "openai_embedding_model": "text-embedding-3-small",

    # ── 通用远程后端配置 ──
    "remote_embedding_config": {
        "url": "https://your-embedding-api.example.com/embed",
        "headers": {"Authorization": "Bearer YOUR_TOKEN"},
        # 响应中 embedding 字段的路径，支持嵌套如 "data.embedding"
        "response_field_path": "embedding",
    },

    # ── 检索参数 ──
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