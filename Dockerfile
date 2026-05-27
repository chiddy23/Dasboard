# JustInsurance Student Dashboard - Production Dockerfile
# Multi-stage build for optimized production image

# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm install

# Copy frontend source
COPY frontend/ ./

# Build for production
RUN npm run build

# Stage 2: Python backend with static files
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements and install
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./

# Copy built frontend to the path Flask actually serves from.
# app.py computes FRONTEND_DIST = dirname(dirname(__file__))/frontend/dist.
# Since backend/ is copied to /app (so app.py is /app/app.py), that resolves
# to /frontend/dist — NOT /app/static. Copy there so the SPA is served.
COPY --from=frontend-build /app/frontend/dist /frontend/dist

# Create session directory
RUN mkdir -p flask_session

# Environment variables
ENV FLASK_ENV=production
ENV PORT=8080

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health')" || exit 1

# Run with gunicorn. ONE worker to match prod's effective WEB_CONCURRENCY=1.
# Multiple workers each hold their own Absorb token and revoke each other
# (single-session-per-account), causing flaky "no students". Threads give
# concurrency within the single worker without the token war.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "120", "app:app"]
