import subprocess
import sys
import time
import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent
VENV_BIN = ROOT / "venv" / "bin"

load_dotenv(ROOT / ".env")

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
litellm  = run("LiteLLM",  ["litellm", "--config", "rlm/litellm_config.yaml", "--port", "4000"])

frontend_cmd = ["bun", "dev"] if shutil.which("bun") else ["npx", "vite", "dev", "--port", "8080"]
frontend = run("Frontend", frontend_cmd, cwd=ROOT / "frontend")

print("\nRunning:")
print("  Backend  → http://localhost:8001")
print("  LiteLLM  → http://localhost:4000")
print("  Frontend → http://localhost:8080")
print("\nCtrl+C to stop all.\n")

try:
    backend.wait()
except KeyboardInterrupt:
    print("\nShutting down...")
    for p in (backend, litellm, frontend):
        p.terminate()
    sys.exit(0)
