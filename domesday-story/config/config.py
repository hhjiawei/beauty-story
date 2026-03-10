"""
配置文件 - 全局配置、API 设置和 LLM 工厂
所有配置和共享对象都集中在这里管理
"""
import os
from datetime import datetime
from langchain_ollama import ChatOllama
# from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

# ================= API 配置 =================
# 请替换为你的实际 API Key
OPENAI_API_KEY = "sk-0638b83c1e6a47eca1aeade34c493f6a"
OPENAI_API_BASE = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"
TEMPERATURE = 0.7
MAX_TOKENS = 10000
TIMEOUT = 60

# 设置环境变量
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
os.environ["OPENAI_API_BASE"] = OPENAI_API_BASE

# ================= 路径配置 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# 确保输出目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================= 文件命名 =================
def generate_filename(prefix="story"):
    """生成带时间戳的文件名"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.md"

# ================= 创作配置 =================
STORY_CONFIG = {
    "target_word_count": 6000,        # 目标字数
    "segment_count": 6,               # 分段数量
    "segment_word_count": 1000,       # 每段目标字数
    "max_iteration": 3,               # 最大重试次数
    "min_score": 55,                  # 质检最低通过分数
}

# ================= 品控标准 =================
QA_STANDARDS = {
    "completeness_min": 80,           # 完整性最低分
    "format_min": 90,                 # 格式最低分
    "quality_min": 85,                # 质量最低分
    "continuity_min": 95,             # 连贯性最低分
}

# ================= 六大特征权重 =================
SIX_FEATURES = {
    "overall": 10,                    # 整体定位
    "protagonist": 10,                # 主角设定
    "hoarding": 10,                   # 核心剧情
    "revenge": 10,                    # 终极目标
    "contrast": 10,                   # 爽感来源
    "rhythm": 10,                     # 叙事节奏
}

# ================= LLM 工厂 =================
# 缓存 LLM 实例，避免重复创建
_llm_cache = {}

def get_llm(model_name=None, temperature=None, cache=True):
    """
    LLM 工厂函数 - 获取或创建 LLM 实例

    Args:
        model_name: 模型名称，默认使用配置中的 MODEL_NAME
        temperature: 温度参数，默认使用配置中的 TEMPERATURE
        cache: 是否使用缓存，默认 True

    Returns:
        ChatOpenAI 实例
    """
    # 使用默认配置
    if model_name is None:
        model_name = MODEL_NAME
    if temperature is None:
        temperature = TEMPERATURE

    # 生成缓存键
    cache_key = f"{model_name}_{temperature}"

    # 检查缓存
    if cache and cache_key in _llm_cache:
        return _llm_cache[cache_key]

    # 创建新实例
    # llm = ChatOpenAI(
    #     model=model_name,
    #     temperature=temperature,
    #     # max_tokens=MAX_TOKENS,
    #     timeout=TIMEOUT,
    #     max_retries=2,
    # )

    llm = ChatOllama(
        model="qwen3-vl:4b",
        base_url="http://10.0.102.100:11434",
    )

    # 存入缓存
    if cache:
        _llm_cache[cache_key] = llm

    return llm


def get_llm_by_purpose(purpose="default"):
    """
    根据用途获取不同配置的 LLM 实例

    Args:
        purpose: 用途类型
            - "default": 默认配置，用于一般创作
            - "creative": 高温度，用于创意生成
            - "precise": 低温度，用于精确任务（如 JSON 解析、质检）
            - "fast": 快速模型，用于简单任务

    Returns:
        ChatOpenAI 实例
    """
    configs = {
        "default": {
            "model_name": MODEL_NAME,
            "temperature": TEMPERATURE,
        },
        "creative": {
            "model_name": MODEL_NAME,
            "temperature": 0.9,  # 更高创意性
        },
        "precise": {
            "model_name": MODEL_NAME,
            "temperature": 0.3,  # 更精确稳定
        },
        "fast": {
            "model_name": "gpt-3.5-turbo",  # 更快更便宜
            "temperature": TEMPERATURE,
        },
    }

    config = configs.get(purpose, configs["default"])
    return get_llm(
        model_name=config["model_name"],
        temperature=config["temperature"],
        cache=True
    )


# ================= 预创建常用 LLM 实例 =================
# 在模块加载时创建常用实例，避免首次调用延迟

llm_default = get_llm()                    # 默认 LLM，用于大部分节点
llm_creative = get_llm(temperature=0.9)    # 创意 LLM，用于写作节点
llm_precise = get_llm(temperature=0.3)     # 精确 LLM，用于质检和 JSON 解析

# ================= 工具函数 =================

def get_llm_stats():
    """
    获取 LLM 缓存统计信息

    Returns:
        字典，包含缓存的 LLM 实例信息
    """
    return {
        "cache_size": len(_llm_cache),
        "cached_models": list(_llm_cache.keys()),
    }


def clear_llm_cache():
    """
    清空 LLM 缓存
    用于释放内存或强制重新创建实例
    """
    global _llm_cache
    _llm_cache = {}
    print("[LLM] 缓存已清空")


# ================= 模块加载时的初始化日志 =================
print(f"[Config] LLM 配置已加载：{MODEL_NAME}, Temperature={TEMPERATURE}")
print(f"[Config] 预创建 LLM 实例：default, creative, precise")
