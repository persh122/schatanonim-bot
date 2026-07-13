FROM python:3.11-slim
WORKDIR /app
RUN mkdir -p /app/data
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY config.py database.py keyboards.py spy.py main.py start.sh ./
COPY handlers/ ./handlers/
COPY middlewares/ ./middlewares/
RUN chmod +x start.sh
ENV DB_PATH=/app/data/bot.db
CMD ["bash", "start.sh"]
