#!/bin/bash
# ec2_setup.sh — bootstrap agentwell on a fresh EC2 Ubuntu instance
# Run once after launch. After first run, save AMI for instant restarts.
#
# Usage:
#   chmod +x scripts/ec2_setup.sh
#   ./scripts/ec2_setup.sh

set -e

echo "=== agentwell EC2 bootstrap ==="

# System packages
sudo apt update -y
sudo apt install -y python3-pip python3-venv git curl

# Clone repo if not already present
if [ ! -d "$HOME/agentwell" ]; then
    git clone https://github.com/flowmindlabs/agentwell.git "$HOME/agentwell"
fi

cd "$HOME/agentwell"

# Pull latest
git pull origin main

# Create venv
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create .env if not present
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
AGENTWELL_UPSTREAM=https://api.groq.com/openai
AGENTWELL_PORT=3001
AGENTWELL_HEALTH_THRESHOLD=70
AGENTWELL_WINDOW_SIZE=20
AGENTWELL_DB_PATH=/home/ubuntu/agentwell/agentwell.db
AGENTWELL_STORE_EMBEDDINGS=false
AGENTWELL_API_KEY=
GROQ_API_KEY=REPLACE_WITH_YOUR_GROQ_KEY
EOF
    echo ""
    echo "IMPORTANT: edit .env and set GROQ_API_KEY before starting the proxy."
    echo "  nano .env"
fi

# Create reports directory
mkdir -p reports

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Set GROQ_API_KEY in .env if not done"
echo "  2. source .venv/bin/activate"
echo "  3. python -m agentwell.proxy.server"
echo "  4. In second terminal: python examples/simulation.py"
