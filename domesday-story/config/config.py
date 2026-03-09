"""
配置文件 - 全局配置和 API 设置
"""
import os
from datetime import datetime

# ================= API 配置 =================
# 请替换为你的实际 API Key
OPENAI_API_KEY = "your-api-key-here"
OPENAI_API_BASE = "https://api.openai.com/v1"
MODEL_NAME = "gpt-4-turbo"
TEMPERATURE = 0.7

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
