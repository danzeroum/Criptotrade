FROM python:3.11-slim

LABEL org.opencontainers.image.title="Criptotrade" \
      org.opencontainers.image.description="Crypto AI trading platform (paper trading, HITL)" \
      org.opencontainers.image.source="https://github.com/danzeroum/Criptotrade" \
      org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directories
RUN mkdir -p /app/data /app/logs

# Expose ports
EXPOSE 8000 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run the FastAPI gateway. NOTE: src.main is the BuildToValue demo (no ASGI app);
# the API lives in src.api.main:app, which the HEALTHCHECK above also targets.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
