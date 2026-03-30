"""
start_light.py - Start the Sales Forecasting System
Dataset: Superstore (train.csv) | 19 features (5 raw + 7 aggregated + 7 engineered)
"""
import subprocess, sys, os, time, threading, webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(ROOT, "frontend")
VENV_PY = os.path.join(ROOT, "venv", "Scripts", "python.exe")
PYTHON = VENV_PY if os.path.exists(VENV_PY) else sys.executable

def print_banner():
    print()
    print("=" * 60)
    print("   SALES FORECASTING SYSTEM")
    print("=" * 60)
    print("   Dataset  :  Superstore (train.csv - 9,800 orders)")
    print("   Model    :  LightGBM (200 trees, 19 features)")
    print("   Features :  5 raw + 7 aggregated + 7 engineered")
    print("=" * 60)
    print("   Frontend :  http://localhost:5173")
    print("   Backend  :  http://localhost:8000")
    print("   API Docs :  http://localhost:8000/docs")
    print("=" * 60)
    print()

def stream(proc, tag):
    for line in iter(proc.stdout.readline, b""):
        txt = line.decode(errors="ignore").rstrip()
        if txt and not any(s in txt.lower() for s in ['watching', 'restarted', 'reloader']):
            print(f"  [{tag}] {time.strftime('%H:%M:%S')} | {txt}")

def start_backend():
    print("[1/2] Starting Backend...")
    proc = subprocess.Popen([PYTHON, "backend_minimal.py"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stream(proc, "API")

def start_frontend():
    print("[2/2] Starting Frontend...")
    if not os.path.exists(os.path.join(FRONTEND, "node_modules")):
        subprocess.run("npm install", cwd=FRONTEND, shell=True, capture_output=True)
    proc = subprocess.Popen("npm run dev", cwd=FRONTEND, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    stream(proc, "UI")

def main():
    print_banner()
    threading.Thread(target=start_backend, daemon=True).start()
    time.sleep(5)
    threading.Thread(target=start_frontend, daemon=True).start()
    time.sleep(3)
    webbrowser.open("http://localhost:5173")
    print("\n" + "=" * 60)
    print("   SYSTEM READY - Press Ctrl+C to stop")
    print("=" * 60)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    main()
