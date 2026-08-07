import importlib.util as u, os, tempfile
from PIL import Image
import numpy as np
# carrega thumbnail.py direto (evita tools/__init__ → yt_dlp)
s = u.spec_from_file_location("thumb", "tools/thumbnail.py")
tn = u.module_from_spec(s); s.loader.exec_module(tn)

# frame sintético (gradiente colorido) como se viesse do vídeo
arr = np.zeros((720, 1280, 3), dtype="uint8")
for y in range(720):
    arr[y, :, 0] = int(255 * y / 720)
    arr[y, :, 1] = 80
    arr[y, :, 2] = 200 - int(150 * y / 720)
frame = Image.fromarray(arr)

# ── 1) compose landscape 1280x720 ──
thumb = tn.compose_thumbnail(frame, "Você não vai acreditar nisso", (1280, 720))
assert thumb.size == (1280, 720)
assert thumb.mode == "RGB"
print("compose landscape 1280x720 OK")

# ── 2) compose vertical (shorts) 1080x1920 ──
thumb_v = tn.compose_thumbnail(frame, "Top 5 curiosidades sobre física quântica que mudam tudo", (1080, 1920))
assert thumb_v.size == (1080, 1920)
print("compose vertical 1080x1920 OK (texto longo quebrado em linhas)")

# ── 3) salva em disco e confere arquivo não-vazio ──
out = tempfile.mktemp(suffix=".jpg")
thumb.convert("RGB").save(out, "JPEG", quality=88)
assert os.path.getsize(out) > 5000, os.path.getsize(out)
print(f"thumbnail salva OK ({os.path.getsize(out)//1024} KB)")
os.unlink(out)

# ── 4) título vazio não quebra ──
t2 = tn.compose_thumbnail(frame, "", (1280, 720))
assert t2.size == (1280, 720)
print("título vazio OK (sem texto)")

# ── 5) fonte carregou (bundled Anton) ──
f = tn._load_font(80)
assert f is not None
print("fonte carregada OK")

# ── 6) wrap quebra texto longo em múltiplas linhas ──
from PIL import ImageDraw
d = ImageDraw.Draw(Image.new("RGB",(1280,720)))
lines = tn._wrap(d, "ESSA É UMA FRASE BEM LONGA QUE PRECISA QUEBRAR EM VÁRIAS LINHAS PARA CABER", tn._load_font(120), 1100)
assert len(lines) >= 2
print(f"wrap OK — {len(lines)} linhas")

print("\nTHUMBNAIL OK ✅")
