import importlib.util as u
s=u.spec_from_file_location("hn","tools/hackernews_source.py"); hn=u.module_from_spec(s); s.loader.exec_module(hn)

# simula a API: lista de IDs + itens
items = {
  "https://hacker-news.firebaseio.com/v0/topstories.json": [101,102,103,104],
  "https://hacker-news.firebaseio.com/v0/item/101.json": {"id":101,"type":"story","title":"SQLite is not a toy database","url":"https://antonz.org/sqlite/","score":842,"descendants":210,"by":"antonz"},
  "https://hacker-news.firebaseio.com/v0/item/102.json": {"id":102,"type":"job","title":"We are hiring"},  # job -> descartado
  "https://hacker-news.firebaseio.com/v0/item/103.json": {"id":103,"type":"story","title":"Show HN: my project","url":"","score":120,"descendants":45,"by":"dev"},
  "https://hacker-news.firebaseio.com/v0/item/104.json": {"id":104,"type":"story","title":"Rust 2.0 released","url":"https://www.rust-lang.org/news","score":560,"descendants":98,"by":"team"},
}
def fk(url,t): return items.get(url)

out = hn.fetch_top(limit=3, fetch=fk)
assert len(out)==3, f"esperava 3, veio {len(out)}"
assert out[0]["title"]=="SQLite is not a toy database" and out[0]["score"]==842 and out[0]["comments"]==210
assert out[0]["domain"]=="antonz.org"
# história sem url -> link aponta para o thread do HN
assert out[1]["url"].startswith("https://news.ycombinator.com/item?id=103")
# www. removido do domínio
assert out[2]["domain"]=="rust-lang.org"
print("parse de top stories (score, comentários, domínio, fallback de url) OK:")
for s in out: print(f"   ▲{s['score']} 💬{s['comments']} {s['title'][:45]} ({s['domain']})")

# job foi descartado (só stories)
assert all("hiring" not in s["title"] for s in out)
print("filtro de tipo (descarta job/comment) OK")

# fail-open: lista vazia -> []
hn._cache["data"]=[]; hn._cache["ts"]=0
assert hn.fetch_top(fetch=lambda u,t: None)==[]
print("fail-open (rede falha → vazio) OK")
print("\nFONTE HACKER NEWS OK ✅")
