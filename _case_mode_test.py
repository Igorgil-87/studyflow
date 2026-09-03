from case_mode.evidence import requirement_matrix, coverage_summary, architecture_layers

rows = requirement_matrix()
assert len(rows) >= 10, len(rows)
assert all("requirement" in r and "implementation" in r and "evidence" in r for r in rows)
assert all(r["covered"] for r in rows), [r["id"] for r in rows if not r["covered"]]
summary = coverage_summary()
assert summary["all_covered"] is True, summary
assert summary["coverage_pct"] == 100.0, summary
layers = architecture_layers()
assert any(x["name"] == "Knowledge" for x in layers)
assert any(x["name"] == "Responsible AI" for x in layers)
print("CASE MODE + EVIDENCE MATRIX OK ✅")
