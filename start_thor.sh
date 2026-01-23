#!/bin/bash
# Thor Memecoin Sniping Bot - Quick Start Script

echo "🔨 Thor Memecoin Sniping Bot"
echo "================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if dependencies are installed
if ! python3 -c "import rich" 2>/dev/null; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
else
    echo "✅ Dependencies already installed"
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  WARNING: .env file not found!"
    echo "📝 Creating .env from template..."
    cp .env.example .env
    echo ""
    echo "🔴 CRITICAL: You must edit .env with your wallet credentials!"
    echo "   nano .env"
    echo ""
    echo "Required fields:"
    echo "  - THOR_WALLET_PRIVATE_KEY"
    echo "  - THOR_WALLET_ADDRESS"
    echo ""
    read -p "Press Enter after editing .env, or Ctrl+C to exit..."
fi

# Final warning
echo ""
echo "🚨 LIVE TRADING WARNING 🚨"
echo "================================"
echo "This bot uses REAL MONEY on Solana blockchain"
echo "You can LOSE funds - crypto trading is extremely risky"
echo ""
echo "Safety checklist:"
echo "  ✅ Start with minimal funds (e.g., 0.1 SOL)"
echo "  ✅ Set THOR_MAX_POSITION_SIZE=10 in .env"
echo "  ✅ Test emergency stop (s key) immediately"
echo "  ✅ Monitor first 10 cycles closely"
echo ""
read -p "Type 'START' to launch Thor: " confirm

if [ "$confirm" != "START" ]; then
    echo "Cancelled. Edit .env and run this script again."
    exit 0
fi

echo ""
echo "🚀 Launching Thor..."
echo ""
python3 main.py
