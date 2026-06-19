# Frontend layout

The two Vue apps stay separate:

- `webpage/` is the public site on local port `5173`.
- `dashboard/` is the logged-in app on local port `5174`.

They share:

- `urls.js` for local/prod URL helpers.
- `assets/images/` as the shared Vite public asset folder, so both apps can use `/images/logo.png`, `/images/cave.jpg`, etc.

Each app now uses the same simple structure:

- `src/components/` for reusable UI pieces.
- `src/pages/` for page-level screens/content.
- `src/router/` for route names and route decisions.
- `src/utils/` for small helpers such as i18n/session code.
- `src/App.vue` as the small coordinator for the app.
