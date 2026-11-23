# IncuBrix Prompt-Based Video Editing Engine
# Multi-stage / lightweight container for Cloud and Distributed Deployments
FROM python:3.11-slim

# Prevent python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    QUEUE_BACKEND=inprocess \
    STORAGE_BACKEND=local \
    DATABASE_URL=sqlite:////app/data/incubrix.db

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

# Ensure data and renders directory exist and are writable
RUN mkdir -p /app/data/renders /app/data/storage /app/test_pack/sessions && chmod -R 777 /app/data /app/test_pack

# Expose port (default 7860 for Hugging Face Spaces; Render/Cloud Run inject $PORT)
EXPOSE 7860

# Default entrypoint binds dynamically to ${PORT:-7860}
CMD ["sh", "-c", "uvicorn service.app:app --host 0.0.0.0 --port ${PORT:-7860}"]
