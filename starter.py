import subprocess
import sys
import time
import os
from pathlib import Path

ROOT = Path(__file__).parent
VENV_PYTHON = ROOT / "venv" / "bin" / "uvicorn"
VENV_BIN = ROOT / "venv" / "bin"

def run(name, cmd, cwd=None, env=None):
    e = {**os.environ, **(env or {})}
    e["PATH"] = f"{VENV_BIN}:{e['PATH']}"
    p = subprocess.Popen(cmd, cwd=cwd or ROOT, env=e, shell=False)
    print(f"[{name}] started (pid {p.pid})")
    return p

print("Starting DTCM Pipeline...\n")

neo4j = subprocess.run(["docker", "start", "neo4j"], capture_output=True, text=True)
if neo4j.returncode == 0:
    print("[Neo4j] started")
else:
    print(f"[Neo4j] {neo4j.stderr.strip() or 'already running / check Docker'}")

time.sleep(2)

backend  = run("Backend",  ["uvicorn", "main:app", "--reload", "--port", "8001"])
frontend = run("Frontend", ["bun", "dev"], cwd=ROOT / "frontend")

print("\nRunning:")
print("  Backend  → http://localhost:8001")
print("  Frontend → http://localhost:8080")
print("\nCtrl+C to stop all.\n")

try:
    backend.wait()
except KeyboardInterrupt:
    print("\nShutting down...")
    backend.terminate()
    frontend.terminate()
    sys.exit(0)
