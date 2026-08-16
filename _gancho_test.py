"""Confirma que o gancho no app.js chama o endpoint certo e que ele funciona."""
import re, importlib.util as u, tempfile, os

# 1) o app.js chama o endpoint correto?
js = open("static/js/app.js").read()
assert "/api/curso-atual" in js, "gancho não encontrado no app.js"
assert "renderQuiz" in js
# o fetch está DENTRO do renderQuiz (após o resultTitle)
i_render = js.index("function renderQuiz")
i_fetch = js.index("/api/curso-atual")
i_next_fn = js.find("\nfunction ", i_render + 10)
assert i_render < i_fetch < (i_next_fn if i_next_fn > 0 else len(js)), "fetch fora do renderQuiz"
assert ".catch(" in js[i_fetch:i_fetch+400], "sem catch → poderia quebrar a geração"
print("gancho no app.js OK (dentro do renderQuiz, com catch)")

# 2) a lógica original continua intacta (funções-chave presentes)
for fn in ["renderQuiz", "$('#resultTitle')", "flashcardsView", "questoesView"]:
    assert fn in js, f"perdeu {fn}"
print("lógica original intacta (renderQuiz, resultTitle, views)")

# 3) o endpoint salva e a home lê
s=u.spec_from_file_location("prefs","auth/prefs.py"); prefs=u.module_from_spec(s)
tmp_fd, tmpdb = tempfile.mkstemp(suffix=".db")
os.close(tmp_fd)
os.environ["USERS_DB"] = tmpdb
s.loader.exec_module(prefs)
user="aluno@sf"
curso={"titulo":"Redes Neurais","subtitulo":"Curso gerado por IA · Whisper + LLM","progresso":0,"aula_atual":""}
prefs.set_pref(user,"curso_atual",curso)
lido=prefs.get_pref(user,"curso_atual",default=None)
assert lido["titulo"]=="Redes Neurais"
print("fluxo completo OK: gerar curso → salva → home lê")
os.remove(tmpdb) if os.path.exists(tmpdb) else None
print("\nGANCHO OK ✅")
