"""后台日志：文件 + 控制台双通道。

日志文件：data/logs/pipeline.log（RotatingFileHandler，5MB x 3）。
节点级结构化日志另存 node_runs 表（GET /api/runs/{id}/node-runs 查看）。
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from . import config

_initialized = False


def get_logger(name: str = "pipeline") -> logging.Logger:
    global _initialized
    logger = logging.getLogger(name)
    if not _initialized:
        config.ensure_dirs()
        log_dir = config.DATA_DIR / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(log_dir / "pipeline.log", maxBytes=5 * 1024 * 1024,
                                 backupCount=3, encoding="utf-8")
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)
        logger.setLevel(logging.INFO)
        _initialized = True
    return logger


def tail_logs(lines: int = 200) -> list[str]:
    log_file = config.DATA_DIR / "logs" / "pipeline.log"
    if not log_file.exists():
        return []
    content = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    return content[-lines:]
