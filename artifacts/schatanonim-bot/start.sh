#!/bin/bash
echo "=== Bot container started ==="
while true; do
    echo "[$(date)] Starting python main.py..."
    python main.py
    echo "[$(date)] Bot exited. Restarting in 10s..."
    sleep 10
done
