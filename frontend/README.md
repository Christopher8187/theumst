# Frontend applications

Theumst has three Vue build entries. [Public site](webpage/README.md) covers public pages and account forms. It shares [desktop windows, Profile and appearance](shared/README.md) with the [Dashboard](dashboard/README.md), which supplies permitted management tools. [Web Demo](demo/README.md) covers the library and study workflow behind its access check and retains its existing 0.1.0 interface.

Each directory owns `package.json`, Vite configuration and a Dockerfile. `urls.js` supplies shared URL configuration. Public and dashboard build outputs are served by FastAPI; the demo build is served by its isolated Nginx container. [Frontend architecture](../docs/architecture/frontend.md) explains shared sessions and state boundaries.

Install locked dependencies with `npm ci` inside each application and run `npm run build`. A coordinated application release builds all three. Deterministic demo checks and browser coverage are documented in [testing](../docs/testing.md).
