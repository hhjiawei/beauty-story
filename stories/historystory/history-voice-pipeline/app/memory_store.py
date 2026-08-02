"""人格 L2 系列记忆（跨任务长期记忆）。

- lessons.md        打回教训沉淀：每次人工打回在任务归档时归纳追加，全部内容节点开工前读取
- voice_samples.md  声口样句库：N2/N4 闸门放行时的语气示例与声口样句
- 读音词典存数据库 pronunciation_dict 表（见 models.py）
"""
from __future__ import annotations

from datetime import UTC, datetime

from . import config

LESSONS = "lessons.md"
VOICE_SAMPLES = "voice_samples.md"


def _path(name: str):
    config.ensure_dirs()
    return config.MEMORY_DIR / name


def read_memory(name: str) -> str:
    p = _path(name)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def append_memory(name: str, entry: str) -> None:
    p = _path(name)
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"\n## {ts}\n\n{entry.strip()}\n")


def list_memories() -> list[str]:
    config.ensure_dirs()
    return [p.name for p in config.MEMORY_DIR.glob("*.md")]
