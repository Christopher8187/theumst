# syntax=docker/dockerfile:1.7

FROM node:22-alpine AS base
WORKDIR /app/frontend/demo
COPY frontend/demo/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/demo ./
COPY frontend/shared /app/frontend/shared

FROM base AS dev
ENV VITE_API_PROXY_TARGET=http://backend:8000
EXPOSE 5175
CMD ["npm", "run", "dev"]

FROM base AS build
RUN npm run build

FROM nginx:1.27-alpine AS production
COPY frontend/demo/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/demo/dist /usr/share/nginx/html/demo
EXPOSE 80
