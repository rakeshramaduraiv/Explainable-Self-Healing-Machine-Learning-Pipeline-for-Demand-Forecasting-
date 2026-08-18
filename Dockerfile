FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend_minimal.py .
COPY data/raw/train.csv data/raw/train.csv

RUN mkdir -p data/uploads models

EXPOSE 8001

CMD ["python", "backend_minimal.py"]
