import importlib.util as u
s=u.spec_from_file_location("cr","tools/clip_rules.py"); cr=u.module_from_spec(s); s.loader.exec_module(cr)

# ── 1) presets de duração específicos ──
assert cr.clip_bounds("shorts_30") == (22, 38)
assert cr.clip_bounds("shorts_45") == (36, 55)
assert cr.clip_bounds("shorts_90") == (75, 105)
assert cr.clip_bounds("corte_120") == (95, 150)
assert cr.clip_bounds("corte_300") == (250, 360)
assert cr.clip_bounds("corte_600") == (520, 700)
assert cr.clip_bounds("corte_900") == (780, 1020)
print("presets de duração (30/45/1:30 e 2/5/10/15min) OK")

# ── 2) compat com tipos antigos ──
assert cr.clip_bounds("shorts")[0] > 0 and cr.clip_bounds("cortes_medio")[0] == 120
print("compat tipos antigos OK")

# ── 3) limite de 15 cortes ──
assert cr.MAX_CLIPS == 15
assert cr.resolve_qty("shorts_30", 30) == (15, 15)   # pediu 30 → corta em 15
assert cr.resolve_qty("shorts_30", 10) == (10, 10)   # pediu 10 → respeita
assert cr.resolve_qty("corte_900", None) == (1, 4)   # sem pedido → faixa do preset
print("limite MAX_CLIPS=15 + respeita pedido OK")

# ── 4) consistência: vídeo curto x podcast longo ──
# vídeo curto (90s) com shorts de 30s → cabem ~3
assert cr.max_clips_for_duration(90, 22) == 4
# podcast longo (1h = 3600s) com corte de 2min (95s min) → muitos, mas teto 15
cabem = cr.max_clips_for_duration(3600, 95)
assert cabem > 15  # cabem mais, mas o MAX_CLIPS limita na prática
assert min(cabem, cr.MAX_CLIPS) == 15
print("vídeo curto avisa poucos / podcast permite até 15 OK")

print("\nPRESETS + LIMITE OK ✅")

# ── cobertura de transcrição (corrige cortes só do começo) ──
short = [{"start": i*5, "text": "fala "+str(i)} for i in range(8)]
txt, amostrado = cr.build_transcript_view(short, 14000)
assert not amostrado and "[0s]" in txt
long = [{"start": i*10, "text": "seg "+str(i)*30} for i in range(3000)]
txt2, amostrado2 = cr.build_transcript_view(long, 14000)
assert amostrado2 and "[0s]" in txt2 and "[29990s]" in txt2  # cobre início e fim
print("build_transcript_view (cobertura total do vídeo) OK")
print("\nPRESETS + LIMITE + COBERTURA OK ✅")
