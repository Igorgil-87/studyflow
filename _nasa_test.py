import importlib.util as u
s=u.spec_from_file_location("nasa","tools/nasa_source.py"); nasa=u.module_from_spec(s); s.loader.exec_module(nasa)

# resposta REAL de imagem
img = {"date":"2026-06-30","title":"Spiral Galaxy NGC 1512","media_type":"image",
  "explanation":"Featured in this Hubble image is an inner ring surrounding the nucleus of the spiral galaxy.",
  "url":"https://apod.nasa.gov/apod/image/2606/NGC1512_960.jpg",
  "hdurl":"https://apod.nasa.gov/apod/image/2606/NGC1512_big.jpg","copyright":"Hubble"}
out = nasa.fetch_apod(fetch=lambda url,t: img)
assert out["title"]=="Spiral Galaxy NGC 1512" and out["media_type"]=="image"
assert out["image"].endswith("960.jpg") and out["hdurl"].endswith("big.jpg")
assert out["copyright"]=="Hubble" and out["date"]=="2026-06-30"
print("parse de imagem (título, url, hd, copyright) OK:")
print(f"   🌌 {out['title']} ({out['date']}) © {out['copyright']}")

# resposta de VÍDEO (usa thumbnail)
vid = {"date":"2026-06-29","title":"A Meteor Shower Time-lapse","media_type":"video",
  "explanation":"Watch this beautiful time-lapse.","url":"https://youtube.com/embed/xyz",
  "thumbnail_url":"https://img.youtube.com/vi/xyz/0.jpg"}
ov = nasa.fetch_apod(fetch=lambda url,t: vid)
assert ov["media_type"]=="video" and ov["image"]=="https://img.youtube.com/vi/xyz/0.jpg"
print("parse de vídeo (usa thumbnail) OK")

# explanation truncada em 300
assert len(out["explanation"]) <= 300
# fail-open
nasa._cache["data"]=None; nasa._cache["ts"]=0
assert nasa.fetch_apod(fetch=lambda url,t: None) is None
print("fail-open (rede falha → None) OK")
print("\nFONTE NASA APOD OK ✅")
