#!/usr/bin/env bash
# ==============================================================================
# LATTICE · IITH Operations Console — 1-Click Startup Script
# MILAN 2026 Lambda Hackathon (Smart Campus Solutions for IIT Hyderabad)
# Unified single-port deployment on Port 8000:
#   1. Student Portal:      http://localhost:8000/ (or /student)
#   2. Technician Portal:   http://localhost:8000/tech (technician / tech123)
#   3. Estate Admin Panel:  http://localhost:8000/admin (admin / admin123)
#   4. Pitch Deck:          http://localhost:8000/presentation
#   5. Swagger API Docs:    http://localhost:8000/docs
# Benchmark Reference: #LAT-8921
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# ------------------------------------------------------------------------------
# 0. CLI Options & Defaults
# ------------------------------------------------------------------------------
AUTO_OPEN=true
RESEED=false
RELOAD=true
MULTI_PORT=false

for arg in "$@"; do
    case "$arg" in
        --no-open|--no-browser|--headless)
            AUTO_OPEN=false
            ;;
        --reseed|-r)
            RESEED=true
            ;;
        --no-reload)
            RELOAD=false
            ;;
        --multi-port)
            MULTI_PORT=true
            ;;
        --help|-h)
            echo "Usage: ./start.sh [options]"
            echo "Options:"
            echo "  --no-open, --no-browser  Do not auto-open browser tabs"
            echo "  --reseed, -r             Force reseed database before starting"
            echo "  --no-reload              Run without uvicorn auto-reload"
            echo "  --multi-port             Run separate processes on 8000, 8001, 8002 (legacy)"
            echo "  --help, -h               Show this help message"
            exit 0
            ;;
    esac
done

# Disable auto-open in Docker, CI, or SSH sessions
if [ -f /.dockerenv ] || [ -n "$CI" ] || [ -n "$SSH_CLIENT" ]; then
    AUTO_OPEN=false
fi

echo "=================================================================="
echo "    Starting LATTICE · IITH Operations Console"
echo "=================================================================="

