Historical input. Read current docs from the repository README.

# theumst website and content administration guide

This guide covers the database-backed content-management workflow. The protected interactive prototype added later is documented separately in `THEUMST_WEB_DEMO_GUIDE.md`.

## What was added

- A redesigned public homepage presenting theumst as an interactive learning and AI-training ecosystem.
- Clear coverage of the longer-term vision: structured knowledge, richer benchmarking, AI-safety applications, and combined AI/human expert review.
- A live News page. Published dashboard stories appear on the homepage and `/news` automatically.
- A new `manager` authority.
- A Books dashboard page with create, read, update, and delete controls for the existing `grimoire` catalog.
- A Media dashboard page with create, read, update, publish/draft, and delete controls.
- An Admin-page control for promoting a regular user to manager.
- Permission updates so managers, admins, and superadmins can use Books and Media.

## Roles and access

| Role | Profile | API keys | Books | Media | Admin tools | Superadmin tools |
| --- | --- | --- | --- | --- | --- | --- |
| User | Yes | Yes | No | No | No | No |
| Manager | Yes | Yes | Yes | Yes | No | No |
| Admin | Yes | Yes | Yes | Yes | Yes | No |
| Superadmin | Yes | Yes | Yes | Yes | Yes | Yes |

An admin or superadmin can promote a regular account from **Dashboard → Admin → Manager authority**. Enter the account's username or email and select **Make manager**. The operation cannot downgrade an admin or superadmin.

## Managing books

1. Sign in as a manager, admin, or superadmin.
2. Open **Dashboard → Books**.
3. Use **Add book** to enter a title and optional publisher, ISBN, date, version, and source key.
4. Use **Edit** beside any catalog item to update it.
5. Use **Delete** to permanently delete the book.

Deleting a book cascades through its connected sections and knowledge objects. The confirmation dialog shows the number of connected sections and objects before deletion.

## Managing news and media

1. Open **Dashboard → Media**.
2. Enter a headline, summary, story, and optional image URL.
3. Choose **Published** to make it public immediately, or **Draft** to keep it private.
4. Published posts appear automatically on the public homepage and `/news`.
5. Use **Edit** to revise or change status, and **Delete** to remove a story.

For bundled placeholder imagery, use `/images/graph.jpg` or `/images/cave.jpg`. Full external `https://` image URLs are also supported.

## Running locally

From the repository root:

```powershell
docker compose --env-file .env -f compose.local.yml up --build -d
```

The local backend only uses filesystem storage. DigitalOcean Spaces and Aliyun OSS clients are lazy-loaded for remote deployments. A production image that uses those storage modes should install `backend/python/requirements-cloud.txt`, which adds `boto3` and `oss2` to the core requirements.

Then open:

- Public website: `http://localhost:5173`
- Dashboard: `http://localhost:5174/dashboard/profile/`
- Backend API docs: `http://localhost:8000/docs`

To view service status:

```powershell
docker compose --env-file .env -f compose.local.yml ps
```

To stop the local services without deleting database data:

```powershell
docker compose --env-file .env -f compose.local.yml down
```

## Main implementation points

- `backend/sql/003_manager_content.sql`: additive role/access migration and `media_post` table.
- `backend/python/app/routers/content.py`: protected book/media APIs and public news API.
- `backend/python/app/routers/admin.py`: manager-promotion API.
- `frontend/dashboard/src/pages/BooksPage.vue`: book CRUD interface.
- `frontend/dashboard/src/pages/MediaPage.vue`: newsroom CRUD interface.
- `frontend/webpage/src/pages/HomePage.vue`: new public vision and live news preview.
- `frontend/webpage/src/pages/NewsPage.vue`: public news feed.

## Important behavior

- SQL migrations are idempotent and applied on backend startup, including existing local database volumes.
- Public visitors only receive posts whose status is `published`.
- Book and media endpoints validate the signed-in user's database-backed access points on every request; hiding dashboard links is not the security boundary.
- The content controls remain independent of the separately deployed Web Demo; see `THEUMST_WEB_DEMO_GUIDE.md` for its access and study workflows.
