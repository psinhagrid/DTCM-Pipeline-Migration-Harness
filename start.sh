#!/usr/bin/env bash
# DTCM Pipeline — Demo starter
# Usage: bash start.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Colours ────────────────────────────────────────────────────────────────────
G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; B='\033[1;34m'; NC='\033[0m'
info()  { echo -e "${G}[✓]${NC} $1"; }
warn()  { echo -e "${Y}[!]${NC} $1"; }
error() { echo -e "${R}[✗]${NC} $1"; exit 1; }
step()  { echo -e "\n${B}──> $1${NC}"; }

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   DTCM Pipeline  —  Demo Starter     ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. macOS guard ─────────────────────────────────────────────────────────────
[[ "$(uname)" == "Darwin" ]] || error "This script is macOS-only (uses Terminal.app)."

# ── 2. Homebrew ────────────────────────────────────────────────────────────────
step "Homebrew"
if ! command -v brew &>/dev/null; then
    warn "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Apple Silicon path
    [[ -f /opt/homebrew/bin/brew ]] && eval "$(/opt/homebrew/bin/brew shellenv)"
fi
info "Homebrew $(brew --version | head -1)"

# ── 3. Python 3 ────────────────────────────────────────────────────────────────
step "Python 3"
if ! command -v python3 &>/dev/null; then
    warn "Installing Python 3 via Homebrew..."
    brew install python
fi
info "$(python3 --version)"

# ── 4. Node.js ─────────────────────────────────────────────────────────────────
step "Node.js / npm"
if ! command -v node &>/dev/null; then
    warn "Installing Node.js via Homebrew..."
    brew install node
fi
info "Node $(node --version)  /  npm $(npm --version)"

# ── 4. Bun ─────────────────────────────────────────────────────────────────────
step "Bun"
if ! command -v bun &>/dev/null; then
    warn "Installing Bun..."
    npm install -g bun
fi
info "Bun $(bun --version)"

# ── 5. Python venv + pip requirements ─────────────────────────────────────────
step "Python environment"
VENV="$SCRIPT_DIR/venv"
if [[ ! -d "$VENV" ]]; then
    python3 -m venv "$VENV"
    info "Virtualenv created at $VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"

if ! pip show litellm &>/dev/null; then
    warn "Installing litellm..."
    pip install --quiet litellm
fi
info "Python deps ready  (litellm $(pip show litellm | awk '/Version/{print $2}'))"

# ── 6. Frontend node_modules ───────────────────────────────────────────────────
step "Frontend dependencies"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    warn "Running bun install in frontend/..."
    bun install --cwd "$FRONTEND_DIR"
else
    info "node_modules already present"
fi
info "Frontend deps ready"

# ── 7. Neo4j (Homebrew, no Docker) ────────────────────────────────────────────
step "Neo4j"
if ! command -v neo4j &>/dev/null; then
    warn "Installing Neo4j via Homebrew (this may take a minute)..."
    brew install neo4j
fi
info "Neo4j $(neo4j --version 2>/dev/null | head -1)"

NEO4J_PREFIX="$(brew --prefix neo4j)"
NEO4J_ADMIN="$NEO4J_PREFIX/bin/neo4j-admin"
NEO4J_DATA="$NEO4J_PREFIX/libexec/data"

# Set initial password before first boot (no-op if DB already initialised)
if [[ ! -d "$NEO4J_DATA/databases/neo4j" ]] && [[ -x "$NEO4J_ADMIN" ]]; then
    warn "Setting Neo4j initial password to 'dtcm_local'..."
    "$NEO4J_ADMIN" dbms set-initial-password dtcm_local 2>/dev/null || \
    "$NEO4J_ADMIN" set-initial-password dtcm_local 2>/dev/null || true
fi

# Start (idempotent — already running is fine)
if ! brew services list | grep -E '^neo4j\s+started' &>/dev/null; then
    warn "Starting Neo4j service..."
    brew services start neo4j
    echo "   Waiting 10 s for Neo4j to be ready..."
    sleep 10
else
    info "Neo4j service already running"
fi
info "Neo4j  →  bolt://localhost:7687  /  http://localhost:7474"

# ── 8. .env ────────────────────────────────────────────────────────────────────
step ".env"
if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
    cp "$SCRIPT_DIR/.env.sample" "$SCRIPT_DIR/.env"
    warn ".env created from .env.sample — open it and replace YOUR_API_KEY_HERE with your Anthropic key, then re-run."
    exit 0
fi
if grep -q "YOUR_API_KEY_HERE" "$SCRIPT_DIR/.env"; then
    error "ANTHROPIC_API_KEY not set. Edit .env, replace YOUR_API_KEY_HERE, then re-run bash start.sh"
fi
info ".env ready"

# ── 9. Open 3 Terminal windows ─────────────────────────────────────────────────
step "Launching services in separate Terminal windows"

# Write a tiny launcher for each service so we don't fight quote escaping.
LAUNCHER_DIR="$(mktemp -d)"
trap 'rm -rf "$LAUNCHER_DIR"' EXIT

# Backend
cat > "$LAUNCHER_DIR/backend.sh" <<BASH
#!/bin/bash
source '$VENV/bin/activate'
cd '$SCRIPT_DIR'
echo '=== DTCM Backend (port 8001) ==='
uvicorn main:app --reload --port 8001
BASH

# LiteLLM
cat > "$LAUNCHER_DIR/litellm.sh" <<BASH
#!/bin/bash
source '$VENV/bin/activate'
cd '$SCRIPT_DIR'
echo '=== LiteLLM (port 4000) ==='
litellm --config rlm/litellm_config.yaml --port 4000
BASH

# Frontend
if command -v bun &>/dev/null; then
    FRONTEND_EXEC="bun dev"
else
    FRONTEND_EXEC="npx vite dev --port 8080"
fi
cat > "$LAUNCHER_DIR/frontend.sh" <<BASH
#!/bin/bash
cd '$FRONTEND_DIR'
echo '=== DTCM Frontend (port 8080) ==='
$FRONTEND_EXEC
BASH

chmod +x "$LAUNCHER_DIR/backend.sh" "$LAUNCHER_DIR/litellm.sh" "$LAUNCHER_DIR/frontend.sh"

open_terminal() {
    local script="$1"
    osascript -e "tell application \"Terminal\" to do script \"$script\"" \
              -e "tell application \"Terminal\" to activate" &>/dev/null
}

open_terminal "$LAUNCHER_DIR/backend.sh"
sleep 0.4
open_terminal "$LAUNCHER_DIR/litellm.sh"
sleep 0.4
open_terminal "$LAUNCHER_DIR/frontend.sh"

# Give launchers a moment to read the files before the trap cleans up.
sleep 3

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Three Terminal windows launched!                ║"
echo "║                                                  ║"
echo "║  Backend  → http://localhost:8001                ║"
echo "║  LiteLLM  → http://localhost:4000                ║"
echo "║  Frontend → http://localhost:8080                ║"
echo "║  Neo4j    → http://localhost:7474                ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
