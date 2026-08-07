import os, tempfile
os.environ["YOUTUBE_PRIVACY"] = "private"
from publish import youtube_uploader as up

# ── 1) build_metadata: título truncado, #Shorts, tags limpas, privacidade ──
meta = up.build_metadata(
    title="X"*150,
    hook="Esse corte vai te surpreender",
    hashtags=["#viral", "motivacao", "#FOCO,bla"],
    privacy="public", is_short=True,
)
assert len(meta["snippet"]["title"]) == 100, "título deve truncar em 100"
assert "#Shorts" in meta["snippet"]["description"]
assert "Esse corte vai te surpreender" in meta["snippet"]["description"]
assert meta["snippet"]["tags"] == ["viral", "motivacao", "FOCO bla"], meta["snippet"]["tags"]
assert meta["status"]["privacyStatus"] == "public"
assert meta["status"]["selfDeclaredMadeForKids"] is False
print("build_metadata OK:", meta["snippet"]["tags"], "| priv:", meta["status"]["privacyStatus"])

# privacidade inválida cai para private (seguro)
m2 = up.build_metadata("t", privacy="banana")
assert m2["status"]["privacyStatus"] == "private"
print("privacidade inválida → private OK")

# ── 2) upload_video com serviço FALSO (sem rede/credencial) ──
class FakeReq:
    def next_chunk(self):
        return (None, {"id": "VID12345"})
class FakeVideos:
    def insert(self, part, body, media_body):
        FakeVideos.captured = body
        return FakeReq()
class FakeService:
    def videos(self): return FakeVideos()

# precisa de um arquivo real no disco (a função valida isfile)
tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
tmp.write(b"fake video bytes"); tmp.close()

res = up.upload_video(tmp.name, title="Meu corte", hook="hook",
                      hashtags=["viral"], privacy="unlisted",
                      _service=FakeService(), _media=object())
assert res["video_id"] == "VID12345"
assert res["url"] == "https://youtu.be/VID12345"
assert res["privacy"] == "unlisted"
assert FakeVideos.captured["snippet"]["title"] == "Meu corte"
print("upload_video (serviço falso) OK:", res)

# ── 3) arquivo inexistente levanta erro claro ──
try:
    up.upload_video("/nao/existe.mp4", title="x", _service=FakeService(), _media=object())
    assert False
except FileNotFoundError:
    print("arquivo inexistente → FileNotFoundError OK")

os.unlink(tmp.name)
print("\nPUBLISH OK ✅")
