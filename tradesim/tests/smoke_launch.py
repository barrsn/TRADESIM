"""
tests/smoke_launch.py — TradeSim smoke-test
Run from repo root:
    conda run -n trade310 python tradesim/tests/smoke_launch.py
"""
import sys, importlib, ast, json, tempfile, pathlib

PASS, FAIL = "✅", "❌"

def check(label: str, fn):
    try:
        fn()
        print(f"{PASS}  {label}")
        return True
    except Exception as e:
        print(f"{FAIL}  {label}: {e}")
        return False

results = []

# 1) Syntax of all main modules
TRADESIM = pathlib.Path(__file__).parent.parent
for mod_file in ["app.py", "data.py", "engine.py", "db.py"]:
    src = (TRADESIM / mod_file).read_text(encoding="utf-8")
    results.append(check(f"syntax: {mod_file}", lambda s=src: ast.parse(s)))

# 2) Import engine + db without Streamlit
sys.path.insert(0, str(TRADESIM))
results.append(check("import: engine", lambda: importlib.import_module("engine")))
results.append(check("import: db",     lambda: importlib.import_module("db")))

# 3) engine.Position round-trip
def _engine_roundtrip():
    import engine as eng
    pos = eng.Position(side="LONG", entry_time=1_700_000_000,
                       entry=100.0, stop=98.0, target=104.0)
    assert abs(pos.r_multiple(104.0) - 2.0) < 1e-6, "r_multiple mismatch"
    assert abs(pos.rr_ratio() - 2.0) < 1e-6, "rr_ratio mismatch"
    import pandas as pd
    bar = pd.Series({"open": 100.5, "high": 104.5, "low": 97.5,
                     "close": 102.0, "volume": 1000, "time": 1_700_001_000})
    hit = eng.check_bar(pos, bar)
    assert hit is not None
    assert hit.exit_reason in ("TARGET", "STOP", "STOP (both hit: worst-case)")
results.append(check("engine: Position round-trip", _engine_roundtrip))

# 4) engine.PendingOrder fields
def _pending_fields():
    import engine as eng
    po = eng.PendingOrder(side="SHORT", stop=105.0, target=95.0,
                          setup="ORB", trigger="break", emotag="#FOMO",
                          emo_intensity=3, rule_adherence=1, notes="test")
    assert po.side == "SHORT"
results.append(check("engine: PendingOrder fields", _pending_fields))

# 5) db.init + insert + read + clear (temp file)
def _db_roundtrip():
    import db
    import pandas as pd
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    orig_db_path = db._DB_PATH if hasattr(db, "_DB_PATH") else None
    # patch db path
    db._DB_PATH = tmp.name
    db.init()
    db.insert_trade({
        "symbol": "TEST", "interval": "1d",
        "side": "LONG", "entry_time": 1000, "exit_time": 2000,
        "entry": 100.0, "exit": 102.0, "stop": 98.0, "target": 104.0,
        "r_multiple": 1.0, "exit_reason": "TARGET",
        "setup": "ORB", "trigger": "break", "emotag": "#Neutral",
        "emo_intensity": 0, "rule_adherence": 1, "notes": "",
    })
    df = db.read_trades("TEST", "1d")
    assert len(df) == 1
    assert float(df["r_multiple"].iloc[0]) == 1.0
    db.clear_trades("TEST", "1d")
    assert db.read_trades("TEST", "1d").empty
    if orig_db_path:
        db._DB_PATH = orig_db_path
results.append(check("db: insert / read / clear", _db_roundtrip))

# 6) _pos_to_dict/_pending_to_dict serialization
def _session_serde():
    import engine as eng
    # replicate helper functions from app.py
    def pos_to_dict(p):
        return {"side": p.side, "entry_time": p.entry_time, "entry": p.entry,
                "stop": p.stop, "target": p.target, "setup": p.setup,
                "trigger": p.trigger, "emotag": p.emotag,
                "emo_intensity": p.emo_intensity,
                "rule_adherence": p.rule_adherence, "notes": p.notes}
    pos = eng.Position(side="LONG", entry_time=1_700_000_000,
                       entry=100.0, stop=98.0, target=104.0)
    d = pos_to_dict(pos)
    j = json.dumps(d)
    p2 = eng.Position(**json.loads(j))
    assert p2.entry == 100.0
    assert p2.side == "LONG"
results.append(check("session: pos serialization round-trip", _session_serde))

# 7) compute_stats
def _stats():
    import numpy as np
    import engine as eng
    import pandas as pd
    r = pd.Series([1.0, -1.0, 2.0, -0.5, 1.5, -1.0, 3.0])
    s = eng.compute_stats(r)
    assert "win_rate" in s
    assert "expectancy_R" in s
    assert "equity_curve" in s
    assert abs(s["win_rate"] - 4/7) < 1e-6
results.append(check("engine: compute_stats", _stats))

# 8) monte_carlo returns correct keys
def _mc():
    import pandas as pd
    import engine as eng
    r = pd.Series([1.0, -1.0, 2.0, -0.5, 1.5, -1.0, 3.0, 0.5])
    mc = eng.monte_carlo(r, n_sims=50, n_trades=20)
    for k in ("p5", "p25", "p50", "p75", "p95", "ruin_pct", "curves_sample"):
        assert k in mc, f"missing key: {k}"
results.append(check("engine: monte_carlo keys", _mc))

# Summary
total = len(results)
passed = sum(results)
print(f"\n{'─'*40}")
print(f"Passed {passed}/{total}")
if passed < total:
    sys.exit(1)
