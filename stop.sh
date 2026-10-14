#!/usr/bin/env bash
# Stop all VISHWAS services
echo "Stopping VISHWAS services..."
pkill -f "uvicorn app.main:app" 2>/dev/null && echo "✓ Backend stopped" || echo "  Backend was not running"
pkill -f "vite" 2>/dev/null && echo "✓ Frontend stopped" || echo "  Frontend was not running"
echo "Done."
