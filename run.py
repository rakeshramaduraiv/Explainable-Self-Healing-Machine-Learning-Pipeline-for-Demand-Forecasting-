"""
run.py - Single command to start the full app
Usage: python run.py
"""
import subprocess, sys, os, time, threading, webbrowser

ROOT     = os.path.dirname(os.path.abspath(__file__))
FRONTEND = os.path.join(ROOT, "frontend")
VENV_PY  = os.path.join(ROOT, "venv", "Scripts", "python.exe")
PYTHON   = VENV_PY if os.path.exists(VENV_PY) else sys.executable

def stream(proc, tag):
    for line in iter(proc.stdout.readline, b""):
        txt = line.decode(errors="ignore").rstrip()
        if txt: print(f"  [{tag}] {txt}")

def backend():
    print("[1/2] Starting FastAPI backend on http://localhost:8000")
    p = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "backend.main:app",
         "--reload", "--port", "8000", "--host", "0.0.0.0"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    stream(p, "API")

def frontend():
    nm = os.path.join(FRONTEND, "node_modules")
    if not os.path.exists(nm):
        print("[2/2] Installing npm packages (first time only)...")
        subprocess.run("npm install", cwd=FRONTEND, shell=True)
    print("[2/2] Starting React frontend on http://localhost:5173")
    p = subprocess.Popen(
        "npm run dev", cwd=FRONTEND,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True
    )
    stream(p, "UI")

if __name__ == "__main__":
    print()
    print("=" * 55)
    print("   Real-Time Demand Forecasting App")
    print("=" * 55)
    print("   Frontend  :  http://localhost:5173")
    print("   Backend   :  http://localhost:8000")
    print("   API Docs  :  http://localhost:8000/docs")
    print("=" * 55)
    print("   Press Ctrl+C to stop both servers")
    print("=" * 55)
    print()

    t1 = threading.Thread(target=backend,  daemon=True)
    t2 = threading.Thread(target=frontend, daemon=True)
    t1.start()
    time.sleep(2)
    t2.start()
    time.sleep(3)
    webbrowser.open("http://localhost:5173")

    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")
