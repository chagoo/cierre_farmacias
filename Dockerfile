# Multi-stage build for cierre_farmacias
# Pass the application environment as build arg (development|production)
ARG ENVIRONMENT=production
FROM python:3.11-slim as base

# Set work directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Install python dependencies
RUN pip install --no-cache-dir .

# Expose port
EXPOSE 5000

# Set environment variable for the app
ENV ENV=${ENVIRONMENT} \
    PYTHONUNBUFFERED=1

# Default command (can be overridden by docker-compose)
CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:5000"]
