FROM python:3.11-slim
WORKDIR /app
RUN mkdir -p /app/data
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY config.py database.py keyboards.py spy.py main.py ./
COPY handlers/ ./handlers/
COPY middlewares/ ./middlewares/
ENV DB_PATH=/app/data/bot.db
CMD ["python", "main.py"]
