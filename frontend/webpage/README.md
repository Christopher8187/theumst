# Public site

Visitors browse public pages and news, create an account, sign in, verify their email or recover a password. Account forms call the backend; their local success messages do not establish that an email reached an inbox.

`src/App.vue` composes the page shell, `pages/` implements account and public pages, and `composables/useWebpageRouter.js` controls page navigation. `utils/language.js` owns public-site copy. Branding images under backend assets are distinct from governed book images.

Build with `npm ci` then `npm run build`. Local Vite uses port 5173. Read [account recovery](../../docs/account-recovery.md) for SMTP and [security](../../docs/security.md) for authentication. Backend tests for email claims, password recovery and frontend policy cover associated behavior; the release browser checks separately cover visible flows.

Run the password-reset browser regression checks with `npm ci`, `npx playwright install chromium`, then `npm test`. To use installed Chrome, set `PLAYWRIGHT_CHANNEL=chrome` instead of installing Chromium. The checks start their own Vite server on loopback port 5187 and cover mismatched passwords, successful resets and the invalid-link fallback in English, Chinese and Japanese. They intercept reset requests using a dummy token, so they do not send email or change real passwords. Output goes to the existing Parent Repo Test Area at `testing_ground/theumst-webpage`; set `PLAYWRIGHT_OUTPUT_DIR` to override it.
