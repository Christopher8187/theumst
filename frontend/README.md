# Frontend applications

Theumst has three Vue applications. [Public site](webpage/README.md) covers public pages and account forms. [Dashboard](dashboard/README.md) covers signed-in profile and permitted management tools. [Web Demo](demo/README.md) covers the library and study workflow behind its access check.

Each directory owns `package.json`, Vite configuration and a Dockerfile. `urls.js` supplies shared URL configuration. Public and dashboard build outputs are served by FastAPI; the demo build is served by its isolated Nginx container. [Frontend architecture](../docs/architecture/frontend.md) explains shared sessions and state boundaries.

Install locked dependencies with `npm ci` inside each application and run `npm run build`. A coordinated application release builds all three. Deterministic demo checks and browser coverage are documented in [testing](../docs/testing.md).
