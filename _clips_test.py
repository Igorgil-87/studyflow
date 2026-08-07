import importlib.util as u
s = u.spec_from_file_location("clip_rules", "tools/clip_rules.py")
cr = u.module_from_spec(s); s.loader.exec_module(cr)

# ── 1) limites por tipo ──
assert cr.clip_bounds("shorts") == (36, 55)
assert cr.clip_bounds("cortes_medio") == (120, 300)
assert cr.clip_bounds("cortes_longo") == (300, 900)
assert cr.clip_bounds("desconhecido") == (36, 55)  # fallback shorts
print("clip_bounds OK")

# ── 2) quantidade: N exato vs faixa do tipo ──
assert cr.resolve_qty("shorts", 3) == (3, 3)        # usuário pediu 3
assert cr.resolve_qty("shorts", None) == (4, 12)    # IA decide (faixa)
assert cr.resolve_qty("cortes_longo", None) == (2, 4)
assert cr.resolve_qty("shorts", 0) == (4, 12)       # 0 → faixa
print("resolve_qty OK (N exato e faixa)")

# ── 3) máximo de cortes pela duração ──
assert cr.max_clips_for_duration(200, 30) == 6      # 200s / 30s
assert cr.max_clips_for_duration(50, 30) == 1       # vídeo curto → 1
assert cr.max_clips_for_duration(95, 30) == 3
assert cr.max_clips_for_duration(0, 30) == 1        # duração desconhecida
print("max_clips_for_duration OK")

# ── 4) densidade de fala (música) ──
assert cr.speech_wpm(600, 200) == 180.0             # fala normal
assert cr.speech_wpm(20, 200) == 6.0                # música
assert cr.speech_wpm(100, 0) == 0.0                 # duração desconhecida
assert cr.is_low_speech(6, 25) is True              # 6 wpm → pouca fala
assert cr.is_low_speech(180, 25) is False           # fala normal
assert cr.is_low_speech(0, 25) is False             # desconhecida não alerta
print("speech_wpm / is_low_speech OK")

print("\nCLIP RULES OK ✅")

# ── 5) enforce_durations: o bug do corte de 5s ──
hls = [
    {"titulo": "A", "inicio": 10, "fim": 15},    # 5s → curto, deve virar 30s
    {"titulo": "B", "inicio": 60, "fim": 95},    # 35s → ok (entre 30 e 45)
    {"titulo": "C", "inicio": 100, "fim": 200},  # 100s → longo, vira 45s
    {"titulo": "D", "inicio": 500, "fim": 540},  # início > duração (300) → descarta
]
cleaned, adj, drop = cr.enforce_durations(hls, 30, 45, total_duration=300)
by = {h["titulo"]: h for h in cleaned}
assert "D" not in by and drop == 1, (list(by), drop)
assert by["A"]["fim"] - by["A"]["inicio"] == 30, by["A"]      # 5s → 30s
assert by["B"]["fim"] - by["B"]["inicio"] == 35                # inalterado
assert by["C"]["fim"] - by["C"]["inicio"] == 45, by["C"]      # 100s → 45s
assert adj == 2, adj   # A e C ajustados; B não
print("enforce_durations OK — corte de 5s vira 30s, 100s vira 45s, inválido descartado")

# corte que estoura o fim do vídeo recua o início
c2, _, _ = cr.enforce_durations([{"titulo":"E","inicio":290,"fim":295}], 30, 45, total_duration=300)
e = c2[0]
assert e["fim"] == 300 and e["inicio"] == 270, e   # recuou para caber 30s
print("recuo de início ao bater no fim do vídeo OK")

print("\nENFORCE DURATIONS OK ✅")
