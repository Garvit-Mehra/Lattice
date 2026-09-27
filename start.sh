#!/usr/bin/env bash
# ==============================================================================
# LATTICE · IITH Operations Console — 1-Click Startup Script
# MILAN 2026 Lambda Hackathon (Smart Campus Solutions for IIT Hyderabad)
# Boots 3 distinct backends connected to the shared SQLite database:
#   1. Student Portal (Port 8000)      - No Login
#   2. Technician Portal (Port 8001)   - Login Required (technician / tech123)
#   3. Estate Admin Panel (Port 8002)  - Login Required (admin / admin123)
# Benchmark Reference: #LAT-8921
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "=================================================================="
echo "    Starting LATTICE · IITH Operations Console"
echo "=================================================================="

# 1. Detect Python Binary (Prefer active venv or pythonProject/.venv, fallback to python3)
if [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python"
elif [ -x "$PROJECT_DIR/../../.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_DIR/../../.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
else
    echo "[!] Error: Python 3 is required but could not be found."
    exit 1
fi

echo "[*] Using Python: $PYTHON_BIN ($($PYTHON_BIN --version))"

# 2. Check & Install Dependencies
echo "[*] Verifying dependencies..."
$PYTHON_BIN -c "import fastapi, uvicorn, sqlalchemy, pydantic" 2>/dev/null || {
    echo "[*] Installing required packages from requirements.txt..."
    $PYTHON_BIN -m pip install -r requirements.txt
}

# 3. Check & Seed Database
if [ ! -f "backend/kandifix.db" ]; then
    echo "[*] Initializing and seeding IITH campus database with #LAT-8921..."
    PYTHONPATH="$PROJECT_DIR" $PYTHON_BIN -m backend.seed_data
else
    echo "[OK] Shared SQLite database verified at backend/kandifix.db"
fi

# 4. Clean up any existing instances on ports 8000, 8001, 8002
for p in 8000 8001 8002; do
    PID=$(lsof -ti :$p 2>/dev/null || true)
    if [ -n "$PID" ]; then
        echo "[*] Freeing existing process on port $p (PID: $PID)..."
        kill -9 $PID 2>/dev/null || true
    fi
done

# 5. Launch Instructions
echo ""
echo "=================================================================="
echo "  All 3 LATTICE Portals are Live & Connected to Shared DB!"
echo "  ----------------------------------------------------------------"
echo "  Student Portal (No Login):       http://localhost:8000"
echo "  Technician Portal (With Login):  http://localhost:8001"
echo "     ↳ Credentials: technician / tech123"
echo "  Admin Control Panel (With Login): http://localhost:8002"
echo "     ↳ Credentials: admin / admin123"
echo "  ----------------------------------------------------------------"
echo "  Benchmark Ticket Lookup:          #LAT-8921 (Raman 814)"
echo "  Interactive Pitch Deck:           http://localhost:8000/presentation"
echo "  API Docs:                         http://localhost:8000/docs"
echo "=================================================================="
echo "Press Ctrl+C to shut down all 3 backends."
echo ""

# 6. Auto-Open Browser Tabs
(
    sleep 1.8
    if command -v open >/dev/null 2>&1; then
        open "http://localhost:8000"
        sleep 0.4
        open "http://localhost:8001"
        sleep 0.4
        open "http://localhost:8002"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://localhost:8000"
        xdg-open "http://localhost:8001"
        xdg-open "http://localhost:8002"
    fi
) &

# 7. Start the 3 backends with trap for graceful shutdown
export PYTHONPATH="$PROJECT_DIR"

echo "[*] Starting Student Backend on port 8000..."
$PYTHON_BIN -m uvicorn backend.student_app:app --host 0.0.0.0 --port 8000 --reload &
STUDENT_PID=$!

echo "[*] Starting Technician Backend on port 8001..."
$PYTHON_BIN -m uvicorn backend.tech_app:app --host 0.0.0.0 --port 8001 --reload &
TECH_PID=$!

echo "[*] Starting Admin Backend on port 8002..."
$PYTHON_BIN -m uvicorn backend.admin_app:app --host 0.0.0.0 --port 8002 --reload &
ADMIN_PID=$!

cleanup() {
    echo ""
    echo "[*] Shutting down LATTICE backends..."
    kill $STUDENT_PID $TECH_PID $ADMIN_PID 2>/dev/null || true
    wait $STUDENT_PID $TECH_PID $ADMIN_PID 2>/dev/null || true
    echo "[OK] All backends stopped."
}

trap cleanup EXIT INT TERM

wait $STUDENT_PID $TECH_PID $ADMIN_PID
