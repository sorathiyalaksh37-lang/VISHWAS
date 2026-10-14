#!/usr/bin/env python3
"""
VISHWAS Quick Stop
Cleanly stops backend and frontend services.
"""
import os
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
LOGS_DIR = ROOT_DIR / "logs"

def free_port(port: int):
    try:
        out = subprocess.check_output(["lsof", "-ti", f":{port}"], text=True).strip()
        if out:
            for pid in out.split():
                try:
                    os.kill(int(pid), 9)
                except OSError:
                    pass
    except Exception:
        pass

def main():
    print("🛑 Stopping VISHWAS services...")
    for pid_file in ["backend.pid", "frontend.pid"]:
        pf = LOGS_DIR / pid_file
        if pf.exists():
            try:
                pid = int(pf.read_text().strip())
                os.kill(pid, 9)
            except OSError:
                pass
            try:
                pf.unlink()
            except OSError:
                pass

    free_port(8000)
    free_port(5173)
    print("✓ All VISHWAS services stopped cleanly.")

if __name__ == "__main__":
    main()
