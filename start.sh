#!/bin/bash

# Personal Finance Dashboard - Start Script
# This script starts both backend and frontend servers

echo "🚀 Starting Personal Finance Dashboard..."
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install it first."
    exit 1
fi

# Start Backend
echo -e "${BLUE}📦 Setting up backend...${NC}"
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Start backend server in background
echo -e "${GREEN}✓ Starting backend server on http://localhost:8000${NC}"
python main.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Start Frontend
cd ../frontend
echo -e "${GREEN}✓ Starting frontend server on http://localhost:3000${NC}"
python3 -m http.server 3000 &
FRONTEND_PID=$!

echo ""
echo "════════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ Dashboard is running!${NC}"
echo ""
echo "   📊 Dashboard:  http://localhost:3000"
echo "   📡 API:        http://localhost:8000"
echo "   📚 API Docs:   http://localhost:8000/docs"
echo ""
echo "   Press Ctrl+C to stop all servers"
echo "════════════════════════════════════════════════════════════"

# Handle shutdown
cleanup() {
    echo ""
    echo "Shutting down servers..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup INT TERM

# Wait for processes
wait

