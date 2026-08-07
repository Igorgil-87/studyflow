import importlib.util as u
def load(name, path):
    s = u.spec_from_file_location(name, path); m = u.module_from_spec(s); s.loader.exec_module(m); return m

chunker = load("rag.chunker", "rag/chunker.py")
# store.py faz "from . import config" → precisa do pacote; carrego via import normal
import sys, types
# stub do pacote rag mínimo para imports relativos
pkg = types.ModuleType("rag"); pkg.__path__ = ["rag"]; sys.modules["rag"] = pkg
cfg = load("rag.config", "rag/config.py"); sys.modules["rag.config"] = cfg
sys.modules["rag.chunker"] = chunker
store_mod = load("rag.store", "rag/store.py"); sys.modules["rag.store"] = store_mod
index_mod = load("rag.index", "rag/index.py")
query_mod = load("rag.query", "rag/query.py")

InMemoryStore = store_mod.InMemoryStore

# ── 1) chunker agrupa por teto de chars/segundos preservando timestamps ──
segs = [{"start": i*3, "end": i*3+3, "text": f"frase {i} " * 5} for i in range(20)]
chunks = chunker.chunk_segments(segs, max_chars=120, max_seconds=60)
assert len(chunks) > 1
assert chunks[0]["start"] == 0
assert all(c["text"] for c in chunks)
print(f"chunker OK — {len(segs)} segmentos → {len(chunks)} chunks")

# ── 2) embed falso: vetor por presença de palavras-chave (juros/fila/gato) ──
VOCAB = ["juros", "fila", "gato"]
def fake_embed(text):
    t = (text or "").lower()
    v = [float(t.count(w)) for w in VOCAB]
    return v if any(v) else [0.01, 0.01, 0.01]

# ── 3) indexar e buscar ──
store = InMemoryStore()
doc_segs = [
    {"start": 0,  "end": 10, "text": "hoje vamos falar sobre juros compostos e juros simples"},
    {"start": 10, "end": 20, "text": "a fila de processamento usa um worker dedicado"},
    {"start": 20, "end": 30, "text": "meu gato dorme o dia todo no sofá"},
]
n = index_mod.index_transcript("vid1", doc_segs, fake_embed, store, max_chars=40, max_seconds=999)
assert n == store.count() and n >= 2, (n, store.count())
print(f"index_transcript OK — {n} trechos na base")

hits = query_mod.search("o que ele falou sobre juros?", fake_embed, store, top_k=1)
assert hits and "juros" in hits[0]["text"], hits
print("busca por similaridade OK — recuperou o trecho de JUROS:", f'{hits[0]["start"]:.0f}s')

# filtro por vídeo
assert query_mod.search("juros", fake_embed, store, video_id="inexistente") == []
print("filtro por video_id OK")

# ── 4) resposta ancorada (RAG) com LLM falso que cita o contexto ──
def fake_llm(prompt):
    assert "CONTEXTO" in prompt and "juros" in prompt.lower()
    return "O vídeo fala de juros compostos e simples [0s]."
ans = query_mod.answer("o que sabe sobre juros?", fake_embed, store, fake_llm, top_k=2)
assert "juros" in ans["answer"].lower()
assert ans["sources"] and "start" in ans["sources"][0]
print("answer (RAG) OK — resposta + fontes com timestamp")

# ── 5) fail-open: store None não quebra ──
assert index_mod.index_transcript("v", doc_segs, fake_embed, None) == 0
assert query_mod.search("x", fake_embed, None) == []
assert query_mod.answer("x", fake_embed, None, fake_llm)["sources"] == []
print("fail-open (sem base) OK")

print("\nRAG OK ✅")
