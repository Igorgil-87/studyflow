import importlib.util as u, json
s=u.spec_from_file_location("eco","tools/economy_source.py"); eco=u.module_from_spec(s); s.loader.exec_module(eco)

# resposta no formato REAL da AwesomeAPI
fake = {
  "USDBRL":{"code":"USD","codein":"BRL","name":"Dólar","bid":"5.7276","pctChange":"-0.09"},
  "EURBRL":{"code":"EUR","codein":"BRL","name":"Euro","bid":"6.8195","pctChange":"0.21"},
  "BTCBRL":{"code":"BTC","codein":"BRL","name":"Bitcoin","bid":"359973.9","pctChange":"4.98"},
}
def fake_fetch(url, timeout):
    assert "economia.awesomeapi.com.br/last/" in url and "USD-BRL" in url
    return fake

q = eco.fetch_quotes(pairs=[("USD-BRL","Dólar"),("EUR-BRL","Euro"),("BTC-BRL","Bitcoin")], fetch=fake_fetch)
assert len(q) == 3
usd, eur, btc = q
assert usd["dir"] == "down" and eur["dir"] == "up" and btc["dir"] == "up"
assert abs(usd["value"] - 5.7276) < 1e-6
print("fetch_quotes + direção (alta/baixa) OK")

# formatação BR
assert eco.format_quote(usd) == "Dólar R$ 5,73 ▼ 0,09%", eco.format_quote(usd)
assert eco.format_quote(eur).startswith("Euro R$ 6,82 ▲")
assert "Bitcoin R$ 359.974" in eco.format_quote(btc) and "▲" in eco.format_quote(btc)
print("format_quote (R$, vírgula, setas) OK:")
for it in q: print("   ", eco.format_quote(it))

# fail-open: sem dados → lista vazia
assert eco.fetch_quotes(fetch=lambda url,t: None) == []
print("fail-open (rede falha → vazio) OK")

print("\nFONTE ECONOMIA OK ✅")

# ── ações B3 (estilo CNN) ──
fake_stocks = {"results":[
  {"symbol":"PETR4","regularMarketPrice":38.06,"regularMarketChangePercent":-0.99},
  {"symbol":"ITUB4","regularMarketPrice":42.24,"regularMarketChangePercent":1.68},
]}
st = eco.fetch_stocks(token="T", fetch=lambda url,t: fake_stocks)
assert len(st)==2 and st[0]["is_stock"] and st[0]["dir"]=="down"
assert eco.format_quote(st[0]) == "PETR4 38,06 ▼ 0,99%", eco.format_quote(st[0])
assert eco.fetch_stocks(token="T", fetch=lambda url,t: None) == []   # fail-open
assert eco.fetch_stocks() == []   # sem token → vazio (sem 401)
print("fetch_stocks (ações B3 estilo CNN) OK")
