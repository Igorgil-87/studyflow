"""Testa a lógica de trilhas: catálogo + persistência (get/set_pref) + validações."""
import importlib.util as u, tempfile, os

# catálogo
import catalog
assert len(catalog.all_courses()) == 12
assert catalog.by_id("ia-decisao")["horas"] == 10
assert catalog.by_id("inexistente") is None
print("catálogo OK (12 cursos, lookup por id)")

# persistência via prefs (usa db temporário)
s = u.spec_from_file_location("prefs", "auth/prefs.py"); prefs = u.module_from_spec(s)
tmpdb = tempfile.mktemp(suffix=".db")
os.environ["USERS_DB"] = tmpdb
s.loader.exec_module(prefs)

# simula o fluxo do endpoint de criar trilha
user = "teste@studyflow"
trilhas = prefs.get_pref(user, "trilhas", default=[]) or []
assert trilhas == [], "começa vazio"

# cria trilha (valida ids + soma horas, como o endpoint faz)
ids = ["ia-decisao", "ml-engineering", "python-backend"]
validos = [c for c in ids if catalog.by_id(c)]
horas = sum(catalog.by_id(c)["horas"] for c in validos)
assert horas == 10 + 38 + 42
trilhas.append({"id":"t1","nome":"Trilha de IA","cursos":validos,"horas":horas,"criada_em":"2026-07-07"})
prefs.set_pref(user, "trilhas", trilhas)

# lê de volta
lidas = prefs.get_pref(user, "trilhas", default=[])
assert len(lidas) == 1 and lidas[0]["nome"] == "Trilha de IA" and lidas[0]["horas"] == 90
print("criar + persistir trilha OK (nome, cursos, 90h somadas)")

# isolamento entre usuários
outro = prefs.get_pref("outro@user", "trilhas", default=[])
assert outro == [], "trilha de um usuário não vaza para outro"
print("isolamento por usuário OK")

# deletar
trilhas2 = [t for t in lidas if t["id"] != "t1"]
prefs.set_pref(user, "trilhas", trilhas2)
assert prefs.get_pref(user, "trilhas", default=[]) == []
print("deletar trilha OK")

os.remove(tmpdb) if os.path.exists(tmpdb) else None
print("\nTRILHAS OK ✅")
