import json
import importlib.util as _u
_spec = _u.spec_from_file_location("tvf", "tools/topic_video_finder.py")
tvf = _u.module_from_spec(_spec); _spec.loader.exec_module(tvf)
find_relevant_videos, build_query = tvf.find_relevant_videos, tvf.build_query

# busca falsa: devolve mix de política + lixo fora do tema
FAKE_VIDEOS = [
    {"titulo": "Análise: reforma política no Congresso", "canal": "Política Hoje", "descricao": "debate sobre o senado", "url": "u1", "duracao_minutos": 12},
    {"titulo": "Receita de bolo de cenoura", "canal": "Cozinha Fácil", "descricao": "sobremesa", "url": "u2", "duracao_minutos": 8},
    {"titulo": "Eleições 2026: o que esperar", "canal": "Jornal X", "descricao": "cenário eleitoral", "url": "u3", "duracao_minutos": 15},
    {"titulo": "Top 10 gols da rodada", "canal": "Esporte TV", "descricao": "futebol", "url": "u4", "duracao_minutos": 6},
]
def fake_search(query, n):
    return json.dumps(FAKE_VIDEOS[:n])

# LLM falso: marca relevante só os de política (índices 0 e 2)
def fake_llm(prompt):
    assert "política" in prompt.lower(), "prompt deve conter o assunto"
    assert "Receita de bolo" in prompt, "prompt deve listar os candidatos"
    return json.dumps([
        {"i": 0, "relevante": True,  "score": 0.95, "motivo": "reforma política"},
        {"i": 1, "relevante": False, "score": 0.0,  "motivo": "culinária"},
        {"i": 2, "relevante": True,  "score": 0.88, "motivo": "eleições"},
        {"i": 3, "relevante": False, "score": 0.0,  "motivo": "esporte"},
    ])

print("── build_query ──")
assert build_query("reforma política", "política") == "reforma política"  # nicho já contido
assert build_query("reforma", "política") == "reforma política"
print("  OK")

print("── filtro de relevância descarta fora do tema ──")
r = find_relevant_videos("política", "política", fake_search, fake_llm)
titulos = [v["titulo"] for v in r["videos"]]
print("  retornados:", titulos)
assert r["filtered"] is True
assert len(r["videos"]) == 2, r["videos"]
assert all("política" in t.lower() or "elei" in t.lower() for t in titulos)
assert "Receita de bolo de cenoura" not in titulos and "Top 10 gols da rodada" not in titulos
# ordenado por relevância (0.95 antes de 0.88)
assert r["videos"][0]["relevancia"] >= r["videos"][1]["relevancia"]
print("  OK — só política, ordenado por relevância")

print("── tudo irrelevante → lista vazia com motivo ──")
def llm_all_no(prompt):
    return json.dumps([{"i": i, "relevante": False, "score": 0} for i in range(4)])
r2 = find_relevant_videos("política", "política", fake_search, llm_all_no)
assert r2["videos"] == [] and "claramente sobre" in r2["reason"]
print("  OK:", r2["reason"])

print("── fail-open: LLM falha → entrega crus (não trava o usuário) ──")
def llm_broken(prompt):
    return "isso não é json"
r3 = find_relevant_videos("política", "política", fake_search, llm_broken)
assert r3["filtered"] is False and len(r3["videos"]) == 4
print("  OK — degradou para resultados crus")

print("\nTOPIC RELEVANCE OK ✅")
