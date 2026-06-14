FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Run as non-root user
RUN addgroup --system app && adduser --system --ingroup app app
RUN chown -R app:app /app
USER app

# Data volume
VOLUME /app/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
