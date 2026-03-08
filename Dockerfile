FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run DB migration then start the server
CMD ["sh", "-c", "python -m app.database --migrate && uvicorn app.main:app --host 0.0.0.0 --port 3000"]
