# Public site

Visitors browse public pages and news, create an account, sign in, verify their email or recover a password. Account forms call the backend; their local success messages do not establish that an email reached an inbox.

`src/App.vue` composes the page shell, `pages/` implements account and public pages, and `composables/useWebpageRouter.js` controls page navigation. `utils/language.js` owns public-site copy. Branding images under backend assets are distinct from governed book images.

Build with `npm ci` then `npm run build`. Local Vite uses port 5173. Read [account recovery](../../docs/account-recovery.md) for SMTP and [security](../../docs/security.md) for authentication. Backend tests for email claims, password recovery and frontend policy cover associated behavior; the release browser checks separately cover visible flows.
