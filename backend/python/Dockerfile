# syntax=docker/dockerfile:1.7

# Built from repository root. Compose chooses dev or production target.

FROM node:22-alpine AS webpage-build
WORKDIR /app/frontend/webpage
COPY frontend/webpage/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/urls.js ../urls.js
COPY frontend/webpage ./
RUN npm run build

FROM node:22-alpine AS dashboard-build
WORKDIR /app/frontend/dashboard
COPY frontend/dashboard/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/urls.js ../urls.js
COPY frontend/dashboard ./
RUN npm run build

FROM python:3.14-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PIP_NO_CACHE_DIR=1     SESSION_DAYS=7     SERVER=LOCAL     LOCAL_STORAGE_DIR=/storage     DB_NAME=theumst     DB_USER=postgres     DB_PASSWORD=postgres     DB_HOST=db     DB_PORT=5432     CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8080,http://127.0.0.1:8080
WORKDIR /app/backend/python
RUN apt-get update     && apt-get install -y --no-install-recommends curl     && rm -rf /var/lib/apt/lists/*
COPY backend/python/requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

FROM base AS dev
COPY backend/python ./
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production
WORKDIR /app
COPY backend ./backend
COPY --from=webpage-build /app/frontend/webpage/dist ./frontend/webpage/dist
COPY --from=dashboard-build /app/frontend/dashboard/dist ./frontend/dashboard/dist
WORKDIR /app/backend/python
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
