import os, tempfile, json
db_fd, db_path = tempfile.mkstemp(suffix=".db")
os.close(db_fd)
# diretório exclusivo e seguro (mode 0700) pros arquivos de artefato do teste
tmp_dir = tempfile.mkdtemp()
os.environ["OBS_DB"] = db_path
os.environ["CACHE_ENABLED"] = "1"
os.environ["CACHE_SEMANTIC"] = "1"
os.environ["RUN_MODE"] = "inline"

# precisa importar DEPOIS de setar env (CACHE_ENABLED é lido na import)
from obs import db as obs_db
from cache import store, llm_cache, embeddings
obs_db.init(); store.init()

# embedder FALSO determinístico (sem OpenAI): vetor por contagem de chars
import re
def fake_embed(text):
    v=[0.0]*26
    for ch in text.lower():
        if 'a'<=ch<='z': v[ord(ch)-97]+=1.0
    return v or [1.0]
embeddings.embed = fake_embed   # injeta

calls = {"n": 0}
def fake_quiz_tool(**kw):
    calls["n"] += 1
    p = os.path.join(tmp_dir, f"quiz_{calls['n']}.json")
    with open(p,"w") as f: json.dump({"tema": kw["topic"], "v": calls["n"]}, f)
    return p

print("── Teste 1: MISS grava, hit EXATO devolve do cache (custo 0, 0 nova chamada) ──")
key = "quiz|redes neurais|5|5|TRANSCRIPT GRANDE AAA"
p1 = llm_cache.smart_call("openai","quiz","gpt-4o-mini", fake_quiz_tool,
        cache_key=key, result_kind="file", file_dir=tmp_dir,
        trace_id="job1", input_text="t", topic="redes neurais")
assert calls["n"]==1, "primeira deve chamar o tool"
p2 = llm_cache.smart_call("openai","quiz","gpt-4o-mini", fake_quiz_tool,
        cache_key=key, result_kind="file", file_dir=tmp_dir,
        trace_id="job2", input_text="t", topic="redes neurais")
assert calls["n"]==1, f"segunda NAO deveria chamar o tool (cache exato), chamou {calls['n']}x"
assert json.load(open(p2))["v"]==1, "conteudo do cache deve ser o do 1o resultado"
print("   tool chamado:", calls["n"], "vez | arquivo reescrito do cache:", os.path.basename(p2))

hits = obs_db.query("SELECT COUNT(*) c FROM traces WHERE status='cache_hit'")[0]["c"]
assert hits==1, hits
print("   trace cache_hit gravado:", hits)

print("── Teste 2: acerto SEMÂNTICO (chave diferente, conteúdo ~igual) ──")
key_sim = "quiz|redes neurais|5|5|TRANSCRIPT GRANDE AAA "  # 1 espaço a mais
p3 = llm_cache.smart_call("openai","quiz","gpt-4o-mini", fake_quiz_tool,
        cache_key=key_sim, result_kind="file", file_dir=tmp_dir,
        trace_id="job3", input_text="t", topic="redes neurais")
print("   tool chamado total:", calls["n"], "(esperado 1 — pegou no semântico)")
assert calls["n"]==1, "deveria ter acertado no cache semântico"

print("── Teste 3: entrada REALMENTE diferente → MISS, chama o tool ──")
p4 = llm_cache.smart_call("openai","quiz","gpt-4o-mini", fake_quiz_tool,
        cache_key="quiz|samurais|5|5|OUTRO TRANSCRIPT ZZZ", result_kind="file",
        file_dir=tmp_dir, trace_id="job4", input_text="t", topic="samurais")
assert calls["n"]==2, f"entrada nova deve chamar o tool, n={calls['n']}"
print("   tool chamado total:", calls["n"], "(esperado 2)")

print("── Teste 4: summary mostra economia ──")
from obs import report
s = report.summary()
print("   cache:", s["cache"])
assert s["cache"]["hits"]==2 and s["cache"]["entries"]==2
assert s["cache"]["estimated_saved_usd"]>=0
print("\nCACHE SEMÂNTICO OK ✅")
