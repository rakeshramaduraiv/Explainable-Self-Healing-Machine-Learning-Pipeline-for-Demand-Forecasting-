import os
import sys
import json
import joblib


def _pass(label):
    print(f"  [PASS] {label}")
    return True

def _fail(label, reason=""):
    print(f"  [FAIL] {label}" + (f": {reason}" if reason else ""))
    return False


def check_file(label, path):
    return _pass(label) if os.path.exists(path) else _fail(label, f"not found: {path}")


def check_json(label, path, required_keys=None):
    if not os.path.exists(path):
        return _fail(label, f"not found: {path}")
    try:
        with open(path) as f:
            data = json.load(f)
        if required_keys:
            missing = [k for k in required_keys if k not in (data[-1] if isinstance(data, list) else data)]
            if missing:
                return _fail(label, f"missing keys: {missing}")
        return _pass(label)
    except json.JSONDecodeError as e:
        return _fail(label, f"invalid JSON: {e}")


def check_model(label, path):
    if not os.path.exists(path):
        return _fail(label, f"not found: {path}")
    try:
        model = joblib.load(path)
        if not hasattr(model, "predict"):
            return _fail(label, "loaded object has no .predict()")
        return _pass(label)
    except Exception as e:
        return _fail(label, f"load error: {e}")


def main():
    print("=" * 50)
    print("PHASE 1 VERIFICATION")
    print("=" * 50)

    results = [
        check_file("Dataset",          "data/uploaded_data.csv"),
        check_model("Active Model",    "models/active_model.pkl"),
        check_model("Baseline RF",     "models/baseline_model_rf.pkl"),
        check_json("Metrics",          "logs/baseline_metrics.json", ["train"]),
        check_json("Data Inspection",  "logs/data_inspection.json",  ["rows", "stores"]),
        check_json("Data Split",       "logs/data_split.json",       ["train_rows", "cutoff_date"]),
        check_json("Training Log",     "logs/training_log.json"),
        check_json("Drift History",    "logs/drift_history.json"),
        check_json("Phase1 Summary",   "logs/phase1_summary.json",   ["final_severity", "months_monitored"]),
        check_json("Phase2 Handoff",   "logs/phase1_to_phase2_handoff.json", ["model_path", "final_severity"]),
        check_file("Completion Flag",  "logs/phase1_complete.json"),
    ]

    passed = sum(results)
    total  = len(results)
    print(f"\nResult: {passed}/{total} checks passed")

    if passed == total:
        print("Phase 1 COMPLETE — Ready for Phase 2")
        return 0
    else:
        print(f"Phase 1 INCOMPLETE — {total - passed} check(s) failed. Run main.py first.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
