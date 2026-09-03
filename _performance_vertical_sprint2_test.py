"""Regression — Performance Sprint 2 vertical."""
import importlib.util
import os
import subprocess
import tempfile
from pathlib import Path


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

ve = load("tools/vertical_export.py", "ve_s2")
vc = load("tools/video_concat.py", "vc_s2")

cmd = ve.build_vertical_command("in.mp4", "out.mp4", mode="blur", fast_blur=True)
joined = " ".join(cmd)
assert "scale=270:480" in joined, joined
assert "scale=1080:-2" in joined, joined
assert "1080:1920" in joined
assert "libx264" in cmd and "fast" in cmd
print("fast blur filter OK")

if ve.check_ffmpeg() and vc.check_ffmpeg():
    with tempfile.TemporaryDirectory(prefix="sf-v45-") as td:
        td = Path(td)
        main = td / "main.mp4"
        outro = td / "outro.mp4"
        final = td / "final.mp4"
        # Short sintético já com specs do vertical.
        subprocess.run([
            "ffmpeg","-y","-f","lavfi","-i","testsrc=duration=2:size=1080x1920:rate=30",
            "-f","lavfi","-i","sine=frequency=440:duration=2:sample_rate=48000",
            "-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p",
            "-c:a","aac","-ar","48000","-ac","2","-shortest",str(main)
        ], capture_output=True, timeout=90, check=True)
        subprocess.run([
            "ffmpeg","-y","-f","lavfi","-i","color=c=black:duration=0.7:size=640x360:rate=30",
            "-f","lavfi","-i","sine=frequency=880:duration=0.7:sample_rate=48000",
            "-c:v","libx264","-preset","ultrafast","-pix_fmt","yuv420p",
            "-c:a","aac","-ar","48000","-ac","2","-shortest",str(outro)
        ], capture_output=True, timeout=90, check=True)
        os.environ["OUTRO_CACHE_DIR"] = str(td / "cache")
        os.environ["OUTRO_FAST_CONCAT"] = "1"
        r = vc.append_outro(str(main), str(outro), str(final), timeout=120)
        assert r["ok"], r
        assert r.get("mode") == "stream_copy", r
        assert final.exists() and final.stat().st_size > 1024
        info = vc.probe_video(str(final))
        assert (info["width"], info["height"]) == (1080, 1920), info
        assert info["duration"] > 2.4, info
        print("fast outro stream-copy real OK")
else:
    print("ffmpeg ausente: execução real pulada")

src = Path("pipelines.py").read_text(encoding="utf-8")
for stage in ("vertical_subtitles", "vertical_encode", "vertical_outro"):
    assert f'"{stage}"' in src, stage
print("deep profiling stages OK")
print("PERFORMANCE VERTICAL SPRINT 2 OK ✅")
