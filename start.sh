#!/bin/bash
echo "==> Installing Chromium system dependencies..."
apt-get update -qq && apt-get install -y -qq \
    libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0t64 libatk-bridge2.0-0t64 \
    libcups2t64 libdrm2 libatspi2.0-0t64 \
    libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libxkbcommon0 libasound2t64
echo "==> System deps installed"
echo "==> Starting gunicorn..."
exec gunicorn 'app:create_app()' --bind 0.0.0.0:$PORT
