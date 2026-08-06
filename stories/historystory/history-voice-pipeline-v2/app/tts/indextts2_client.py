"""IndexTTS2 HTTP 客户端封装（适配层：参数集中一处，本地部署版本签名差异只改这里）。

执行方案 §4.8 / 语音层手册：参数名（emo_audio_prompt/emo_alpha/use_emo_text 等）
以本地部署版本 README 为准——开工先 smoke_test() 对签名，再批量。
"""
from __future__ import annotations

import httpx

from .. import config


class IndexTTS2Client:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or config.INDEXTTS2_BASE_URL).rstrip("/")

    def smoke_test(self) -> dict:
        """最小 infer 冒烟：验证服务可达与参数签名。"""
        try:
            r = httpx.get(f"{self.base_url}/", timeout=10)
            return {"ok": r.status_code < 500, "detail": f"HTTP {r.status_code}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "detail": str(e)}

    def infer(self, *, text: str, out_path: str, spk_audio: str,
              emo_audio: str | None = None, emo_text: str | None = None,
              emo_alpha: float = 0.7, speed: float = 1.0,
              duration_target_s: float | None = None) -> dict:
        """单单元合成。参数签名按本地版本 README 适配（此处为常见 HTTP 包装形态）。"""
        payload = {
            "text": text,
            "spk_audio_prompt": spk_audio,
            "emo_alpha": emo_alpha,
            "speed": speed,
        }
        if emo_audio:
            payload["emo_audio_prompt"] = emo_audio
        if emo_text:
            payload["emo_text"] = emo_text
            payload["use_emo_text"] = True
        if duration_target_s is not None:
            payload["duration_target_s"] = duration_target_s  # 精确时长模式
        r = httpx.post(f"{self.base_url}/infer", json=payload, timeout=180)
        r.raise_for_status()
        data = r.json()
        audio_url = data.get("audio_url") or data.get("output_path")
        if audio_url and str(audio_url).startswith("http"):
            with httpx.stream("GET", audio_url, timeout=120) as resp:
                resp.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in resp.iter_bytes():
                        f.write(chunk)
        elif audio_url:
            import shutil
            shutil.copy(audio_url, out_path)
        else:
            raise RuntimeError(f"IndexTTS2 返回缺少音频路径: {data}")
        return {"path": out_path, "raw": data}
