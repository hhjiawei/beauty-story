"""技能加载器：读取 skills/ 目录下各技能的 SKILL.md。

六份方法论文档是流水线的灵魂——正文原样加载，只剥 frontmatter。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from . import config


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            nl = text.find("\n", end + 1)
            return text[nl + 1 :] if nl != -1 else ""
    return text


@lru_cache(maxsize=None)
def load_skill(name: str) -> str:
    """按技能名加载正文（去 frontmatter）。未找到抛 FileNotFoundError。"""
    path: Path = config.SKILLS_DIR / name / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(f"技能不存在: {name} ({path})")
    return _strip_frontmatter(path.read_text(encoding="utf-8")).strip()


def skill_exists(name: str) -> bool:
    return (config.SKILLS_DIR / name / "SKILL.md").exists()
