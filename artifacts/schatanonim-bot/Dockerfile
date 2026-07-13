FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY config.py database.py keyboards.py spy.py main.py ./
COPY handlers/ ./handlers/
COPY middlewares/ ./middlewares/
CMD ["python", "main.py"]
