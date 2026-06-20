# syntax=docker/dockerfile:1.7

# Built from the repository root so shared frontend/urls.js and frontend/assets
# are available without depending on where dev scripts are launched from.

FROM node:22-alpine AS base
WORKDIR /app/frontend/webpage
COPY frontend/webpage/package*.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY frontend/urls.js ../urls.js
COPY frontend/assets ../assets
COPY frontend/webpage ./

FROM base AS dev
ENV VITE_API_BASE=http://localhost:8000 \
    VITE_WEBPAGE_BASE=http://localhost:5173 \
    VITE_DASHBOARD_BASE=http://localhost:5174/dashboard \
    VITE_ASSET_BASE=http://localhost:8000/images
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM base AS build
RUN npm run build

FROM nginx:1.27-alpine AS production
COPY --from=build /app/frontend/webpage/dist /usr/share/nginx/html
EXPOSE 80
