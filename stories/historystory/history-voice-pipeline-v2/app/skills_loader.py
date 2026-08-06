"""技能加载器：读取 skills/ 目录下各技能的 SKILL.md。

六份方法论文档是流水线的灵魂——正文原样加载，只剥 frontmatter。
deepagents 渐进加载模式下，本模块同时提供技能清单/元数据（名称+描述），
供节点挂载配置与 prompt 的「已挂载技能清单」段使用。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from . import config


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """返回 (frontmatter 键值, 正文)。仅解析 name:/description: 等简单标量行。"""
    meta: dict[str, str] = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"').strip("'")
            nl = text.find("\n", end + 1)
            return meta, (text[nl + 1:] if nl != -1 else "")
    return meta, text


def _strip_frontmatter(text: str) -> str:
    return _split_frontmatter(text)[1]


@lru_cache(maxsize=None)
def load_skill(name: str) -> str:
    """按技能名加载正文（去 frontmatter）。未找到抛 FileNotFoundError。"""
    path: Path = config.SKILLS_DIR / name / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(f"技能不存在: {name} ({path})")
    return _strip_frontmatter(path.read_text(encoding="utf-8")).strip()


def skill_exists(name: str) -> bool:
    return (config.SKILLS_DIR / name / "SKILL.md").exists()


def skill_description(name: str) -> str:
    """技能 frontmatter 的 description（渐进加载第 1 层元数据）。"""
    path: Path = config.SKILLS_DIR / name / "SKILL.md"
    if not path.exists():
        return ""
    meta, _ = _split_frontmatter(path.read_text(encoding="utf-8"))
    return meta.get("description", "")


def list_skills() -> list[dict]:
    """列出技能库全部可用技能：[{name, description}]，按目录名排序。"""
    out = []
    if not config.SKILLS_DIR.exists():
        return out
    for d in sorted(config.SKILLS_DIR.iterdir()):
        if d.is_dir() and (d / "SKILL.md").exists():
            out.append({"name": d.name, "description": skill_description(d.name)})
    return out
