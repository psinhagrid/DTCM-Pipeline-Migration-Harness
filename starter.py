import subprocess
import sys
import time
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
VENV_PYTHON = ROOT / "venv" / "bin" / "uvicorn"
VENV_BIN = ROOT / "venv" / "bin"

def run(name, cmd, cwd=None, env=None):
    e = {**os.environ, **(env or {})}
    e["PATH"] = f"{VENV_BIN}:{e['PATH']}"
    p = subprocess.Popen(cmd, cwd=cwd or ROOT, env=e, shell=False)
    print(f"[{name}] started (pid {p.pid})")
    return p

print("Starting DTCM Pipeline...\n")

# Start Neo4j via Homebrew services (no Docker required)
neo4j_status = subprocess.run(
    ["brew", "services", "list"], capture_output=True, text=True
)
already_running = "neo4j" in neo4j_status.stdout and "started" in neo4j_status.stdout

if already_running:
    print("[Neo4j] already running")
else:
    result = subprocess.run(["brew", "services", "start", "neo4j"], capture_output=True, text=True)
    if result.returncode == 0:
        print("[Neo4j] started via Homebrew")
        print("[Neo4j] waiting 8s for Neo4j to be ready...")
        time.sleep(8)
    else:
        print(f"[Neo4j] failed to start: {result.stderr.strip()}")
        print("[Neo4j] continuing anyway — graph features may be unavailable")

time.sleep(2)

litellm  = run("LiteLLM",  [str(VENV_BIN / "litellm"), "--config", "rlm/litellm_config.yaml", "--port", "4000"])
print("[LiteLLM] waiting 3s to be ready...")
time.sleep(3)

backend  = run("Backend",  [str(VENV_BIN / "uvicorn"), "main:app", "--reload", "--port", "8001"])
frontend = run("Frontend", ["npm", "run", "dev"], cwd=ROOT / "frontend")

print("\nRunning:")
print("  LiteLLM  → http://localhost:4000")
print("  Backend  → http://localhost:8001")
print("  Frontend → http://localhost:8080")
print("\nCtrl+C to stop all.\n")

try:
    backend.wait()
except KeyboardInterrupt:
    print("\nShutting down...")
    backend.terminate()
    litellm.terminate()
    frontend.terminate()
    sys.exit(0)
