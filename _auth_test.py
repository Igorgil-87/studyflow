import os, tempfile
_fd, _tmpdb = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["USERS_DB"] = _tmpdb
from auth import users

users.init()

# ── 1) criar usuário local + hash (senha nunca em texto) ──
u = users.create_local_user("Maria@Email.com ", "segredo123", "Maria")
assert u["email"] == "maria@email.com"  # normalizado
assert u["password_hash"] and "segredo123" not in u["password_hash"]
assert u["provider"] == "local"
print("create_local_user OK (e-mail normalizado, senha em hash)")

# ── 2) login correto e errado ──
assert users.verify_login("maria@email.com", "segredo123")["name"] == "Maria"
assert users.verify_login("maria@email.com", "errada") is None
assert users.verify_login("naoexiste@x.com", "x") is None
print("verify_login OK (certo/errado/inexistente)")

# ── 3) e-mail duplicado é barrado ──
try:
    users.create_local_user("maria@email.com", "outra123"); assert False
except ValueError as e:
    assert "já está cadastrado" in str(e)
print("e-mail duplicado barrado OK")

# ── 4) validações ──
for bad in [("","x123456"),("semarroba","x123456"),("a@b.com","123")]:
    try: users.create_local_user(*bad); assert False, bad
    except ValueError: pass
print("validações (e-mail/senha) OK")

# ── 5) OAuth upsert: cria uma vez, recupera depois ──
o1 = users.upsert_oauth_user("google", "G-123", "joao@gmail.com", "João")
o2 = users.upsert_oauth_user("google", "G-123", "joao@gmail.com", "João")
assert o1["id"] == o2["id"] and o1["provider"] == "google"
print("upsert_oauth_user OK (idempotente)")

# ── 6) OAuth vincula por e-mail a conta local existente ──
linked = users.upsert_oauth_user("linkedin", "L-9", "maria@email.com", "Maria")
assert linked["email"] == "maria@email.com"  # achou a conta local
print("vínculo por e-mail OK")

# ── 7) Instagram sem e-mail (provider_id only) ──
ig = users.upsert_oauth_user("instagram", "IG-7", None, "maria_insta")
assert ig["provider"] == "instagram" and ig["name"] == "maria_insta"
print("usuário Instagram sem e-mail OK")

print("\nAUTH (usuários + OAuth upsert) OK ✅")
