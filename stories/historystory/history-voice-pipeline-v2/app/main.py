"""FastAPI 入口：挂载 API 与静态页，/media 暴露产物与音频。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .agents import factory
from .api import projects, runs, settings_api, voices
from .db import get_engine
from .logging_setup import tail_logs

config.ensure_dirs()
get_engine()
factory.ensure_default_node_configs()   # 按 §5.1 挂载表播种默认节点配置（幂等）

app = FastAPI(title="历史短视频音频生产流水线", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(settings_api.router)
app.include_router(voices.router)

@app.get("/api/logs/tail")
def logs_tail(lines: int = 200):
    """服务器日志尾部（后台日志查看）。"""
    return {"lines": tail_logs(min(lines, 1000))}


app.mount("/media", StaticFiles(directory=str(config.DATA_DIR)), name="media")
app.mount("/", StaticFiles(directory=str(config.STATIC_DIR), html=True), name="static")
