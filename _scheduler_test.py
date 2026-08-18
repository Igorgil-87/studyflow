import os, tempfile, time
from urllib.parse import urlparse
_fd, _tmpdb = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["OBS_DB"] = _tmpdb
os.environ["DRIFT_WEBHOOK_URL"] = "https://example.com/hook"  # ativa envio
from obs import db, drift, notify
import seed_demo

db.init()

# ── 1) NotifyGate: transição + cooldown ──
gate = notify.NotifyGate(cooldown_s=100)
alert_rep = {"status":"alert","ts":0,"alerts":[{"metric":"error_rate","severity":"critical","message":"x","baseline":0,"recent":1}]}
ok_rep = {"status":"ok","alerts":[]}
t=1000.0
assert gate.should(alert_rep, t) is True, "1a vez em alerta deve notificar"
assert gate.should(alert_rep, t+10) is False, "mesmo alerta dentro do cooldown: não"
assert gate.should(alert_rep, t+200) is True, "passou cooldown: notifica de novo"
assert gate.should(ok_rep, t+201) is False, "status ok não notifica"
# novo alerta diferente reseta assinatura → notifica mesmo dentro do cooldown
alert2 = {"status":"alert","ts":0,"alerts":[{"metric":"avg_judge_score","severity":"critical","message":"y","baseline":0.9,"recent":0.7}]}
assert gate.should(alert2, t+202) is True, "conjunto de alertas mudou: notifica"
print("NotifyGate (transição + cooldown + mudança de assinatura) OK")

# ── 2) send_alert com webhook FALSO injetado ──
sent_payloads = []
def fake_opener(url, data):
    sent_payloads.append((url, data))
assert notify.send_alert(alert_rep, _opener=fake_opener) is True
assert notify.send_alert(ok_rep, _opener=fake_opener) is False, "ok não envia"
_netloc = urlparse(sent_payloads[0][0]).netloc
assert len(sent_payloads)==1 and (_netloc == "example.com" or _netloc.endswith(".example.com"))
import json
body = json.loads(sent_payloads[0][1].decode())
assert "text" in body and "alerts" in body and body["status"]=="alert"
print("send_alert (webhook injetado, fail-open p/ ok) OK")
print("  payload.text:", body["text"].split(chr(10))[0])

# ── 3) send_alert é fail-open se o webhook explode ──
def boom(url, data): raise RuntimeError("rede caiu")
assert notify.send_alert(alert_rep, _opener=boom) is False
print("send_alert fail-open em erro de rede OK")

# ── 4) tick real do scheduler com dados degradados → persiste + tenta notificar ──
seed_demo.main()
import scheduler
g2 = notify.NotifyGate(cooldown_s=0)
rep = scheduler.tick(g2)
assert rep["status"]=="alert"
hist = drift.history()
assert len(hist)>=1 and hist[0]["status"]=="alert"
print("scheduler.tick persistiu no histórico:", {k:hist[0][k] for k in ('status','n_alerts')})

print("\nSCHEDULER + NOTIFY OK ✅")
