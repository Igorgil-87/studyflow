import importlib.util as u, tempfile, os
# 1) geração do PNG
import certificado
png = certificado.gerar_certificado_png("Igor Gil","Machine Learning na Prática","07/07/2026","88%")
assert png[:8] == b'\x89PNG\r\n\x1a\n', "não é PNG válido"
assert len(png) > 10000, "PNG muito pequeno"
print("gera PNG válido OK (", len(png), "bytes )")

# nome vazio não quebra
png2 = certificado.gerar_certificado_png("","Curso X","01/01/2026",None)
assert png2[:8] == b'\x89PNG\r\n\x1a\n'
print("PNG com nome vazio/sem nota OK")

# curso longo (quebra de linha) não quebra
png3 = certificado.gerar_certificado_png("Ana","Desenvolvimento Back-End com Python e Arquitetura de Microsserviços Avançada","01/01/2026","95%")
assert png3[:8] == b'\x89PNG\r\n\x1a\n'
print("PNG com curso longo (quebra) OK")

# 2) persistência de concluídos
s=u.spec_from_file_location("prefs","auth/prefs.py"); prefs=u.module_from_spec(s)
tmp_fd, tmpdb = tempfile.mkstemp(suffix=".db")
os.close(tmp_fd)
os.environ["USERS_DB"] = tmpdb
s.loader.exec_module(prefs)
user="aluno@sf"
assert (prefs.get_pref(user,"concluidos",default=[]) or [])==[]
prefs.set_pref(user,"concluidos",[{"id":"c1","curso":"RNN","nota":"90%","data":"07/07/2026"}])
lidos=prefs.get_pref(user,"concluidos",default=[])
assert len(lidos)==1 and lidos[0]["curso"]=="RNN"
print("persistir curso concluído OK")
assert (prefs.get_pref("outro","concluidos",default=[]) or [])==[]
print("isolamento OK")
os.remove(tmpdb) if os.path.exists(tmpdb) else None
print("\nCERTIFICADOS OK ✅")
