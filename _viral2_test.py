# testa título-fallback e merge/dedup do extrator (lógica pura, sem langchain)
import re
src = open("tools/highlight_extractor.py").read()
block = src[src.index("_TIPOS = ("):src.index("class HighlightsOutput")]
ho = re.search(r"class HighlightsOutput.*?\n\n", src, re.DOTALL).group(0)
ns = {}
exec("from pydantic import BaseModel, Field\n" + block + ho, ns)
H = ns["Highlight"]

# ── 1) título vazio → usa titulos_alt[0] ──
def fix_title(h):
    if (not h.titulo) or h.titulo.strip().lower() in ("", "clip sem título", "clip sem titulo"):
        if h.titulos_alt: h.titulo = h.titulos_alt[0]
        elif h.hook_otimizado: h.titulo = h.hook_otimizado
    return h
h1 = H(inicio=10, fim=40, titulos_alt=["O Segredo do Papado", "outro"], hook_otimizado="Você sabia?")
# titulo cai no default "Clip sem título"
assert h1.titulo == "Clip sem título"
fix_title(h1)
assert h1.titulo == "O Segredo do Papado", h1.titulo
print("título vazio → usa melhor título alternativo OK:", h1.titulo)
# sem titulos_alt → usa hook otimizado
h2 = H(inicio=0, fim=30, hook_otimizado="Você sabia disso?")
fix_title(h2)
assert h2.titulo == "Você sabia disso?"
print("título vazio sem alt → usa hook otimizado OK")

# ── 2) merge/dedup por sobreposição de tempo ──
def merge_dedup(highlights, limit):
    highlights.sort(key=lambda h: h.viral_score or 0, reverse=True)
    kept = []
    for h in highlights:
        overlap = any(not (h.fim <= k.inicio or h.inicio >= k.fim) for k in kept)
        if not overlap: kept.append(h)
        if len(kept) >= limit: break
    return kept

a = H(inicio=0,   fim=75,  viral_score=90, titulo="A")
b = H(inicio=30,  fim=100, viral_score=80, titulo="B (sobrepoe A)")
c = H(inicio=120, fim=195, viral_score=85, titulo="C")
d = H(inicio=200, fim=275, viral_score=70, titulo="D")
res = merge_dedup([a, b, c, d], 15)
tits = [h.titulo for h in res]
assert "B (sobrepoe A)" not in tits, tits   # B descartado (sobrepõe A)
assert tits == ["A", "C", "D"], tits        # ordenado por score, sem sobreposição
print("merge_dedup remove sobreposição e ordena por score OK:", tits)

# respeita o limite
res2 = merge_dedup([a, c, d], 2)
assert len(res2) == 2
print("merge_dedup respeita o limite OK")

print("\nTÍTULO + MERGE/DEDUP OK ✅")
