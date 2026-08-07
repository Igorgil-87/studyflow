import importlib.util as u
s=u.spec_from_file_location("w","tools/weather_source.py"); w=u.module_from_spec(s); s.loader.exec_module(w)

# resposta REAL (formato /data/2.5/weather, metric, pt_br)
fake = {
  "name":"São Paulo",
  "main":{"temp":23.4,"feels_like":24.1,"temp_min":21.0,"temp_max":25.7,"humidity":68},
  "weather":[{"main":"Clouds","description":"nuvens dispersas","icon":"03d"}],
  "wind":{"speed":3.1},
}
out = w.fetch_weather(city="São Paulo,BR", api_key="K", fetch=lambda url,t: fake)
assert out["city"]=="São Paulo" and out["temp"]==23
assert out["feels"]==24 and out["tmin"]==21 and out["tmax"]==26
assert out["humidity"]==68 and out["desc"]=="Nuvens dispersas"
assert out["emoji"]=="☁️" and out["wind"]==11   # 3.1 m/s -> ~11 km/h
print("parse do clima (temp, sensação, umidade, vento, emoji) OK:")
print(f"   {out['emoji']} {out['city']} {out['temp']}°C — {out['desc']} | sensação {out['feels']}°C | vento {out['wind']} km/h")

# fail-open: sem chave → None
assert w.fetch_weather(api_key="", city="X") is None
# fail-open: erro de rede → None
assert w.fetch_weather(api_key="K", city="X", fetch=lambda url,t: None) is None
# resposta inválida → None
assert w.parse_weather({"cod":404}) is None
print("fail-open (sem chave / rede falha / cidade inexistente) OK")
print("\nFONTE CLIMA OK ✅")
