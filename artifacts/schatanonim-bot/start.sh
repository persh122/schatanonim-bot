#!/bin/sh
echo "=== Bot started ==="
while true; do
    echo "Running bot..."
    python main.py
    echo "Bot stopped. Restarting in 10s..."
    sleep 10
done
