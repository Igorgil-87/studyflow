# valida que o schema Highlight tolera campos faltando (o bug do print)
import re
src = open("tools/highlight_extractor.py").read()
block = src[src.index("_TIPOS = ("):src.index("class HighlightsOutput")]
ho = re.search(r"class HighlightsOutput.*?\n\n", src, re.DOTALL).group(0)
ns = {}
exec("from pydantic import BaseModel, Field\n" + block + ho, ns)
H, HO = ns["Highlight"], ns["HighlightsOutput"]

# JSON real que falhava: 5 highlights SEM hashtags
items = [
  {"titulo":"O Anticristo é o Papa?","inicio":168,"fim":174,"tipo":"controversia","viral_score":92,"tier":"S","hook":"O Anticristo era o papado."},
  {"titulo":"O Julgamento Final","inicio":321,"fim":347,"viral_score":88,"tier":"A"},
  {"titulo":"sem tempo","viral_score":50},  # sem inicio/fim → descarta
]
ok = [H(**it) for it in items if "inicio" in it and "fim" in it]
assert len(ok) == 2
assert ok[0].hashtags == [] and ok[0].descricao == "" and ok[0].thumb_texto == ""
assert ok[0].titulo == "O Anticristo é o Papa?" and ok[0].tier == "S"
assert HO(highlights=ok).highlights[1].viral_score == 88
print("schema tolera hashtags/descricao/thumb ausentes OK ✅")

# ── normalização de título (bug "Clip sem título") ──
def normalize_title(h):
    t = (h.get("titulo") or "").strip()
    if not t or t.lower() == "clip sem título":
        return (h.get("titulos_alt") or [None])[0] or h.get("hook_otimizado") or h.get("thumb_texto") or "Corte viral"
    return t

# título vazio mas com alternativos → usa o 1º alternativo
h1 = {"titulo":"", "titulos_alt":["O Anticristo é o Papa?","A Verdade Sobre..."], "hook_otimizado":"Você sabia?"}
assert normalize_title(h1) == "O Anticristo é o Papa?"
# placeholder default → idem
h2 = {"titulo":"Clip sem título", "titulos_alt":["Título Forte"]}
assert normalize_title(h2) == "Título Forte"
# sem alternativos → usa hook otimizado
h3 = {"titulo":"", "titulos_alt":[], "hook_otimizado":"Você sabia que...?"}
assert normalize_title(h3) == "Você sabia que...?"
# título bom → mantém
h4 = {"titulo":"Meu Título"}
assert normalize_title(h4) == "Meu Título"
print("normalização de título (nunca mais 'Clip sem título') OK ✅")
