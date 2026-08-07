import importlib.util as u, json
s=u.spec_from_file_location("ppf","tools/people_podcast_finder.py"); ppf=u.module_from_spec(s); s.loader.exec_module(ppf)

# ── 1) queries com viés de podcast ──
q = ppf.build_queries("Leandro Karnal", "Roma antiga", prefer_podcast=True)
assert "Leandro Karnal podcast" in q and "Leandro Karnal entrevista" in q
assert "Leandro Karnal Roma antiga" in q and "Leandro Karnal" in q
print("build_queries (pessoa + podcast + assunto) OK:", len(q), "queries")
# sem podcast
q2 = ppf.build_queries("Fulano", "", prefer_podcast=False)
assert q2 == ["Fulano"]
# só assunto
q3 = ppf.build_queries("", "vikings", prefer_podcast=True)
assert "vikings podcast" in q3
print("build_queries (variações) OK")

# ── 2) detecção de formato podcast ──
assert ppf.is_podcast_like("Flow Podcast #123 com Fulano")
assert ppf.is_podcast_like("Entrevista exclusiva com historiador")
assert not ppf.is_podcast_like("Como fazer pão caseiro")
print("is_podcast_like OK")

# ── 3) match de pessoa (título ou canal) ──
assert ppf.person_match({"titulo":"Leandro Karnal fala sobre Roma","canal":"X"}, "Leandro Karnal")
assert ppf.person_match({"titulo":"Roma antiga","canal":"Canal do Leandro Karnal"}, "Leandro Karnal")
assert ppf.person_match({"titulo":"Karnal e a história de Roma","canal":"Y"}, "Leandro Karnal")  # primeiro+último
assert not ppf.person_match({"titulo":"Receita de bolo","canal":"Z"}, "Leandro Karnal")
print("person_match OK")

# ── 4) pontuação: podcast + pessoa + duração longa ganham ──
v_bom = {"titulo":"Leandro Karnal | Inteligência Ltda Podcast","canal":"Inteligencia","duracao_minutos":120}
v_meh = {"titulo":"Resumo rápido de Roma","canal":"X","duracao_minutos":3}
assert ppf.score_video(v_bom, "Leandro Karnal", True) > ppf.score_video(v_meh, "Leandro Karnal", True)
print("score_video prioriza podcast+pessoa+longo OK")

# ── 5) find ranqueia e devolve relevancia/motivo ──
catalog = {
  "Leandro Karnal podcast": [
    {"titulo":"Leandro Karnal | Flow Podcast #500","url":"u1","canal":"Flow","duracao_minutos":150},
    {"titulo":"Clipe curto Karnal","url":"u2","canal":"X","duracao_minutos":2},
  ],
  "Leandro Karnal entrevista": [
    {"titulo":"Entrevista com Leandro Karnal","url":"u3","canal":"TV","duracao_minutos":40},
    {"titulo":"Leandro Karnal | Flow Podcast #500","url":"u1","canal":"Flow","duracao_minutos":150},  # dup
  ],
  "Leandro Karnal": [{"titulo":"Bolo de fubá","url":"u4","canal":"Receitas","duracao_minutos":5}],
}
def fake_search(q, n): return json.dumps(catalog.get(q, []))
r = ppf.find_people_videos("Leandro Karnal", "", fake_search, prefer_podcast=True, max_results=5)
urls = [v["url"] for v in r["videos"]]
assert "u1" in urls and urls.count("u1") == 1   # dedup
assert urls[0] == "u1"                          # melhor = podcast longo com a pessoa
assert "u4" == urls[-1]                         # bolo de fubá no fim
assert all("relevancia" in v and "motivo" in v for v in r["videos"])
print("find_people_videos ranqueia + dedup + motivo OK")
print("  ranking:", urls)

print("\nBUSCADOR PESSOA/PODCAST OK ✅")
