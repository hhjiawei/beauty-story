"""环境变量与全局配置。一切可调参数集中在这里。"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("HVP_DATA_DIR", str(BASE_DIR / "data")))
SKILLS_DIR = Path(os.getenv("HVP_SKILLS_DIR", str(BASE_DIR / "skills")))
STATIC_DIR = BASE_DIR / "static"

DB_PATH = DATA_DIR / "pipeline.db"
CHECKPOINT_DB_PATH = DATA_DIR / "checkpoints.db"
MEMORY_DIR = DATA_DIR / "memory"          # 人格 L2 系列记忆
REFS_DIR = DATA_DIR / "refs"              # 音色库
AGENT_WORKSPACE_DIR = DATA_DIR / "agent_workspaces"   # 各节点 deepagents 工作区（skills 挂载副本）

# TTS 后端：mock（本地演示/测试）| indextts2（真实合成）
TTS_BACKEND = os.getenv("HVP_TTS_BACKEND", "mock")
INDEXTTS2_BASE_URL = os.getenv("INDEXTTS2_BASE_URL", "http://127.0.0.1:7860")

# FFmpeg 后期链参数（语音层手册 Step 4）
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
POST_HIGHPASS_HZ = int(os.getenv("HVP_POST_HIGHPASS_HZ", "80"))
POST_EQ_CLARITY = os.getenv("HVP_POST_EQ_CLARITY", "3000:t=q:w=1:g=2")
POST_EQ_WARMTH = os.getenv("HVP_POST_EQ_WARMTH", "400:t=q:w=1:g=-2")
POST_COMPRESSOR = os.getenv("HVP_POST_COMPRESSOR", "threshold=-18dB:ratio=3:attack=10:release=100")
POST_LOUDNORM = os.getenv("HVP_POST_LOUDNORM", "I=-16:TP=-1.5:LRA=11")
CHAPTER_GAP_MS = int(os.getenv("HVP_CHAPTER_GAP_MS", "900"))   # 章间静音 800-1000ms

HOST = os.getenv("HVP_HOST", "0.0.0.0")
PORT = int(os.getenv("HVP_PORT", "8600"))


def ensure_dirs() -> None:
    for d in (DATA_DIR, MEMORY_DIR, REFS_DIR, AGENT_WORKSPACE_DIR):
        d.mkdir(parents=True, exist_ok=True)
