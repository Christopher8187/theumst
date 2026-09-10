# Signed-in dashboard

The dashboard lets a user manage their profile and keys, request Web Demo access, and open permitted content or administrative tools. Access determines both available navigation and server authorization. Users do not gain access by entering a page URL manually.

`src/router/` selects pages. `src/pages/` contains profile, API keys, Demo, Books, Media, Users, Admin and Superadmin views. `src/components/Sidebar.vue` presents available destinations. Privileged role names and arbitrary SQL remain outside ordinary user flows.

Run `npm ci` and `npm run build` here. Local Vite uses port 5174 and the dashboard path prefix. Read [administration](../../docs/administration.md), [security](../../docs/security.md) and [backend test modules](../../backend/python/tests/README.md) before changing role-sensitive behavior.
