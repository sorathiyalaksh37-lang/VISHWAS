#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# VISHWAS — One-command setup & start script (Mac / Linux)
# Usage: bash setup_and_run.sh
# ─────────────────────────────────────────────────────────────────

set -e

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   VISHWAS — AI Voice Fraud Detection Setup   ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Check prerequisites ───────────────────────────────────────────
check_command() {
  if ! command -v "$1" &>/dev/null; then
    echo "❌  '$1' is not installed. Please install it and re-run."
    echo "    $2"
    exit 1
  fi
}

check_command python3 "https://python.org/downloads"
check_command node   "https://nodejs.org"
check_command npm    "https://nodejs.org"

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓  Python $PYTHON_VERSION detected"
echo "✓  Node $(node --version) detected"
echo ""

# ── Backend setup ─────────────────────────────────────────────────
echo "▶  Setting up backend..."
cd backend

# Create virtualenv if missing
if [ ! -d "venv" ]; then
  echo "   Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate

# Install / upgrade pip quietly
pip install --upgrade pip -q

# Install minimal requirements (mock mode, no heavy ML models)
echo "   Installing Python packages (mock mode, no heavy ML needed)..."
pip install -r requirements_minimal.txt -q

# Create .env from example if not present
if [ ! -f ".env" ]; then
  echo "   Creating backend .env..."
  cp .env.example .env
  # Set mock mode
  sed -i.bak 's/ANALYSIS_MODE=real/ANALYSIS_MODE=mock/' .env
  sed -i.bak 's/ENABLE_VOICE_LAYER=true/ENABLE_VOICE_LAYER=false/' .env
  # Generate a secure random secret key
  SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  sed -i.bak "s/SECRET_KEY=your-secret-key-here-change-in-production/SECRET_KEY=$SECRET/" .env
  rm -f .env.bak
  echo "   ✓ backend/.env created"
fi

deactivate
cd ..

# ── Frontend setup ─────────────────────────────────────────────────
echo ""
echo "▶  Setting up frontend..."
cd vishwas-frontend

npm install -q

if [ ! -f ".env" ]; then
  echo "   Creating frontend .env..."
  echo "VITE_API_URL=http://localhost:8000/api/v1" > .env
  echo "   ✓ vishwas-frontend/.env created"
fi

cd ..

# ── Start both services ───────────────────────────────────────────
echo ""
echo "▶  Starting services..."

# Kill any old instances
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

# Start backend
echo "   Starting backend on http://localhost:8000 ..."
cd backend
source venv/bin/activate
nohup python -m uvicorn app.main:app --port 8000 --host 0.0.0.0 > /tmp/vishwas_backend.log 2>&1 &
BACKEND_PID=$!
deactivate
cd ..

# Wait for backend to be ready
echo "   Waiting for backend to start..."
for i in $(seq 1 15); do
  if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "   ✓ Backend is up! (PID: $BACKEND_PID)"
    break
  fi
  sleep 1
done

# Start frontend
echo "   Starting frontend on http://localhost:5173 ..."
cd vishwas-frontend
nohup npm run dev > /tmp/vishwas_frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

sleep 3

# ── Done ──────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║              ✅  VISHWAS is LIVE!            ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  Dashboard  →  http://localhost:5173         ║"
echo "║  API Docs   →  http://localhost:8000/docs    ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  Logs:                                       ║"
echo "║   Backend  → /tmp/vishwas_backend.log        ║"
echo "║   Frontend → /tmp/vishwas_frontend.log       ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  To stop: bash stop.sh                       ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "   NOTE: Running in MOCK mode."
echo "   No AI models are downloaded. Analysis is simulated."
echo "   To enable real ASR, set ANALYSIS_MODE=real in backend/.env"
echo ""
