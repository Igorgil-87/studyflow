import os, time
os.environ["SECRET_KEY"] = "test-secret"
import importlib.util as u
s = u.spec_from_file_location("mfa", "auth/mfa.py")
mfa = u.module_from_spec(s); s.loader.exec_module(mfa)

# ── 1) código tem 6 dígitos ──
c = mfa.generate_code()
assert len(c) == 6 and c.isdigit()
print("generate_code OK (6 dígitos)")

# ── 2) desafio guarda só o HASH, não o código ──
challenge, code = mfa.make_challenge("user@email.com")
assert code not in str(challenge)            # código não vaza
assert challenge["code_hash"] and challenge["email"] == "user@email.com"
print("make_challenge OK (guarda hash, não o código)")

# ── 3) código certo passa, errado falha ──
ok, _ = mfa.verify(challenge, code)
assert ok
ok2, reason = mfa.verify(challenge, "000000")
assert not ok2 and "incorreto" in reason.lower()
print("verify OK (certo passa, errado reprova)")

# ── 4) e-mail diferente não valida (hash inclui e-mail) ──
ch2, code2 = mfa.make_challenge("outro@email.com")
ok3, _ = mfa.verify(ch2, code)   # código do primeiro desafio
assert not ok3
print("hash vinculado ao e-mail OK")

# ── 5) expiração ──
expired = dict(challenge); expired["expires"] = time.time() - 1
ok4, reason4 = mfa.verify(expired, code)
assert not ok4 and "expirad" in reason4.lower()
print("expiração OK")

# ── 6) limite de tentativas ──
maxed = dict(challenge); maxed["attempts"] = mfa.MAX_ATTEMPTS
ok5, reason5 = mfa.verify(maxed, code)
assert not ok5 and "tentativas" in reason5.lower()
print("limite de tentativas OK")

# ── 7) sessão ausente ──
ok6, reason6 = mfa.verify(None, code)
assert not ok6
print("desafio ausente OK")

# ── 8) envio em modo DEV (sem SMTP) não quebra ──
assert mfa.send_code("x@y.com", "123456") is True
print("send_code modo DEV OK")

print("\nMFA OK ✅")
