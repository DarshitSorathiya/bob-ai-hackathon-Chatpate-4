FROM python:3.12-slim

WORKDIR /app

# Install system deps needed by some ML packages (e.g. psycopg binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

EXPOSE 8000

# Default: run migrations then start the server.
# Override CMD in docker-compose for a migrate-only one-shot container.
CMD alembic upgrade head && \
    uvicorn app.main:app --host 0.0.0.0 --port 8000
