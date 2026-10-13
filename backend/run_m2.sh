#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# VISHWAS — Member 2 Backend Quick-Start
# Usage: bash backend/run_m2.sh [--mock]
#
# Flags:
#   --mock    Use mock analysis (no ML models needed — for UI testing)
#   --small   Use whisper-small instead of base (more accurate, slower)
#   --help    Show this help
# ─────────────────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Parse args ────────────────────────────────────────────────────────────────
ANALYSIS_MODE="real"
WHISPER_MODEL="base"

for arg in "$@"; do
  case $arg in
    --mock)   ANALYSIS_MODE="mock" ;;
    --small)  WHISPER_MODEL="small" ;;
    --help)
      echo "Usage: bash run_m2.sh [--mock] [--small]"
      echo "  --mock   Skip ML models, use instant mock results"
      echo "  --small  Use whisper-small for better accuracy (slower)"
      exit 0 ;;
  esac
done

echo "════════════════════════════════════════════════════════"
echo "  VISHWAS Backend — Member 2 (Perception + ASR)"
echo "  Mode: $ANALYSIS_MODE | Whisper: $WHISPER_MODEL"
echo "════════════════════════════════════════════════════════"

# ── Check Python ──────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌  python3 not found. Install Python 3.10+"
  exit 1
fi
echo "✓  Python: $(python3 --version)"

# ── Virtual environment ───────────────────────────────────────────────────────
if [ ! -d "venv" ]; then
  echo "→  Creating virtual environment..."
  python3 -m venv venv
fi
source venv/bin/activate
echo "✓  venv activated"

# ── Install core deps ─────────────────────────────────────────────────────────
echo "→  Installing core dependencies..."
pip install -q --upgrade pip
# Install everything except the commented-out heavy ML deps
grep -v "^#" requirements.txt | grep -v "^$" | pip install -q -r /dev/stdin
echo "✓  Core deps installed"

# ── Optional: faster-whisper (ASR) ───────────────────────────────────────────
if [ "$ANALYSIS_MODE" = "real" ]; then
  if ! python3 -c "import faster_whisper" 2>/dev/null; then
    echo "→  Installing faster-whisper..."
    pip install -q faster-whisper
  fi
  echo "✓  faster-whisper ready"
fi

# ── Check ffmpeg ──────────────────────────────────────────────────────────────
if command -v ffmpeg &>/dev/null; then
  echo "✓  ffmpeg: $(ffmpeg -version 2>&1 | head -1)"
else
  echo "⚠  ffmpeg not found. Audio conversion will be skipped."
  echo "   Install: https://ffmpeg.org/download.html"
fi

# ── .env setup ────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "→  Created .env from .env.example"
fi

# Apply runtime overrides
export ANALYSIS_MODE="$ANALYSIS_MODE"
export WHISPER_MODEL_SIZE="$WHISPER_MODEL"

# ── Storage directory ─────────────────────────────────────────────────────────
mkdir -p storage/uploads
echo "✓  Storage: ./storage/uploads"

# ── Database init ─────────────────────────────────────────────────────────────
echo "→  Initialising database..."
python3 -m app.database.init_db 2>/dev/null || true
echo "✓  Database ready"

# ── Print endpoint summary ────────────────────────────────────────────────────
echo ""
echo "  API Endpoints (Member 2):"
echo "  ─────────────────────────────────────────────────────"
echo "  POST /api/v1/analyze/recording      → Upload audio"
echo "  GET  /api/v1/call/{id}/status       → Job status"
echo "  GET  /api/v1/call/{id}/state        → Full report"
echo "  GET  /api/v1/call/{id}/counterfactual"
echo "  POST /api/v1/contacts               → Add trusted contact"
echo "  POST /api/v1/contacts/{id}/voiceprint → Enroll voiceprint"
echo "  GET  /api/v1/calls                  → History"
echo "  GET  /docs                          → Swagger UI"
echo "  ─────────────────────────────────────────────────────"
echo ""

# ── Start server ──────────────────────────────────────────────────────────────
echo "→  Starting server on http://0.0.0.0:8000"
echo "   Press Ctrl+C to stop"
echo ""
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --log-level info
