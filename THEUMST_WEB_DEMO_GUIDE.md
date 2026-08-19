# The Ultimate Mega Study Tool — Web Demo Version 0.0.1 guide

This release adds a protected, interactive study prototype in an isolated container. It is designed as the first usable layer of the wider UMST ecosystem: structured learning today, and richer expert-reviewed benchmarking, model evaluation, AI training, and AI-safety research over time.

## What was added

- A new `betatester` authority and database-backed beta request/review workflow.
- A professional **Dashboard → Web Demo** access page for every signed-in user.
- An admin/superadmin review queue with Approve and Reject controls.
- Direct demo access for beta testers, managers, admins, and superadmins.
- A separate `demo` Docker container, protected in production by Nginx `auth_request`.
- A searchable book library, book details, summoning transition, grimoire library, and eight illustrated realm tiles.
- Text and exercise study modes with progress recovery, section breadcrumbs, and a responsive knowledge graph.
- Central graph nodes for definitions, notation, theorems, and exercises, with branching context objects and completion state.
- Attached notes and book-independent scribble notes, all persisted in PostgreSQL.
- Training navigation to the next unfinished exercise.
- Crystallize search using an equal blend of statement similarity and combined statement/working-summary similarity, including cross-book navigation and return to the original study book.
- Safe KaTeX display-math rendering for content wrapped in `$$` delimiters.
- Seven interface languages: English, Chinese, Japanese, Korean, Spanish, French, and German. Ingested book content remains English for this version, while the database already retains language-aware content tables.
- Visible `Web Demo Version 0.0.1` labelling throughout the demo.
- Root-only SEO consolidation, canonical metadata, a crawlable UMST favicon, a focused sitemap, and noindex/disallow controls for private application surfaces.

## Roles and demo access

| Authority | Request needed | Enter demo | Review requests |
| --- | --- | --- | --- |
| User | Yes | After approval | No |
| Beta tester | No | Yes | No |
| Manager | No | Yes | No |
| Admin | No | Yes | Yes |
| Superadmin | No | Yes | Yes |

Approval promotes an ordinary user to `betatester`. It never downgrades a manager, admin, or superadmin.

## Requesting and approving access

1. Register or sign in on the public website.
2. Open **Dashboard → Web Demo**.
3. Select **Request access**. The optional message is shown to reviewers.
4. An admin or superadmin opens **Dashboard → Web Demo**.
5. In **Demo access requests**, select **Approve** or **Reject**.
6. After approval, the user's **Enter Web Demo** button becomes active.

The public site's **Demo** menu item sends signed-out visitors to login, preserving the intended dashboard destination. Signed-in visitors go directly to the dashboard gate.

## Using the demo

### Library and summoning

1. Search the Arcane Library by title.
2. Open a book to see its summary, table of contents, edition, and ISBN.
3. Select **Summon grimoire**.
4. Use **My grimoires** to search summoned books by recency.

The four actions at the bottom of the library and the Expand, Review, Preview, Advice, and Progress realms intentionally show “coming soon”.

### Study realms

- **書 / Text** opens knowledge objects in source order with statement, workings, labels, breadcrumbs, and graph navigation.
- **問 / Questions** focuses on exercise objects and adds Previous/Next controls.
- **寫 / Notes** opens the two-panel Scholar's Desk for attached notes and scribbles.
- **Train** jumps to the nearest unfinished exercise after the current object.
- **Crystallize** opens embedding-similar objects. Opening another book preserves the original study book so Back/Return restores the starting session.
- **Mark done** persists completion and updates graph-node colour.

Audio, AI prompt, and Project controls are visible but intentionally report “coming soon” in version 0.0.1.

## LaTeX content

Display math is rendered whenever ingested text includes LaTeX between double-dollar delimiters:

```text
A vector in $$\mathbb{R}^n$$ has coordinates $$v=(v_1,\ldots,v_n)$$.
```

The renderer escapes ordinary HTML before inserting KaTeX output, so source content is not treated as trusted HTML.

## Running locally

From the repository root:

```powershell
docker compose --env-file .env -f compose.local.yml up --build -d
```

Open:

- Public site: `http://localhost:5173`
- Dashboard: `http://localhost:5174/dashboard/demo/`
- Isolated demo: `http://localhost:5175/demo/`
- Backend API: `http://localhost:8000/docs`

The direct port is convenient for local development. Production `/demo/` traffic goes through the protected Docker Nginx route.

## Live release

Web Demo Version 0.0.1 is deployed at `https://theumst.com`.

- Open **Demo** in the public navigation. Signed-out visitors are sent to login.
- After login, **Dashboard → Web Demo** shows the request/access gate.
- The isolated application is served at `/demo/`, but Nginx checks the user's session and `demo` permission before returning any application files.
- The eight source artworks are retained as PNG files in the repository; optimized 1200×800 WebP delivery copies are served by the website.

The release was checked with production frontend/container builds, the automated Python test suite, zero-vulnerability npm audits, direct database migration checks, desktop/mobile browser passes, public health endpoints, and live SEO/redirect checks.

## Main implementation points

- `backend/sql/005_demo_beta.sql` — roles, access requests, durable study state, notes, similarity samples, and sample books.
- `backend/python/app/routers/demo.py` — protected access, book, graph, progress, note, and crystallize APIs.
- `frontend/dashboard/src/pages/DemoPage.vue` — request gate and reviewer queue.
- `frontend/demo/` — isolated Vue/KaTeX Web Demo application and production Nginx image.
- `config/nginx.docker.conf` — production demo access check and proxy.
- `backend/python/app/routers/frontend.py` — dashboard routing, robots policy, and sitemap.

## Search indexing

The public SPA uses `https://theumst.com/` as its canonical URL and the title **The Ultimate Mega Study Tool**. The sitemap lists only the canonical root so legacy and client-side routes consolidate instead of competing as separate search results. Dashboard, demo, authentication/API, and documentation routes are excluded from crawling. The favicon is the square UMST logo at `/images/logo.png`.

Search engines decide when to recrawl and may take time to replace previously indexed URLs. After deployment, submitting `https://theumst.com/sitemap.xml` in Google Search Console can accelerate discovery, but indexing changes are not immediate or guaranteed.
