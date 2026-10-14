#!/usr/bin/env python3
"""
VISHWAS Quick-Start Launcher
Starts backend (FastAPI :8000) and frontend (Vite :5173) in < 2 seconds.
"""
import os
import sys
import time
import subprocess
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

def free_port(port: int):
    """Terminate any process listening on given port."""
    try:
        out = subprocess.check_output(["lsof", "-ti", f":{port}"], text=True).strip()
        if out:
            pids = out.split()
            for pid in pids:
                try:
                    os.kill(int(pid), 9)
                except OSError:
                    pass
    except Exception:
        pass

def wait_for_url(url: str, timeout: float = 6.0) -> bool:
    """Poll URL until 200 OK or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VISHWAS-Launcher"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status in (200, 304):
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False

def main():
    print("🛡️  Starting VISHWAS Full Stack...")
    
    # 1. Clean up ports
    print("→ Freeing ports 8000 & 5173...")
    free_port(8000)
    free_port(5173)
    time.sleep(0.3)

    # 2. Determine Python interpreter
    python_bin = sys.executable

    # 3. Start Backend
    print("→ Starting Backend (FastAPI on http://127.0.0.1:8000)...")
    backend_log = open(LOGS_DIR / "backend.log", "w")
    backend_proc = subprocess.Popen(
        [python_bin, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=str(ROOT_DIR / "backend"),
        stdin=subprocess.DEVNULL,
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    (LOGS_DIR / "backend.pid").write_text(str(backend_proc.pid))

    # 4. Start Frontend
    print("→ Starting Frontend (Vite on http://localhost:5173)...")
    frontend_log = open(LOGS_DIR / "frontend.log", "w")
    
    # Prefer node with vite.js
    node_vite_bin = ROOT_DIR / "vishwas-frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    if node_vite_bin.exists():
        frontend_cmd = ["node", str(node_vite_bin), "--host", "0.0.0.0"]
    else:
        frontend_cmd = ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

    frontend_proc = subprocess.Popen(
        frontend_cmd,
        cwd=str(ROOT_DIR / "vishwas-frontend"),
        stdin=subprocess.DEVNULL,
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    (LOGS_DIR / "frontend.pid").write_text(str(frontend_proc.pid))

    # 5. Fast verification
    print("→ Verifying services...")
    backend_ok = wait_for_url("http://127.0.0.1:8000/api/v1/health", timeout=5.0)
    frontend_ok = wait_for_url("http://localhost:5173", timeout=5.0)

    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if backend_ok and frontend_ok:
        print("🚀 VISHWAS Full Stack is up and ready to use!")
    else:
        print("⚠️  VISHWAS services started (check logs if any issue):")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  📊 Frontend Dashboard: http://localhost:5173")
    print("  🔧 Backend API:        http://127.0.0.1:8000")
    print("  📖 Swagger Docs:       http://127.0.0.1:8000/docs")
    print()
    print("  Default Credentials:")
    print("    Admin: admin@vishwas.local / admin123")
    print("    Demo:  demo@example.com    / demo123")
    print()
    print("  Logs:")
    print("    Backend:  tail -f logs/backend.log")
    print("    Frontend: tail -f logs/frontend.log")
    print()
    print("  To stop: python3 stop.py  or  ./stop.sh")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    main()
