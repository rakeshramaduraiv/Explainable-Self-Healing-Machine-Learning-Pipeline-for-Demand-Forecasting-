"""SQLite storage — uses context managers to avoid connection leaks."""
import sqlite3
import json
import os
from contextlib import contextmanager
from datetime import datetime


class DriftDatabase:
    def __init__(self, db_path="logs/drift_system.db"):
        os.makedirs("logs", exist_ok=True)
        self.db_path = db_path
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS model_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT UNIQUE,
                    trained_at TEXT,
                    metrics TEXT,
                    features TEXT,
                    model_path TEXT,
                    is_active INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS drift_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    month TEXT,
                    severity TEXT,
                    severe_features INTEGER,
                    mild_features INTEGER,
                    error_increase REAL,
                    wasserstein TEXT,
                    js_divergence TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    month TEXT,
                    mean_pred REAL,
                    mean_actual REAL,
                    lower_bound REAL,
                    upper_bound REAL,
                    model_version TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS feature_importance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_version TEXT,
                    feature TEXT,
                    importance REAL,
                    category TEXT
                );
            """)

    def save_model_version(self, version, metrics, features, model_path, is_active=True):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO model_versions "
                "(version,trained_at,metrics,features,model_path,is_active) VALUES (?,?,?,?,?,?)",
                (version, datetime.now().isoformat(), json.dumps(metrics),
                 json.dumps(features), model_path, int(is_active))
            )

    def save_drift_log(self, month, report):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO drift_logs "
                "(month,severity,severe_features,mild_features,error_increase,wasserstein,js_divergence) "
                "VALUES (?,?,?,?,?,?,?)",
                (month, report["severity"], report["severe_features"], report["mild_features"],
                 report["error_trend"].get("error_increase", 0),
                 json.dumps(report.get("wasserstein", {})),
                 json.dumps(report.get("js_divergence", {})))
            )

    def save_prediction(self, month, mean_pred, mean_actual, lower, upper, version):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO predictions "
                "(month,mean_pred,mean_actual,lower_bound,upper_bound,model_version) VALUES (?,?,?,?,?,?)",
                (month, mean_pred, mean_actual, lower, upper, version)
            )

    def save_feature_importance(self, version, importance_dict):
        rows = [
            (version, f, float(v), "high" if v > 0.1 else "medium" if v > 0.01 else "low")
            for f, v in importance_dict.items()
        ]
        with self._conn() as conn:
            conn.executemany(
                "INSERT INTO feature_importance (model_version,feature,importance,category) VALUES (?,?,?,?)",
                rows
            )

    def get_drift_history(self, limit=100):
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT * FROM drift_logs ORDER BY created_at DESC LIMIT ?", (limit,)
            )
            return [dict(r) for r in cur.fetchall()]

    def get_active_model(self):
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT * FROM model_versions WHERE is_active=1 ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
            return dict(row) if row else None
