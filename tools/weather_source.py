"""
tools/weather_source.py — clima atual via OpenWeather (endpoint clássico gratuito).

Usa /data/2.5/weather (free tier, sem cartão; a chave vai em appid=).
NÃO usa One Call 3.0/4.0 (esses viraram pagos por assinatura).

Chave grátis em openweathermap.org → conta → API keys (pode levar ~2h p/ ativar).
Env: OPENWEATHER_API_KEY, WEATHER_CITY (default São Paulo,BR).

Fail-open: sem chave ou erro de rede, retorna None e o widget mostra indisponível.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.parse
import urllib.request

API_URL = "https://api.openweathermap.org/data/2.5/weather"

# tradução simplificada dos grupos de clima -> emoji (ícone visual sem depender de CDN)
_ICON = {
    "Clear": "☀️", "Clouds": "☁️", "Rain": "🌧️", "Drizzle": "🌦️",
    "Thunderstorm": "⛈️", "Snow": "❄️", "Mist": "🌫️", "Fog": "🌫️",
    "Haze": "🌫️", "Smoke": "🌫️", "Dust": "🌫️", "Sand": "🌫️",
}


def _http_get(url: str, timeout: int):
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "StudyFlow/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        # 401 = chave nova ainda não ativa / ausente; 429 = limite
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)


def parse_weather(data: dict) -> dict | None:
    """Normaliza a resposta do OpenWeather num dicionário enxuto para o widget."""
    if not data or "main" not in data:
        return None
    try:
        main = data["main"]
        weather = (data.get("weather") or [{}])[0]
        grupo = weather.get("main", "")
        return {
            "city": data.get("name", ""),
            "temp": round(float(main.get("temp", 0))),
            "feels": round(float(main.get("feels_like", 0))),
            "tmin": round(float(main.get("temp_min", 0))),
            "tmax": round(float(main.get("temp_max", 0))),
            "humidity": int(main.get("humidity", 0)),
            "desc": (weather.get("description", "") or "").capitalize(),
            "group": grupo,
            "emoji": _ICON.get(grupo, "🌡️"),
            "wind": round(float(data.get("wind", {}).get("speed", 0)) * 3.6),  # m/s -> km/h
        }
    except (TypeError, ValueError, KeyError):
        return None


def fetch_weather(city: str | None = None, api_key: str | None = None,
                  fetch=None, timeout: int = 10) -> dict | None:
    """Clima atual de uma cidade. Retorna dict normalizado ou None (fail-open)."""
    api_key = api_key or os.getenv("OPENWEATHER_API_KEY", "")
    city = city or os.getenv("WEATHER_CITY", "São Paulo,BR")
    if not api_key:
        print("[weather] OPENWEATHER_API_KEY ausente — widget de clima desativado")
        return None
    params = urllib.parse.urlencode({
        "q": city, "appid": api_key, "units": "metric", "lang": "pt_br",
    })
    if fetch is not None:
        data, err = fetch(f"{API_URL}?{params}", timeout), None
    else:
        data, err = _http_get(f"{API_URL}?{params}", timeout)
    if err:
        print(f"[weather] falhou: {err}")
        return None
    return parse_weather(data)
