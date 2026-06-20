# Frontend layout

The two Vue apps stay separate:

- `webpage/` is the public site on local port `5173`.
- `dashboard/` is the logged-in app on local port `5174`.

They share `frontend/urls.js` for local/prod URL helpers.

Static images now live under the backend:

```text
backend/assets/images/
```

The backend serves them at `/images/...`. During local Vite development, `VITE_ASSET_BASE=http://localhost:8000/images` points both Vue apps to the backend asset server. In deployment, nginx proxies everything to FastAPI, so `/images/...` still works.

Each app uses the same simple structure:

- `src/components/` for reusable UI pieces.
- `src/pages/` for page-level screens/content.
- `src/router/` for route names and route decisions.
- `src/utils/` for small helpers such as i18n code.
- `src/App.vue` as the small coordinator for the app.

The public webpage is now real Vue components, not raw HTML fragments injected through `v-html`.
