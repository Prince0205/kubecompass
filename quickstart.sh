#!/bin/bash
# Quick Start Script for KubeCompass Unified App
# This script sets up and runs the complete integrated application on port 8000

set -e  # Exit on error

echo "=========================================="
echo "KubeCompass - Unified App Quick Start"
echo "=========================================="
echo ""

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "❌ ERROR: Python is not installed or not in PATH"
    exit 1
fi

# Check if Node is available
if ! command -v node &> /dev/null; then
    echo "❌ ERROR: Node is not installed or not in PATH"
    exit 1
fi

echo "✓ Python: $(python --version)"
echo "✓ Node: $(node --version)"
echo "✓ NPM: $(npm --version)"
echo ""

# Check MongoDB
echo "Checking MongoDB..."
if ! command -v mongod &> /dev/null; then
    echo "⚠️  WARNING: MongoDB is not in PATH"
    echo "   Make sure MongoDB is running on localhost:27017"
    echo "   You can start it manually: mongod"
    read -p "Press ENTER to continue anyway, or Ctrl+C to cancel..."
else
    echo "✓ MongoDB found"
fi
echo ""

# Build React if needed
if [ ! -d "ui/dist" ] || [ -z "$(ls -A ui/dist 2>/dev/null)" ]; then
    echo "Building React frontend..."
    cd ui
    npm install --silent
    npm run build
    cd ..
    echo "✓ React build complete"
    echo ""
fi

# Install Python dependencies if needed
echo "Checking Python dependencies..."
python -m pip install -q -r requirements.txt || echo "⚠️  Could not auto-install dependencies"
echo ""

# Show startup info
echo "=========================================="
echo "🚀 Starting KubeCompass on Port 8000"
echo "=========================================="
echo ""
echo "Access the app at: http://localhost:8000"
echo ""
echo "To stop the server: Press Ctrl+C"
echo ""
echo "Default Login Credentials:"
echo "  Email: admin@example.com"
echo "  Password: admin123"
echo ""
echo "=========================================="
echo ""

# Start the backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
