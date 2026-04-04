#!/bin/bash

# US Debt Clock Startup Script

set -e

echo "===== US Debt Clock Startup ====="
echo

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found"
    exit 1
fi

# Check .env
if [ ! -f .env ]; then
    echo "ERROR: .env not found"
    echo "Copy .env.example to .env and add your FRED_KEY"
    exit 1
fi

# Load env
set -a
source .env
set +a

# Check FRED_KEY
if [ -z "$FRED_KEY" ] || [ "$FRED_KEY" = "your_fred_api_key_here" ]; then
    echo "ERROR: FRED_KEY not configured in .env"
    exit 1
fi

echo "Python: $(python3 --version)"
echo "FRED_KEY: ${FRED_KEY:0:10}..."
echo

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
    echo "✓ Dependencies installed"
else
    source venv/bin/activate
fi

echo

# Initialize database
if [ ! -f debt_clock.db ]; then
    echo "Initializing database..."
    python3 -c "from data_collector import Database; from pathlib import Path; Database(Path('debt_clock.db'))"
    echo "✓ Database initialized"
fi

echo

# Test API connectivity
echo "Testing API connectivity..."
python3 -c "
import asyncio
from data_collector import TreasuryClient, FredClient

async def test():
    async with TreasuryClient() as treasury:
        result = await treasury.get_national_debt()
        if result:
            print(f'  ✓ Treasury API: \${result[\"debt\"]:,.0f}')
        else:
            print('  ✗ Treasury API: No response')

    async with FredClient('$FRED_KEY') as fred:
        result = await fred.get_gdp()
        if result:
            print(f'  ✓ FRED API: GDP = \${result/1e12:.2f}T')
        else:
            print('  ✗ FRED API: No response')

asyncio.run(test())
"

echo

echo "===== Startup Complete ====="
echo
echo "Run API server:"
echo "  python api.py"
echo
echo "In another terminal, run monitor:"
echo "  python self_heal.py"
echo
echo "Access dashboard:"
echo "  http://localhost:8500"
echo
