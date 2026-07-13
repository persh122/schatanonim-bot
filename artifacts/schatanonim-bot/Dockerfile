FROM python:3.11-slim
WORKDIR /app
RUN mkdir -p /app/data
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENV DB_PATH=/app/data/bot.db
CMD ["sh", "start.sh"]
