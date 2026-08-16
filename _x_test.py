import importlib.util as u, json
from urllib.parse import urlparse
s=u.spec_from_file_location("x","tools/x_source.py"); X=u.module_from_spec(s); s.loader.exec_module(X)

# ── 1) build_query: bombando vs polêmica ──
qb = X.build_query("Roma antiga", mode="bombando", lang="pt", min_faves=500)
assert "Roma antiga" in qb and "min_faves:500" in qb and "lang:pt" in qb
qp = X.build_query("Roma antiga", mode="polemica", lang="pt", min_faves=200)
assert "polêmica" in qp.lower() and "min_faves:200" in qp
print("build_query (bombando + polêmica) OK")

# ── 2) parse no formato real da twitterapi.io ──
fake = {"tweets":[
  {"text":"Polêmica: descoberta muda o que sabíamos sobre Roma! https://x.co/a","url":"https://x.com/u/1",
   "likeCount":1200,"retweetCount":300,"author":{"userName":"historiador"}},
  {"text":"Thread sobre o Coliseu","url":"https://x.com/u/2","likeCount":800,"author":{"userName":"roma_fan"}},
  {"text":"oi","url":"https://x.com/u/3","likeCount":5,"author":{"userName":"x"}},  # curto → ignora
]}
r = X.parse_response(fake)
assert len(r["topics"]) == 2, r["topics"]               # ignorou "oi"
assert "http" not in r["topics"][0]                      # limpou URL
assert len(r["links"]) == 2 and r["links"][0]["source"] == "@historiador"
assert "X / Twitter" in r["context"]
print("parse_response (formato twitterapi.io) OK")

# ── 3) fetch_x com header e provider corretos ──
def fake_fetch(url, headers, timeout):
    assert "advanced_search" in url and "query=" in url and "queryType=Latest" in url
    assert headers.get("X-API-Key") == "TESTKEY"
    return fake
out = X.fetch_x("Roma", mode="bombando", provider="twitterapi", api_key="TESTKEY", fetch=fake_fetch)
assert len(out["topics"]) == 2
print("fetch_x (twitterapi.io header X-API-Key) OK")

# getxapi usa Authorization: Bearer + q/product
def fake_getx(url, headers, timeout):
    assert urlparse(url).netloc.endswith("getxapi.com") and "q=" in url and "product=Latest" in url
    assert headers.get("Authorization") == "Bearer K2"
    return fake
out2 = X.fetch_x("Roma", provider="getxapi", api_key="K2", fetch=fake_getx)
assert len(out2["topics"]) == 2
print("fetch_x (getxapi Bearer) OK")

# ── 4) sem chave → vazio (fail-open) ──
assert X.fetch_x("Roma", api_key=None)["topics"] == []
print("fail-open sem chave OK")

print("\nFONTE X (Twitter) OK ✅")
