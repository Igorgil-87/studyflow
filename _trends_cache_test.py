import os, tempfile, time
os.environ["TTL_CACHE_DB"] = tempfile.mktemp(suffix=".db")
from cache import ttl_cache

# ── 1) set/get dentro do TTL ──
payload = {"categories": {"ciencia": [{"titulo": "X"}]}, "summary": "resumo"}
ttl_cache.set("trends|ciencia", payload, ttl_seconds=3600)
got = ttl_cache.get("trends|ciencia")
assert got == payload, got
assert ttl_cache.ttl_left("trends|ciencia") > 3500
print("TTL set/get dentro da janela OK")

# ── 2) chave ausente ──
assert ttl_cache.get("nao_existe") is None
print("chave ausente → None OK")

# ── 3) expiração ──
ttl_cache.set("expira", {"a": 1}, ttl_seconds=-1)   # já expirado
assert ttl_cache.get("expira") is None
assert ttl_cache.ttl_left("expira") == 0
print("expiração OK")

# ── 4) índice de trends no pgvector (store em memória) ──
import importlib.util as u, sys, types
pkg = types.ModuleType("rag"); pkg.__path__ = ["rag"]; sys.modules["rag"] = pkg
def load(n,p): s=u.spec_from_file_location(n,p); m=u.module_from_spec(s); s.loader.exec_module(m); return m
cfg = load("rag.config","rag/config.py"); sys.modules["rag.config"]=cfg
load("rag.chunker","rag/chunker.py")
store_mod = load("rag.store","rag/store.py"); sys.modules["rag.store"]=store_mod
index_mod = load("rag.index","rag/index.py")

store = store_mod.InMemoryStore()
def fake_embed(t):
    tl=(t or "").lower()
    return [float(tl.count("fisica")), float(tl.count("respira")), 0.01]
all_results = {
  "ciencia": [
    {"titulo":"Físicos criam algo do nada","insight":"marco da fisica","angulo":"discutir implicacoes","hashtags":["fisica","inovacao"]},
    {"titulo":"Respiração lenta e cérebro","insight":"neurociencia respira","angulo":"tecnicas","hashtags":["respiracao"]},
  ]
}
n = index_mod.index_trends(all_results, fake_embed, store)
assert n == 2 and store.count() == 2, (n, store.count())
# busca por "fisica" recupera o trend de física
hits = store.search([1.0,0.0,0.0], top_k=1)
assert "Físicos" in hits[0]["text"], hits
assert hits[0]["video_id"] == "trend:ciencia"
print("index_trends + busca OK — recuperou o trend de física")

assert index_mod.index_trends({}, fake_embed, store) == 0   # vazio
assert index_mod.index_trends(all_results, fake_embed, None) == 0  # fail-open
print("index_trends fail-open OK")

print("\nTRENDS CACHE + INDEX OK ✅")
