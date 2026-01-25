#!/bin/bash
# Thor Memecoin Sniping Bot - Web GUI Mode Launcher

echo "🌐 Thor Memecoin Sniping Bot - Web GUI"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if Flask is installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo "📥 Installing Flask and dependencies..."
    pip install flask>=2.3.0
else
    echo "✅ Flask already installed"
fi

# Check if other dependencies are installed
if ! python3 -c "import rich" 2>/dev/null; then
    echo "📥 Installing all dependencies..."
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
    read -p "Press Enter after editing .env, or Ctrl+C to exit..."
fi

# Final warning
echo ""
echo "🚨 LIVE TRADING WARNING 🚨"
echo "================================"
echo "This bot uses REAL MONEY on Solana blockchain"
echo "You can LOSE funds - crypto trading is extremely risky"
echo ""
echo "Safety reminders:"
echo "  ✅ Start with minimal funds (e.g., 0.1 SOL)"
echo "  ✅ Set THOR_MAX_POSITION_SIZE=10 in .env"
echo "  ✅ Test thoroughly before using large amounts"
echo ""
echo "🌐 Starting Web GUI..."
echo "   Open your browser to: http://localhost:5001"
echo ""
echo "Press Ctrl+C in this terminal to stop the server"
echo ""
sleep 2

# Launch Web GUI
./venv/bin/python3 web_gui.py
