import importlib.util as u, subprocess, os
s=u.spec_from_file_location("ve","tools/vertical_export.py"); ve=u.module_from_spec(s); s.loader.exec_module(ve)

# ── 1) comando bem formado (puro) ──
cmd = ve.build_vertical_command("in.mp4", "out.mp4", mode="blur")
j = " ".join(cmd)
assert "1080:1920" in j, "deve mirar 1080x1920"
assert "libx264" in cmd and "yuv420p" in cmd
assert "320k" in cmd and "48000" in cmd        # áudio AAC 48k 320k
assert "+faststart" in j                        # streaming-friendly
assert cmd[-1] == "out.mp4"
print("comando blur (specs de Short) OK")

cmd_crop = ve.build_vertical_command("in.mp4", "out.mp4", mode="crop")
assert "crop=1080:1920" in " ".join(cmd_crop)
print("comando crop OK")

# ── 2) execução real com ffmpeg (se disponível) ──
if ve.check_ffmpeg():
    os.makedirs("/tmp/vt", exist_ok=True)
    src = "/tmp/vt/in_16x9.mp4"
    subprocess.run(["ffmpeg","-y","-f","lavfi","-i","testsrc=duration=2:size=1280x720:rate=30",
                    "-f","lavfi","-i","sine=frequency=440:duration=2",
                    "-c:v","libx264","-c:a","aac","-shortest",src],
                   capture_output=True, timeout=60)
    r = ve.export_vertical(src, "/tmp/vt/out_9x16.mp4", mode="blur")
    assert r["ok"], r
    dims = subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
                           "-show_entries","stream=width,height","-of","csv=p=0","/tmp/vt/out_9x16.mp4"],
                          capture_output=True, text=True).stdout.strip()
    assert dims == "1080,1920", dims
    print(f"execução real: saída {dims} (1080x1920) OK ✅")
else:
    print("ffmpeg ausente — só o comando foi validado")

print("\nEXPORT 9:16 OK ✅")
