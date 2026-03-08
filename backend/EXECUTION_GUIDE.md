# Phase 1 Execution Guide

## Setup
```bash
pip install -r requirements.txt
```

## Run
```bash
python main.py
```

## Verify
```bash
python verify_system.py
```

## Expected Output
- Drift severity: none / mild / severe
- All files created in logs/

## Troubleshooting
- Missing dataset: ensure data/uploaded_data.csv exists
- Import errors: run pip install -r requirements.txt
- Date parse errors: dataset must have Date column in dd-mm-yyyy format
