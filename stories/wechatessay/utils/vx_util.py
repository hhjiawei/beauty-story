from pathlib import Path
from typing import Optional, List
import logging
from wechatessay.states.vx_state import MapReduceState


logger = logging.getLogger(__name__)


# 输入时创建 mapreduce state 传入 input_path
def create_mapreduce_state(input_path: str, articles_content: Optional[str] = None) -> MapReduceState:
    return {
        "input_path": input_path,
        "articles_content": articles_content,
        "article_files": [],
        "per_article_results": [],
        "analysis_result": None,
        "error": None,
        "raw_response": None,
    }


# =============================================================================
# 四、工具函数
# =============================================================================

def scan_article_files(input_path: str) -> List[str]:
    """扫描路径下的所有文章文件"""
    path = Path(input_path)
    files = []

    if path.is_file():
        files = [str(path)]
    elif path.is_dir():
        for ext in ["*.txt", "*.md", "*.html", "*.htm", "*.json"]:
            files.extend(sorted(path.rglob(ext)))

    return [str(f) for f in files]


def read_article(file_path: str) -> str:
    """读取单篇文章"""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"读取文件失败 {file_path}: {e}")
        return ""


def split_articles(content: str, delimiter: str = "===== 文件:") -> List[str]:
    """将合并的文章内容拆分为单篇"""
    parts = content.split(delimiter)
    return [p.strip() for p in parts if p.strip()]