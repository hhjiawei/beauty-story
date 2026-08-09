# 后期链路（FFmpeg 全自动）

> 本文件为 SKILL.md 的参考文档，按需加载。包含响度标准化、EQ、压缩、混响、侧链闪避、拼接的完整参数与命令。

---

## 后期四板斧

合成干音直接放进视频会"干"且"飘"。后期四板斧，全部可脚本化：

| 工序 | 参数建议 | 作用 |
|------|----------|------|
| 响度标准化 | 整体 **-16 LUFS**（短视频平台通用），真峰值 ≤ -1 dBTP | 全系列音量统一，观众不用调音量 |
| EQ | 高通 80Hz 去轰隆；2–4kHz 提升 +2dB 增清晰度；300–500Hz 衰减 -2dB 去闷感 | 人声清晰温暖 |
| 压缩 | 阈值约 -18dB，比率 3:1 | 动态统一，忽大忽小消失 |
| 混响 | 极小剂量：room 类，mix 8%–12% | 让干音"落地"，有空间感。**宁少勿多**——多了糊台词 |

---

## FFmpeg 示意链

响度＋EQ＋压缩一条命令：

```bash
ffmpeg -i in.wav -af "highpass=f=80, equalizer=f=3000:t=q:w=1:g=2, equalizer=f=400:t=q:w=1:g=-2, acompressor=threshold=-18dB:ratio=3:attack=10:release=100, loudnorm=I=-16:TP=-1.5:LRA=11" out.wav
```

---

## BGM 侧链闪避

旁白轨与 BGM 轨做 ducking，旁白出现时 BGM 自动压 -8~-12dB。

实现方式：
- 剪映：自动闪避功能
- Final Cut Pro：侧链压缩
- FFmpeg：sidechaincompress 滤镜

---

## 拼接

单元间按画本停顿参数 pad 静音后顺序拼接，章间静音 800–1000ms。

```bash
# 示意：用 sox 或 ffmpeg concat 拼接
ffmpeg -f concat -safe 0 -i filelist.txt -c copy out.wav
```

`filelist.txt` 格式：
```
file '001_0.wav'
duration 2.5
file 'silence_400ms.wav'
duration 0.4
file '001_1.wav'
...
```
