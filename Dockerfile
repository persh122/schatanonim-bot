FROM python:3.11-slim
WORKDIR /app
RUN mkdir -p /app/data
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY bot/ ./bot/
ENV DB_PATH=/app/data/bot.db
CMD ["sh", "-c", "while true; do python bot/main.py; echo 'Bot exited, restarting in 10s...'; sleep 10; done"]
