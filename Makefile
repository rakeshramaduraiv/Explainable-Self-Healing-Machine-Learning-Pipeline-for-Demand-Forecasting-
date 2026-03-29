PYTHON = venv\Scripts\python.exe
STREAMLIT = venv\Scripts\streamlit.exe

# ── Setup ─────────────────────────────────────────────────
install:
	python -m venv venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

# ── Full Pipeline (initial training) ─────────────────────
pipeline:
	$(PYTHON) -m pipelines.flow

# ── Individual Pipeline Steps ─────────────────────────────
ingest:
	$(PYTHON) -c "from pipelines._01_ingest import ingest_data; ingest_data()"

validate:
	$(PYTHON) -c "from pipelines._02_validate import validate_data; validate_data()"

features:
	$(PYTHON) -c "from pipelines._03_features import create_features; create_features()"

train:
	$(PYTHON) -c "from pipelines._04_predict import train_and_predict; train_and_predict()"

evaluate:
	$(PYTHON) -c "from pipelines._05_evaluate import evaluate; evaluate()"

drift:
	$(PYTHON) -c "from pipelines._drift import run_drift_check; import json; print(json.dumps(run_drift_check(), indent=2))"

# ── Model Update ──────────────────────────────────────────
finetune:
	$(PYTHON) -c "from pipelines._06_retrain import fine_tune; import json; print(json.dumps(fine_tune(), indent=2))"

retrain:
	$(PYTHON) -c "from pipelines._06_retrain import sliding_window_retrain; import json; print(json.dumps(sliding_window_retrain(), indent=2))"

forecast:
	$(PYTHON) -c "from pipelines._06_retrain import predict_next_month; df=predict_next_month(); print(df.head())"

# ── Fix / Repair Utilities ────────────────────────────────
fix-schema:
	$(PYTHON) fix_schema.py

fix-encoders:
	$(PYTHON) fix_encoders.py

debug:
	$(PYTHON) debug_features.py

# ── Dashboard ─────────────────────────────────────────────
dashboard:
	$(STREAMLIT) run dashboards/app.py

# ── Tests ─────────────────────────────────────────────────
test:
	$(PYTHON) -m pytest tests/ -v

test-coverage:
	$(PYTHON) -m pytest tests/ --cov=pipelines --cov-report=term-missing

# ── Git ───────────────────────────────────────────────────
status:
	git status

log:
	git log --oneline -10

# ── Cleanup ───────────────────────────────────────────────
clean-pyc:
	del /s /q *.pyc 2>nul
	del /s /q __pycache__ 2>nul