# ------------------------------------------------------------------------------
# 1. Detect Python Binary
# ------------------------------------------------------------------------------
if [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python"
elif [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
elif [ -x "$PROJECT_DIR/../.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_DIR/../.venv/bin/python"
elif [ -x "$PROJECT_DIR/../../.venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_DIR/../../.venv/bin/python"
elif [ -x "/Users/garvitmehra/pythonProject/.venv/bin/python" ]; then
    PYTHON_BIN="/Users/garvitmehra/pythonProject/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
else
    echo "[!] Error: Python 3 is required but could not be found."
    exit 1
fi

echo "[*] Using Python: $PYTHON_BIN ($($PYTHON_BIN --version))"

# ------------------------------------------------------------------------------
# 2. Check & Install Dependencies
# ------------------------------------------------------------------------------
echo "[*] Verifying dependencies..."
$PYTHON_BIN -c "import fastapi, uvicorn, sqlalchemy, pydantic, watchfiles" 2>/dev/null || {
    echo "[*] Installing required packages from requirements.txt..."
    $PYTHON_BIN -m pip install -r requirements.txt
}

# ------------------------------------------------------------------------------
# 3. Check & Seed Database
# ------------------------------------------------------------------------------
if [ "$RESEED" = "true" ] || [ ! -f "backend/kandifix.db" ]; then
    echo "[*] Initializing and seeding IITH campus database with #LAT-8921..."
    PYTHONPATH="$PROJECT_DIR" $PYTHON_BIN -m backend.seed_data
else
    echo "[OK] Shared SQLite database verified at backend/kandifix.db"
fi

# ------------------------------------------------------------------------------
# 4. Clean up any existing instances on port 8000 (and 8001, 8002 if multi-port)
# ------------------------------------------------------------------------------
PORTS_TO_CHECK="8000"
if [ "$MULTI_PORT" = "true" ]; then
    PORTS_TO_CHECK="8000 8001 8002"
fi

for p in $PORTS_TO_CHECK; do
    PIDS=$(lsof -ti :$p 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo "[*] Freeing existing process on port $p..."
        kill -9 $PIDS 2>/dev/null || true
    fi
done

# ------------------------------------------------------------------------------
# 5. Launch Instructions Banner
# ------------------------------------------------------------------------------
echo ""
echo "=================================================================="
if [ "$MULTI_PORT" = "true" ]; then
    echo "  LATTICE Portals Live (Multi-Port Mode)!"
    echo "  ----------------------------------------------------------------"
    echo "  Student Portal (No Login):       http://localhost:8000"
    echo "  Technician Portal (With Login):  http://localhost:8001"
    echo "     ↳ Credentials: technician / tech123"
    echo "  Admin Control Panel (With Login): http://localhost:8002"
    echo "     ↳ Credentials: admin / admin123"
else
    echo "  LATTICE Portals Live on Unified Single Port (8000)!"
    echo "  ----------------------------------------------------------------"
    echo "  Student Portal (No Login):       http://localhost:8000/ (or /student)"
    echo "  Technician Portal (With Login):  http://localhost:8000/tech"
    echo "     ↳ Credentials: technician / tech123"
    echo "  Admin Control Panel (With Login): http://localhost:8000/admin"
    echo "     ↳ Credentials: admin / admin123"
fi
echo "  ----------------------------------------------------------------"
echo "  Benchmark Ticket Lookup:          #LAT-8921 (Raman 814)"
echo "  Interactive Pitch Deck:           http://localhost:8000/presentation"
echo "  API Documentation (Swagger):      http://localhost:8000/docs"
echo "=================================================================="
echo "Press Ctrl+C to shut down."
echo ""

# ------------------------------------------------------------------------------
# 6. Auto-Open Browser (Background)
# ------------------------------------------------------------------------------
if [ "$AUTO_OPEN" = "true" ]; then
    (
        sleep 1.5
        if command -v open >/dev/null 2>&1; then
            open "http://localhost:8000"
        elif command -v xdg-open >/dev/null 2>&1; then
            xdg-open "http://localhost:8000"
        fi
    ) &
fi

# ------------------------------------------------------------------------------
# 7. Start Backend with Reliable Shutdown Trap
# ------------------------------------------------------------------------------
export PYTHONPATH="$PROJECT_DIR"

RELOAD_ARGS=""
if [ "$RELOAD" = "true" ]; then
    RELOAD_ARGS="--reload --reload-exclude *.db* --reload-exclude *.db-wal --reload-exclude *.db-shm --reload-exclude *.log"
fi

if [ "$MULTI_PORT" = "true" ]; then
    echo "[*] Starting Student Backend on port 8000..."
    $PYTHON_BIN -m uvicorn backend.student_app:app --host 0.0.0.0 --port 8000 $RELOAD_ARGS &
    PID1=$!

    echo "[*] Starting Technician Backend on port 8001..."
    $PYTHON_BIN -m uvicorn backend.tech_app:app --host 0.0.0.0 --port 8001 $RELOAD_ARGS &
    PID2=$!

    echo "[*] Starting Admin Backend on port 8002..."
    $PYTHON_BIN -m uvicorn backend.admin_app:app --host 0.0.0.0 --port 8002 $RELOAD_ARGS &
    PID3=$!

    cleanup() {
        trap - EXIT INT TERM
        echo ""
        echo "[*] Shutting down LATTICE backends..."
        kill -TERM $PID1 $PID2 $PID3 2>/dev/null || true
        sleep 0.5
        for p in 8000 8001 8002; do
            PIDS=$(lsof -ti :$p 2>/dev/null || true)
            if [ -n "$PIDS" ]; then
                kill -9 $PIDS 2>/dev/null || true
            fi
        done
        wait $PID1 $PID2 $PID3 2>/dev/null || true
        echo "[OK] All backends stopped cleanly."
    }
    trap cleanup INT TERM EXIT
    wait $PID1 $PID2 $PID3 || true
else
    # Unified Single-Port Mode on Port 8000
    cleanup() {
        trap - EXIT INT TERM
        echo ""
        echo "[*] Shutting down LATTICE server..."
        PIDS=$(lsof -ti :8000 2>/dev/null || true)
        if [ -n "$PIDS" ]; then
            kill -9 $PIDS 2>/dev/null || true
        fi
        echo "[OK] Server stopped cleanly."
    }
    trap cleanup INT TERM EXIT

    exec $PYTHON_BIN -m uvicorn backend.student_app:app --host 0.0.0.0 --port 8000 $RELOAD_ARGS
fi
