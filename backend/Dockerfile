FROM python:3.12-slim

WORKDIR /app

# Install curl for health check probe
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Add non-root user for security
RUN useradd --no-create-home --shell /bin/false nonroot
USER nonroot

# Cloud Run expects port 8080
EXPOSE 8080

# Local docker healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
