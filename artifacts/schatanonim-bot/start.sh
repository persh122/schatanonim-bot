#!/bin/bash
echo "Starting bot..."
while true; do
    python main.py
    echo "Bot exited, restarting in 10 seconds..."
    sleep 10
done
