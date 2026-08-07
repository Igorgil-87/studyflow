# Testa a lógica de seleção de tier S/A (replica a regra do extrator, sem langchain)
def select_tier(highlights, qty_min):
    sa = [h for h in highlights if (h.get("tier") or "").upper().strip() in ("S","A")]
    if sa:
        chosen = sa
    else:
        chosen = sorted(highlights, key=lambda h: h.get("viral_score",0), reverse=True)[:max(1,qty_min)]
    chosen.sort(key=lambda h: h.get("viral_score",0), reverse=True)
    return chosen

# ── 1) mantém só S e A, ordenado por score ──
hls = [
    {"titulo":"a","tier":"S","viral_score":92},
    {"titulo":"b","tier":"C","viral_score":40},
    {"titulo":"c","tier":"A","viral_score":78},
    {"titulo":"d","tier":"B","viral_score":55},
    {"titulo":"e","tier":"A","viral_score":85},
]
r = select_tier(hls, 2)
assert [h["titulo"] for h in r] == ["a","e","c"], [h["titulo"] for h in r]  # S(92),A(85),A(78)
assert all(h["tier"] in ("S","A") for h in r)
print("filtro S/A + ordenação por score OK")

# ── 2) fallback: nenhum S/A → pega top por score ──
low = [{"titulo":"x","tier":"C","viral_score":30},{"titulo":"y","tier":"B","viral_score":60},{"titulo":"z","tier":"C","viral_score":45}]
r2 = select_tier(low, 2)
assert [h["titulo"] for h in r2] == ["y","z"], [h["titulo"] for h in r2]  # top 2 por score
print("fallback (nenhum S/A → top por score) OK")

# ── 3) threading: campos virais entram no clip ──
hl = {"inicio":10,"fim":40,"titulo":"T","tier":"S","viral_score":90,"hook":"h",
      "hook_otimizado":"H!","titulos_alt":["t1","t2"],"thumb_texto":"CHOCANTE",
      "thumb_emocao":"choque","s_hook":9,"hashtags":["a","b"],"recomendacao":"Publicar"}
clip = {"arquivo":"v.mp4","duracao":"30s","resumo":"r"}
for k,v in hl.items():
    if k not in ("inicio","fim","arquivo"): clip[k]=v
assert clip["tier"]=="S" and clip["thumb_texto"]=="CHOCANTE" and clip["hook_otimizado"]=="H!"
assert clip["titulos_alt"]==["t1","t2"] and clip["s_hook"]==9
assert clip["arquivo"]=="v.mp4"  # preservado
print("threading dos campos virais pro clip OK")

# ── 4) thumbnail usa thumb_texto primeiro ──
def thumb_title(clip): return clip.get("thumb_texto") or clip.get("hook") or clip.get("titulo") or ""
assert thumb_title(clip)=="CHOCANTE"
assert thumb_title({"hook":"oi","titulo":"t"})=="oi"
assert thumb_title({"titulo":"só titulo"})=="só titulo"
print("thumbnail prioriza thumb_texto OK")

print("\nVIRAL (tier + threading + thumb) OK ✅")
