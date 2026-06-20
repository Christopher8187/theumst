# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS frontend
WORKDIR /app

COPY frontend/webpage/package*.json ./frontend/webpage/
RUN --mount=type=cache,target=/root/.npm cd frontend/webpage && npm ci

COPY frontend/dashboard/package*.json ./frontend/dashboard/
RUN --mount=type=cache,target=/root/.npm cd frontend/dashboard && npm ci

COPY frontend ./frontend
RUN cd frontend/webpage && npm run build
RUN cd frontend/dashboard && npm run build

FROM python:3.14-slim AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SESSION_DAYS=7 \
    SERVER=LOCAL \
    LOCAL_STORAGE_DIR=/storage \
    DB_NAME=theumst \
    DB_USER=postgres \
    DB_PASSWORD=postgres \
    DB_HOST=db \
    DB_PORT=5432 \
    CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8080,http://127.0.0.1:8080
WORKDIR /app/backend/python
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY backend/python/requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

FROM python-base AS dev
WORKDIR /app/backend/python
COPY backend/python ./
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM python-base AS production
WORKDIR /app
COPY backend ./backend
COPY frontend/assets ./frontend/assets
COPY --from=frontend /app/frontend/webpage/dist ./frontend/webpage/dist
COPY --from=frontend /app/frontend/dashboard/dist ./frontend/dashboard/dist
WORKDIR /app/backend/python
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
