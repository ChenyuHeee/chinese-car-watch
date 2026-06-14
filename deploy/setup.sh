#!/bin/bash
# AutoInsight server setup script
# Run on server: bash deploy/setup.sh
set -e

TARGET=/var/www/insight/auto
REPO=git@github.com:ChenyuHeee/chinese-car-watch.git

echo "=== AutoInsight Setup ==="
echo "Target: $TARGET"

# 1. Clone or update repo
if [ -d "$TARGET/.git" ]; then
    echo "→ Updating existing repo..."
    cd "$TARGET" && git pull
else
    echo "→ Cloning repo..."
    mkdir -p "$(dirname "$TARGET")"
    git clone "$REPO" "$TARGET"
fi

cd "$TARGET"

# 2. Create .env if missing
if [ ! -f .env ]; then
    echo "→ Creating .env (please fill in DEEPSEEK_API_KEY)..."
    cat > .env << 'EOF'
# DeepSeek API key (get from https://platform.deepseek.com/api_keys)
DEEPSEEK_API_KEY=your_key_here

# Proxy (if needed in mainland China)
# HTTPS_PROXY=http://127.0.0.1:7890
# HTTP_PROXY=http://127.0.0.1:7890
EOF
    echo "⚠️  Edit $TARGET/.env with your actual API key!"
fi

# 3. Build and start
echo "→ Building Docker image..."
docker compose build

echo "→ Starting services..."
docker compose up -d

# 4. Verify
sleep 3
echo "→ Health check..."
curl -s http://localhost:8081/auto/api/health || echo "⚠️  Health check failed"

echo ""
echo "=== Setup complete ==="
echo "Dashboard: http://localhost:8081/auto"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your DEEPSEEK_API_KEY"
echo "  2. Configure nginx to proxy /auto to localhost:8081"
echo "  3. Set up cron: crontab deploy/crontab.txt"
