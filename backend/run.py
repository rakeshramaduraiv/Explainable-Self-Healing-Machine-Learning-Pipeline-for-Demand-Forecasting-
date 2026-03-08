import subprocess, sys, os

BASE = os.path.dirname(os.path.abspath(__file__))
PY   = sys.executable

def run(cmd, label):
    print(f"\n{'='*50}\n{label}\n{'='*50}")
    result = subprocess.run([PY] + cmd, cwd=BASE)
    if result.returncode != 0:
        print(f"[FAILED] {label}")
        sys.exit(1)
    print(f"[DONE] {label}")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ("all", "pipeline"):
        run(["main.py"], "Phase 1 Pipeline")

    if mode in ("all", "verify"):
        run(["verify_system.py"], "System Verification")

    if mode in ("all", "test"):
        subprocess.run([PY, "-m", "pytest", "tests/", "-v"], cwd=BASE)

    if mode in ("all", "viz"):
        run(["generate_visualizations.py"], "Generate Visualizations")

    if mode in ("all", "dashboard"):
        print("\n" + "="*50)
        print("Launching Dashboard → http://localhost:8501")
        print("="*50)
        subprocess.run([PY, "-m", "streamlit", "run", "dashboard.py"], cwd=BASE)
