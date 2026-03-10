#!/bin/bash
echo "==> Installing Chromium system dependencies..."
playwright install-deps chromium
echo "==> System deps installed"
echo "==> Starting gunicorn..."
exec gunicorn 'app:create_app()' --bind 0.0.0.0:$PORT
