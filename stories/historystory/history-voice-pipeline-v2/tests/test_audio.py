"""音频链路单测：mock 合成 → 拼接（含停顿/章间）→ FFmpeg 后期 → 时间轴。"""
import json
import wave

from app.tts import mock_tts, postprocess


def test_mock_synthesize(tmp_path):
    out = str(tmp_path / "u.wav")
    r = mock_tts.synthesize("鼓声响了。是进军鼓。", out)
    assert r["duration_s"] > 0.3
    with wave.open(out) as w:
        assert w.getframerate() == 22050 and w.getnframes() > 0


def test_concat_with_pauses_and_timeline(tmp_path):
    u1 = str(tmp_path / "u1.wav"); u2 = str(tmp_path / "u2.wav")
    d1 = mock_tts.synthesize("第一句。", u1)["duration_s"]
    d2 = mock_tts.synthesize("第二句。", u2)["duration_s"]
    out = str(tmp_path / "all.wav")
    timeline = postprocess.concat_units([
        {"path": u1, "unit_id": "seg001_u0", "text": "第一句。",
         "前停顿_ms": 0, "后停顿_ms": 500},
        {"path": u2, "unit_id": "seg002_u0", "text": "第二句。",
         "前停顿_ms": 0, "后停顿_ms": 0, "chapter_break": True},
    ], out)
    total = postprocess.wav_duration(out)
    # 总长 ≈ 单元1 + 停顿0.5 + 章间0.9 + 单元2
    assert total >= d1 + d2 + 1.3
    assert timeline[0]["start_s"] == 0.0
    assert abs(timeline[1]["start_s"] - (d1 + 0.5 + 0.9)) < 0.05
    assert timeline[1]["end_s"] > timeline[1]["start_s"]


def test_ffmpeg_master_and_mp3(tmp_path):
    src = str(tmp_path / "in.wav")
    mock_tts.synthesize("后期链路测试，响度标准化。", src)
    out = str(tmp_path / "out.wav")
    r = postprocess.ffmpeg_master(src, out)
    assert r["ok"], r["detail"]  # 沙箱有 ffmpeg
    assert postprocess.wav_duration(out) > 0.2
    mp3 = str(tmp_path / "out.mp3")
    assert postprocess.to_mp3(out, mp3)


def test_subtitle_written(tmp_path):
    p = str(tmp_path / "sub.json")
    postprocess.write_subtitle([{"unit_id": "a", "start_s": 0, "end_s": 1, "text": "x"}], p)
    assert json.loads(open(p, encoding="utf-8").read())[0]["unit_id"] == "a"
