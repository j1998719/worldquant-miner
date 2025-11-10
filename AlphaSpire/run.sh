#!/bin/bash
# Quick start script for AlphaSpire

echo "🚀 Starting AlphaSpire - Iterative Alpha Miner"
echo ""

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
    echo "⚠️  Warning: Ollama doesn't seem to be running"
    echo "   Please start Ollama first: ollama serve"
    echo ""
    read -p "Press Enter to continue anyway, or Ctrl+C to abort..."
fi

# Load the model (start and exit to preload it)
echo "🔄 Loading model gemma3:1b..."
echo "/bye" | ollama run gemma3:1b > /dev/null 2>&1
echo "✅ Model loaded and ready"
echo ""

# Check if config exists
if [ ! -f "config.yaml" ]; then
    echo "❌ Error: config.yaml not found"
    echo "   Please create config.yaml first"
    exit 1
fi

# Check if dependencies are installed
echo "🔍 Checking dependencies..."
if ! python3 -c "import requests, yaml, pandas" 2>/dev/null; then
    echo "⚠️  Missing dependencies detected"
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        echo "   Please run manually: pip install -r requirements.txt"
        exit 1
    fi
    echo "✅ Dependencies installed"
fi

# Run the miner
python3 alpha_miner.py "$@"

