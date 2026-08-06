"""SQLite 引擎与建表。"""
from __future__ import annotations

from sqlmodel import SQLModel, create_engine, Session

from . import config
from . import models  # noqa: F401  确保表注册

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        config.ensure_dirs()
        _engine = create_engine(
            f"sqlite:///{config.DB_PATH}",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(_engine)
    return _engine


def reset_engine(db_path=None):
    """测试用：重建引擎指向临时库。"""
    global _engine
    if db_path is not None:
        config.DB_PATH = db_path
    _engine = None
    return get_engine()


def session() -> Session:
    return Session(get_engine())
