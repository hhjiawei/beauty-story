"""FastAPI 入口：挂载 API 与静态页，/media 暴露产物与音频。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from .api import projects, runs, settings_api, voices
from .db import get_engine

config.ensure_dirs()
get_engine()

app = FastAPI(title="历史短视频音频生产流水线", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(settings_api.router)
app.include_router(voices.router)

app.mount("/media", StaticFiles(directory=str(config.DATA_DIR)), name="media")
app.mount("/", StaticFiles(directory=str(config.STATIC_DIR), html=True), name="static")
