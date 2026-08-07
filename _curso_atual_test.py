import importlib.util as u, tempfile, os
s=u.spec_from_file_location("prefs","auth/prefs.py"); prefs=u.module_from_spec(s)
tmpdb=tempfile.mktemp(suffix=".db"); os.environ["USERS_DB"]=tmpdb; s.loader.exec_module(prefs)

user="aluno@studyflow"
# sem curso ainda → None
assert prefs.get_pref(user,"curso_atual",default=None) is None
print("estado inicial (sem curso) OK")

# salva um curso em andamento (como o endpoint POST faz)
curso={"titulo":"Redes Neurais Convolucionais","subtitulo":"Curso gerado por IA",
       "progresso":65,"aula_atual":"Backpropagation","atualizado_em":"2026-07-07 21:00"}
prefs.set_pref(user,"curso_atual",curso)

# lê de volta
lido=prefs.get_pref(user,"curso_atual",default=None)
assert lido["titulo"]=="Redes Neurais Convolucionais" and lido["progresso"]==65
assert lido["aula_atual"]=="Backpropagation"
print("salvar + ler curso atual OK (título, 65%, aula)")

# isolamento
assert prefs.get_pref("outro","curso_atual",default=None) is None
print("isolamento por usuário OK")

os.remove(tmpdb) if os.path.exists(tmpdb) else None
print("\nCURSO EM ANDAMENTO OK ✅")
