"""TTS 引擎路由：按配置选择 IndexTTS2 或 Mock。

单单元失败重试 3 次（执行方案 §4.8）；地图留白对轴段走精确时长模式。
"""
from __future__ import annotations

import time

from .. import config
from . import mock_tts
from .indextts2_client import IndexTTS2Client


def synthesize_unit(*, text: str, out_path: str, emotion: str = "",
                    emo_alpha: float = 0.7, speed: float = 1.0,
                    duration_target_s: float | None = None,
                    spk_audio: str | None = None,
                    max_retry: int = 3) -> dict:
    last_err = None
    for attempt in range(1, max_retry + 1):
        try:
            if config.TTS_BACKEND == "indextts2":
                client = IndexTTS2Client()
                return client.infer(
                    text=text, out_path=out_path,
                    spk_audio=spk_audio or "refs/narrator.wav",
                    emo_text=emotion or None, emo_alpha=emo_alpha,
                    speed=speed, duration_target_s=duration_target_s,
                )
            return mock_tts.synthesize(text, out_path, speed=speed)
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(0.5 * attempt)
    raise RuntimeError(f"单元合成失败（重试 {max_retry} 次）: {last_err}")
