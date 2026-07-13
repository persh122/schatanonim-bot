FROM python:3.11-slim
WORKDIR /app
RUN mkdir -p /app/data
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot/ ./bot/
ENV DB_PATH=/app/data/bot.db
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "while true; do python bot/main.py 2>&1; echo \"[RESTART] Bot exited, restarting in 10s...\"; sleep 10; done"]
