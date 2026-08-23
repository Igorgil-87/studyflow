import importlib.util as u, tempfile, os
s=u.spec_from_file_location("prefs","auth/prefs.py"); prefs=u.module_from_spec(s)
tmp_fd, tmpdb = tempfile.mkstemp(suffix=".db")
os.close(tmp_fd)
os.environ["USERS_DB"] = tmpdb
s.loader.exec_module(prefs)

user="aluno@sf"
assert (prefs.get_pref(user,"eventos",default=[]) or []) == []
print("estado inicial vazio OK")

# cria 2 eventos fora de ordem
evs=[]
evs.append({"id":"e2","titulo":"Live: Machine Learning","data":"2026-07-20","hora":"19:00","tipo":"live","nota":""})
evs.append({"id":"e1","titulo":"Estudar RNN","data":"2026-07-10","hora":"08:00","tipo":"aula","nota":"cap 3"})
prefs.set_pref(user,"eventos",evs)

# lista ordenada por data (como o endpoint faz)
lidos=prefs.get_pref(user,"eventos",default=[])
lidos.sort(key=lambda e:(e.get("data",""),e.get("hora","")))
assert lidos[0]["data"]=="2026-07-10" and lidos[1]["data"]=="2026-07-20"
print("criar + ordenar por data OK:", [e["titulo"] for e in lidos])

# deletar
lidos=[e for e in lidos if e["id"]!="e1"]
prefs.set_pref(user,"eventos",lidos)
assert len(prefs.get_pref(user,"eventos",default=[]))==1
print("deletar evento OK")

# isolamento
assert (prefs.get_pref("outro","eventos",default=[]) or [])==[]
print("isolamento por usuário OK")

os.remove(tmpdb) if os.path.exists(tmpdb) else None
print("\nEVENTOS OK ✅")
