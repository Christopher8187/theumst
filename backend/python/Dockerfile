FROM node:22-alpine AS webpage-build
WORKDIR /app/frontend/webpage
COPY frontend/webpage/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/urls.js ../urls.js
COPY frontend/shared ../shared
COPY frontend/dashboard/src ../dashboard/src
COPY frontend/webpage ./
RUN npm run build

FROM node:22-alpine AS dashboard-build
WORKDIR /app/frontend/dashboard
COPY frontend/dashboard/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/urls.js ../urls.js
COPY frontend/shared ../shared
COPY frontend/webpage/src ../webpage/src
COPY frontend/dashboard ./
RUN npm run build

FROM python:3.13-slim AS base
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
    QDRANT_ENABLED=true \
    QDRANT_URL=http://qdrant:6333 \
    QDRANT_COLLECTION=knowledge-qwen3-embedding-0-6b \
    QDRANT_VECTOR_SIZE=1024 \
    QDRANT_DISTANCE=cosine
WORKDIR /app/backend/python
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
COPY backend/python/requirements.txt ./requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
COPY backend/sql /app/backend/sql

FROM base AS dev
COPY backend/python ./
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production
COPY backend/python/requirements-cloud.txt ./requirements-cloud.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-cloud.txt
WORKDIR /app
COPY backend ./backend
COPY --from=webpage-build /app/frontend/webpage/dist ./frontend/webpage/dist
COPY --from=dashboard-build /app/frontend/dashboard/dist ./frontend/dashboard/dist
WORKDIR /app/backend/python
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
