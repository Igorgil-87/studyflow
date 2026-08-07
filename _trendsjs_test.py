# garante que toda função usada em trends.js está definida (pega o bug do escapeHtml)
import re
src = open("static/js/trends.js").read()

# funções auxiliares que DEVEM existir (usadas no render)
must_define = ["escapeHtml", "renderEditorial", "buildHero", "buildTrendNewsCard", "el", "nxLoadMarket"]
for fn in must_define:
    # aceita 'function nome(' ou 'const nome =' ou 'nome =' (arrow)
    defined = bool(re.search(rf"(function\s+{fn}\b)|((const|let|var)\s+{fn}\s*=)", src))
    assert defined, f"função '{fn}' é usada mas NÃO está definida em trends.js"
print("todas as funções auxiliares de trends.js estão definidas OK ✅")

# escapeHtml deve escapar os 5 caracteres perigosos
m = re.search(r"function escapeHtml.*?\n}", src, re.DOTALL)
assert m and "&amp;" in m.group(0) and "&lt;" in m.group(0) and "&quot;" in m.group(0)
print("escapeHtml escapa & < > \" ' OK ✅")
