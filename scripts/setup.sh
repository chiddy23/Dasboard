#!/bin/bash

# JustInsurance Student Dashboard - Unix/Mac Setup Script

echo ""
echo "========================================"
echo "JustInsurance Student Dashboard Setup"
echo "========================================"
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.11+ from https://python.org"
    exit 1
fi

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "ERROR: Node.js is not installed"
    echo "Please install Node.js 20+ from https://nodejs.org"
    exit 1
fi

# Get the script's directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "[1/5] Creating Python virtual environment..."
cd backend
python3 -m venv venv

echo "[2/5] Activating virtual environment and installing Python dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo "[3/5] Installing Node.js dependencies..."
cd ../frontend
npm install

echo "[4/5] Copying environment file..."
cd ..
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "IMPORTANT: Edit .env file with your Absorb API credentials!"
    echo ""
fi

echo "[5/5] Creating session directory..."
mkdir -p backend/flask_session

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "To start the application:"
echo ""
echo "1. Edit .env with your Absorb API credentials"
echo ""
echo "2. Start backend (in a new terminal):"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   python app.py"
echo ""
echo "3. Start frontend (in another terminal):"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "4. Open http://localhost:3000"
echo ""
