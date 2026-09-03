import os, tempfile
_fd, _tmpdb = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["OBS_DB"] = _tmpdb
from obs import db, judge, report
db.init()

def caller(prompt, model):
    return '{"groundedness":0.95,"relevance":0.90,"coherence":0.88,"source_fidelity":0.97,"completeness":0.84,"hallucination":false,"judge_score":0.91,"rationale":"resposta sustentada"}'

v = judge.run_response_eval(
    "rag-1", "rag_answer", "O que é RAG?",
    "RAG recupera contexto antes de gerar uma resposta.",
    "RAG recupera contexto relevante e o fornece ao modelo antes da geração.",
    _caller=caller,
)
assert v["ok"] and v["source_fidelity"] == 0.97 and v["completeness"] == 0.84, v
rows = db.query("SELECT * FROM evals WHERE trace_id=?", ("rag-1",))
assert len(rows) == 1 and rows[0]["prompt_version"], rows
s = report.summary()
assert s["evals"]["count"] == 1
assert s["evals"]["avg_source_fidelity"] == 0.97
assert s["evals"]["by_target"]["rag_answer"]["judge_score"] == 0.91
print("RESPONSE EVAL + PERSISTENCE + REPORT OK ✅")
