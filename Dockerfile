# IncuBrix Prompt-Based Video Editing Engine
# Multi-stage / lightweight container for Cloud and Distributed Deployments
FROM python:3.11-slim

# Prevent python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies: FFmpeg and curl (for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Ensure data and renders directory exist
RUN mkdir -p /app/data/renders /app/data/storage

EXPOSE 8000

# Default entrypoint runs the FastAPI service; worker container overrides with 'python worker.py'
CMD ["uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8000"]
