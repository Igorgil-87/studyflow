import importlib.util as u
s=u.spec_from_file_location("gh","tools/github_source.py"); gh=u.module_from_spec(s); s.loader.exec_module(gh)

# resposta REAL (formato /search/repositories)
fake = {"total_count":2,"items":[
  {"full_name":"openai/openclaw","description":"Fastest growing OSS project of 2026","stargazers_count":62000,"language":"TypeScript","html_url":"https://github.com/openai/openclaw","owner":{"avatar_url":"https://x/y.png"}},
  {"full_name":"ollama/ollama","description":"Run LLMs locally","stargazers_count":48000,"language":"Go","html_url":"https://github.com/ollama/ollama","owner":{"avatar_url":""}},
]}
repos = gh.fetch_trending(limit=6, fetch=lambda url,t: fake)
assert len(repos)==2
assert repos[0]["name"]=="openai/openclaw" and repos[0]["stars"]==62000 and repos[0]["lang"]=="TypeScript"
assert repos[1]["name"]=="ollama/ollama" and repos[1]["lang"]=="Go"
print("parse de repos em alta OK:")
for r in repos: print(f"   ⭐ {r['stars']:,} {r['name']} ({r['lang']}) — {r['desc'][:40]}")

# a query usa created:> e sort=stars
captured = {}
def cap(url,t): captured['url']=url; return fake
gh.fetch_trending(days=7, fetch=cap)
assert "created" in captured["url"] and "sort=stars" in captured["url"] and "order=desc" in captured["url"]
print("query (created:>data, sort=stars, order=desc) OK")

# fail-open: erro de rede → lista vazia (sem cache ainda)
gh._cache["data"]=[]; gh._cache["ts"]=0
assert gh.fetch_trending(fetch=lambda url,t: None) == []
print("fail-open (rede falha → vazio) OK")

print("\nFONTE GITHUB OK ✅")
