"""Mock TTS：零依赖正弦音合成器。

演示与测试用——按文本哈希定音高、按字数定时长，生成可试听、可验证的 wav。
（执行方案 §5.2 降级通道思想的零依赖实现：IndexTTS2 不可用时保证流水线可全链路跑通。）
"""
from __future__ import annotations

import math
import struct
import wave

SAMPLE_RATE = 22050


def synthesize(text: str, out_path: str, speed: float = 1.0) -> dict:
    """把文本『读』成一段音调序列：每个字一拍，音高随字变化，听得出节奏。"""
    chars = [c for c in text if not c.isspace()]
    beat = max(0.055 / max(speed, 0.5), 0.03)
    frames = bytearray()
    for i, ch in enumerate(chars):
        freq = 180 + (ord(ch) % 240)
        n = int(SAMPLE_RATE * beat)
        # 标点处给一个更长的音（模拟停顿感）
        if ch in "。！？；":
            n = int(n * 1.4)
        for j in range(n):
            env = 1.0 - j / n  # 衰减包络，出「字」的颗粒感
            v = int(9000 * env * math.sin(2 * math.pi * freq * j / SAMPLE_RATE))
            frames += struct.pack("<h", v)
        frames += b"\x00\x00" * int(SAMPLE_RATE * 0.012)  # 字间小气口
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(bytes(frames))
    duration = len(frames) / 2 / SAMPLE_RATE
    return {"path": out_path, "duration_s": round(duration, 3)}
