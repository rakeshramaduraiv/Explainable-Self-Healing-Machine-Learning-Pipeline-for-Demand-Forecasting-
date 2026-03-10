import json
import os
import csv
from datetime import datetime
from logger import get_logger

log = get_logger(__name__)


class LogBook:
    def __init__(self, log_dir="logs"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

    def _save_log(self, filename, entry):
        path = os.path.join(self.log_dir, filename)
        data = []
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                data = []
        data.append(entry)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)

    def log_training(self, metrics, params, feature_count):
        self._save_log("training_log.json", {
            "timestamp": datetime.now().isoformat(),
            "feature_count": feature_count,
            "params": params,
            "metrics": metrics,
        })

    def log_batch_predictions(self, month_label, predictions, actuals, stores=None):
        if not predictions:
            return
        self._save_log("prediction_batches.json", {
            "timestamp": datetime.now().isoformat(),
            "month": month_label,
            "count": len(predictions),
            "mean_pred":   round(sum(predictions) / len(predictions), 2),
            "mean_actual": round(sum(actuals)     / len(actuals),     2),
        })
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(self.log_dir, f"predictions_{ts}.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["month", "store", "prediction", "actual", "error"])
            for i, (p, a) in enumerate(zip(predictions, actuals)):
                store = int(stores[i]) if stores is not None else ""
                writer.writerow([month_label, store, round(p, 2), round(a, 2), round(a - p, 2)])

    def log_drift_detection(self, month_label, drift_report):
        self._save_log("drift_history.json", {
            "timestamp": datetime.now().isoformat(),
            "month": month_label,
            "severity": drift_report["severity"],
            "severe_features": drift_report["severe_features"],
            "mild_features": drift_report["mild_features"],
            "total_features": drift_report.get("total_features", 0),
            "error_trend": drift_report["error_trend"],
        })

    def log_phase1_completion(self, summary):
        with open(os.path.join(self.log_dir, "phase1_summary.json"), "w") as f:
            json.dump(summary, f, indent=2)

        handoff = {
            "timestamp": datetime.now().isoformat(),
            "model_path": "models/active_model.pkl",
            "metrics_path": "logs/baseline_metrics.json",
            "drift_history_path": "logs/drift_history.json",
            "final_severity": summary.get("final_severity"),
            "recommendation": summary.get("recommendation"),
            "feature_names": summary.get("feature_names", []),
        }
        with open(os.path.join(self.log_dir, "phase1_to_phase2_handoff.json"), "w") as f:
            json.dump(handoff, f, indent=2)

        with open(os.path.join(self.log_dir, "phase1_complete.json"), "w") as f:
            json.dump({"completed": True, "timestamp": datetime.now().isoformat()}, f, indent=2)

        log.info("All logs saved")
