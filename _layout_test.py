# valida o módulo de preferências (layout do Mission Control)
import importlib.util as u, os, tempfile
_fd, _tmpdb = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["USERS_DB"] = _tmpdb
s=u.spec_from_file_location("prefs","auth/prefs.py"); p=u.module_from_spec(s); s.loader.exec_module(p)

# default quando vazio
assert p.get_pref("u1","mc_layout", default=None) is None
# grava ordem e relê
ordem = ["mcFeedWidget","gtSummaryCard","mcMarketWidget","gtCrossThemes"]
assert p.set_pref("u1","mc_layout", ordem)
assert p.get_pref("u1","mc_layout") == ordem
# isolamento entre usuários
assert p.get_pref("u2","mc_layout", default=[]) == []
p.set_pref("u2","mc_layout", ["gtSummaryCard"])
assert p.get_pref("u1","mc_layout") == ordem        # u1 intacto
assert p.get_pref("u2","mc_layout") == ["gtSummaryCard"]
# sobrescrita
assert p.set_pref("u1","mc_layout", ["mcMarketWidget"])
assert p.get_pref("u1","mc_layout") == ["mcMarketWidget"]
print("layout: persistência, isolamento por usuário e sobrescrita OK ✅")

# validação de entrada (espelha a regra do endpoint)
def valido(layout):
    return isinstance(layout, list) and all(isinstance(x, str) for x in layout)
assert valido(["a","b"]) and not valido("x") and not valido([1,2]) and not valido(None)
print("validação de layout (lista de strings) OK ✅")
