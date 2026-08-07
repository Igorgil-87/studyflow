import importlib.util as u
def load(n,p): s=u.spec_from_file_location(n,p); m=u.module_from_spec(s); s.loader.exec_module(m); return m
px = load("perplexity_source", "tools/perplexity_source.py")
news = load("news_source", "tools/news_source.py")

# ── 1) Perplexity: parse de tópicos + citações ──
fake_px = {
  "choices": [{"message": {"content":
    "1. Eleições municipais 2026: novas pesquisas divididas\n"
    "2. Reforma tributária entra em vigor com polêmica\n"
    "- STF julga marco temporal nesta semana\n"
    "x\n"  # linha curta, deve ser ignorada
  }}],
  "citations": [
    "https://g1.globo.com/politica/noticia-x",
    {"url": "https://folha.uol.com.br/poder/y", "title": "Reforma tributária"},
  ],
}
def fake_fetch_px(url, body, headers, timeout):
    assert "perplexity.ai" in url and headers["Authorization"].startswith("Bearer ")
    return fake_px
r = px.fetch_trends("Política", api_key="TEST", fetch=fake_fetch_px)
assert len(r["topics"]) == 3, r["topics"]            # ignorou o "x" curto
assert "Eleições municipais" in r["topics"][0]
assert len(r["links"]) == 2
assert r["links"][0]["url"].startswith("https://g1")
assert r["links"][1]["title"] == "Reforma tributária"
assert "Perplexity" in r["context"]
print("Perplexity OK — 3 tópicos específicos + 2 citações")

# sem api key → vazio (fail-open)
assert px.fetch_trends("Política", api_key=None)["topics"] == []
print("Perplexity sem chave → vazio OK")

# ── 2) GNews: parse de manchetes ──
fake_gnews = {"articles": [
  {"title": "Descoberta na física quântica", "url": "https://news.com/a", "source": {"name": "Globo"}},
  {"title": "Nova missão espacial", "url": "https://news.com/b", "source": {"name": "UOL"}},
  {"title": "", "url": "https://news.com/c"},   # sem título → descartado
]}
def fake_fetch_news(url, timeout):
    assert "gnews.io" in url and "lang=pt" in url
    return fake_gnews
n = news.fetch_news("ciência", api_key="TEST", provider="gnews", fetch=fake_fetch_news)
assert len(n["headlines"]) == 2
assert n["headlines"][0]["source"] == "Globo"
assert len(n["links"]) == 2 and n["links"][0]["url"] == "https://news.com/a"
print("GNews OK — 2 manchetes com link")

# ── 3) NewsData: formato diferente ──
fake_nd = {"results": [
  {"title": "Política em alta", "link": "https://nd.com/x", "source_id": "g1"},
]}
n2 = news.fetch_news("política", api_key="T", provider="newsdata", fetch=lambda url,t: fake_nd)
assert n2["headlines"][0]["url"] == "https://nd.com/x" and n2["headlines"][0]["source"] == "g1"
print("NewsData OK (formato results/link)")

# sem chave → vazio
assert news.fetch_news("x", api_key=None)["topics"] == []
print("News sem chave → vazio OK")


# ── limpeza de lixo do Perplexity (intro, **, [n]) ──
messy = {"choices":[{"message":{"content":
  "Os assuntos em alta sao:\n- **Fusao Nuclear** avanca em 2026 [5]\n- **IA Agentica** ganha forca [7]"}}],
  "citations":["https://x.com/a"]}
rc = px.parse_response(messy)
assert len(rc["topics"]) == 2, rc["topics"]
assert not any(("**" in t) or ("[" in t) or t.lower().endswith(":") for t in rc["topics"])
print("limpeza de intro/markdown/citacoes OK")


# ── busca de polêmicas (Perplexity) ──
fake_pol = {"choices":[{"message":{"content":"- Debate quente sobre tema X [1]\n- Polemica sobre Y divide opinioes [2]"}}],"citations":["https://a.com"]}
rp = px.fetch_controversies("Historia", api_key="T", fetch=lambda u,b,h,t: fake_pol)
assert len(rp["topics"]) == 2 and "POL" in rp["context"].upper()
print("fetch_controversies (polemicas) OK")

print("\nFONTES (Perplexity + News) OK ✅")
