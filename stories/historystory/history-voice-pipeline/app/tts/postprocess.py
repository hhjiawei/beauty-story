"""FFmpeg 后期链与拼接（语音层手册 Step 4，执行方案 §4.9）。

- 拼接：单元按画本停顿参数 pad 静音后顺序拼接（纯 Python wave 实现，零依赖可用）
- 后期链：高通 → EQ → 压缩 → 响度标准化 -16 LUFS（有 ffmpeg 则跑，无则跳过并标记）
- 产出：成品 wav(+mp3) + 字幕时间轴 JSON（逐单元起止时间）
"""
from __future__ import annotations

import json
import shutil
import subprocess
import wave
from pathlib import Path

from .. import config


def _read_wav(path: str):
    with wave.open(path, "rb") as w:
        params = (w.getnchannels(), w.getsampwidth(), w.getframerate())
        frames = w.readframes(w.getnframes())
    return params, frames


def _silence(nch: int, width: int, rate: int, ms: int) -> bytes:
    return b"\x00" * int(rate * ms / 1000) * nch * width


def concat_units(unit_wavs: list[dict], out_wav: str) -> list[dict]:
    """按画本停顿拼接。unit_wavs: [{path, 前停顿_ms, 后停顿_ms, chapter_break}]
    返回字幕时间轴 [{unit_id, start_s, end_s, text}]。"""
    if not unit_wavs:
        raise ValueError("无单元可拼接")
    timeline, all_frames = [], bytearray()
    params0, _ = _read_wav(unit_wavs[0]["path"])
    nch, width, rate = params0
    cursor = 0.0
    for u in unit_wavs:
        gap = config.CHAPTER_GAP_MS if u.get("chapter_break") else u.get("前停顿_ms", 0)
        sil = _silence(nch, width, rate, gap)
        all_frames += sil
        cursor += len(sil) / (nch * width) / rate
        params, frames = _read_wav(u["path"])
        if params != params0:
            raise ValueError(f"采样参数不一致: {u['path']}")
        start = cursor
        all_frames += frames
        cursor += len(frames) / (nch * width) / rate
        timeline.append({
            "unit_id": u.get("unit_id", Path(u["path"]).stem),
            "text": u.get("text", ""),
            "start_s": round(start, 3),
            "end_s": round(cursor, 3),
        })
        tail = _silence(nch, width, rate, u.get("后停顿_ms", 0))
        all_frames += tail
        cursor += len(tail) / (nch * width) / rate
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(nch)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(bytes(all_frames))
    return timeline


def ffmpeg_master(in_wav: str, out_wav: str) -> dict:
    """后期链：高通 80Hz → 3kHz+2dB / 400Hz-2dB → 压缩 → -16 LUFS。无 ffmpeg 则原样拷贝。"""
    if not shutil.which(config.FFMPEG_BIN):
        shutil.copy(in_wav, out_wav)
        return {"ok": False, "detail": "ffmpeg 不可用，已跳过后期（直接拼接干音）"}
    af = (
        f"highpass=f={config.POST_HIGHPASS_HZ},"
        f"equalizer=f={config.POST_EQ_CLARITY},"
        f"equalizer=f={config.POST_EQ_WARMTH},"
        f"acompressor={config.POST_COMPRESSOR},"
        f"loudnorm={config.POST_LOUDNORM}"
    )
    cmd = [config.FFMPEG_BIN, "-y", "-i", in_wav, "-af", af, out_wav]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        shutil.copy(in_wav, out_wav)
        return {"ok": False, "detail": f"ffmpeg 失败已降级: {r.stderr[-200:]}"}
    return {"ok": True, "detail": "后期链完成（-16 LUFS / TP -1.5）"}


def to_mp3(in_wav: str, out_mp3: str) -> bool:
    if not shutil.which(config.FFMPEG_BIN):
        return False
    r = subprocess.run(
        [config.FFMPEG_BIN, "-y", "-i", in_wav, "-codec:a", "libmp3lame", "-q:a", "4", out_mp3],
        capture_output=True, text=True,
    )
    return r.returncode == 0


def wav_duration(path: str) -> float:
    with wave.open(path, "rb") as w:
        return round(w.getnframes() / w.getframerate(), 3)


def write_subtitle(timeline: list[dict], out_json: str) -> None:
    Path(out_json).write_text(json.dumps(timeline, ensure_ascii=False, indent=2), encoding="utf-8")
