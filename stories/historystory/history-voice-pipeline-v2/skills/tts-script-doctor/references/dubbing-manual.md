# 画本加工手册

> 本文件为 SKILL.md 的参考文档，按需加载。包含画本 JSON Schema、加工规则、合成脚本示例。

---

## 画本 JSON Schema

```json
{
  "段号": 5,
  "对应成稿段": "【段5·高潮】",
  "文本": "鼓声响了。是进军鼓。三万人，冲向四十万。",
  "拆分": ["鼓声响了。", "是进军鼓。", "三万人，冲向四十万。"],
  "情感": "压低后的爆发，克制中带狠劲",
  "情感强度": 0.8,
  "语速": 1.0,
  "前停顿_ms": 400,
  "后停顿_ms": 600,
  "读音表": {"亳": "bó", "妺喜": "mò xǐ"},
  "时长目标_s": null,
  "备注": "短句鼓点段，语速参数不动，靠文本本身的短句出节奏"
}
```

---

## 加工规则

| 规则 | 做法 | 依据 |
|------|------|------|
| **拆分** | 按语义拆成 1–3 句的合成单元，每单元 ≤80 字；长句在主语后、从句前主动加逗号断句 | 长文本韵律坍塌 |
| **停顿翻译** | 成稿（顿）→ 前/后停顿参数；炸点后 400–600ms，动情点后 600–800ms，章间 800–1000ms | 停顿是武器（写作层纪律的声音层落实） |
| **读音表** | 全稿扫多音字／生僻字／专名，逐集累积进**系列读音词典**（越做越省力）；数字、年代统一转成口语读法（"公元前1600年"→"公元前一千六百年"） | 读错是硬伤 |
| **情感标注** | **直接抄大纲的"情绪坐标"字段翻译**：高位起跳→明亮有力；回落蓄力→平稳放缓；爬升→渐强；峰顶→该段的炸点类型决定（燃点→有力，唏嘘→压低）；谷底→低沉克制 | 大纲层情绪波形是白捡的情感图纸 |
| **语速** | 全片基准 1.0；蓄力段 0.95，高潮段 1.0–1.05。**语速调整幅度不超过 ±10%**——节奏感靠文本短句和停顿出，不靠参数硬拉 | 参数拉节奏会出机械感 |
| **古文引文** | 【上屏】引文同时需要朗读的，单独拆成一个合成单元，情感标"换声线感"（稍慢、稍重），与正文旁白形成听觉区隔 | 引文是炸点，不能和正文一个声 |

---

## 合成脚本示例

```python
from indextts.infer_v2 import IndexTTS2
import json, os

# 示意：参数名以本地 README 为准
tts = IndexTTS2(cfg_path="checkpoints/config.yaml", model_dir="checkpoints")

# 情感参考音频库
EMO_REFS = {
    "平静": "refs/calm.wav",
    "燃": "refs/fire.wav",
    "唏嘘": "refs/sigh.wav",
    "讽刺": "refs/irony.wav",
    "惊讶": "refs/surprise.wav",
    "温情": "refs/warm.wav"
}

with open("画本.json", encoding="utf-8") as f:
    pages = json.load(f)

for p in pages:
    for i, unit in enumerate(p["拆分"]):
        tts.infer(
            spk_audio_prompt="refs/narrator.wav",          # 专属音色
            emo_audio_prompt=EMO_REFS[p["情感基调"]],      # 情感参考
            emo_alpha=p["情感强度"],
            text=unit,
            output_path=f"out/{p['段号']:03d}_{i}.wav",
            interval_silence=p["后停顿_ms"],
        )
```

> 注意：具体参数名（emo_audio_prompt、emo_alpha、emo_vector、use_emo_text 等）以本地部署版本为准。
