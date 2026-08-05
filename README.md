# The UMST website

This repository contains the complete public website, dashboard, FastAPI backend,
PostgreSQL schema, Qdrant semantic-vector database, and LOCAL/COM/CN object-storage
integrations.

The checked-in release archive includes a populated `.env` using the deployment
information supplied for:

- `theumst.com` on the COM server with DigitalOcean Spaces;
- `theumst.cn` on the CN server with Aliyun OSS;
- local Docker development on Windows.

`.env` remains listed in `.gitignore`. Do not add it to a public repository.

## What the deployment scripts do

A full remote deployment performs every application-side step in this order:

1. Connect to the selected server over SSH.
2. Install or update Docker, Nginx, Certbot, curl, tar, and gzip.
3. Enable Docker and open ports 22, 80, and 443 in UFW when UFW is present.
4. Create and repair permissions for the remote application directory.
5. Build one gzip-compressed deployment archive containing the source and a target-specific `.env`.
6. Upload that single archive, extract it into a temporary release directory, atomically activate it, and delete both temporary archive copies:
   - COM receives only the DigitalOcean storage credentials;
   - CN receives only the Aliyun storage credentials.
7. Build the production frontend and backend Docker image.
8. Start PostgreSQL, Qdrant, FastAPI, and the internal Docker Nginx proxy.
9. Wait until the database-backed application health check succeeds.
10. Obtain or reuse the TLS certificate.
11. Install the correct host Nginx configuration.
12. Verify the public website and all dependency health endpoints.

The host Nginx service proxies HTTPS traffic to the production Docker stack bound
only to `127.0.0.1:8080`. PostgreSQL and Qdrant are not published publicly.

---

# 1. Architecture

```text
Browser
   |
Host Nginx :80/:443
   |
Docker Nginx 127.0.0.1:8080
   |
FastAPI :8000
   |-------------------|------------------|
PostgreSQL          Qdrant       LOCAL / Spaces / Aliyun OSS
```

Production frontend files are compiled into the FastAPI production image. The
backend serves both Vue applications and the API from the same public origin.

Backend source follows normal FastAPI package conventions:

```text
backend/python/
├── app.py
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── schemas.py
│   ├── security.py
│   ├── routers/
│   └── services/
└── tests/
```

---

# 2. Required external state

These are the only prerequisites that cannot be created from this source tree.
Complete them before running a public deployment.

## 2.1 Windows software

Install and start:

1. **Docker Desktop**, including Docker Compose.
2. **Git for Windows**, including Git Bash.
3. PowerShell 5 or later.

Verify in PowerShell:

```powershell
docker version
docker compose version
bash --version
ssh -V
```

## 2.2 SSH private keys

Place these files in `%USERPROFILE%\.ssh`:

```text
chris-theumst-com.pem
chris-theumst-cn.pem
```

The Windows deployment wrappers pass this Windows directory explicitly to Git
Bash or WSL and translate it to the correct shell path. Leave
`SSH_KEY_DIR=__AUTO__` in `.env` for this behavior. To use another directory,
set `SSH_KEY_DIR` to an absolute path, preferably with forward slashes, such as
`C:/keys/theumst`.

Restrict their permissions in PowerShell:

```powershell
icacls "$env:USERPROFILE\.ssh\chris-theumst-com.pem" /inheritance:r
icacls "$env:USERPROFILE\.ssh\chris-theumst-com.pem" /grant:r "$env:USERNAME:(R)"
icacls "$env:USERPROFILE\.ssh\chris-theumst-cn.pem" /inheritance:r
icacls "$env:USERPROFILE\.ssh\chris-theumst-cn.pem" /grant:r "$env:USERNAME:(R)"
```

## 2.3 DNS records

The public certificate and final health checks require these records to exist.

For COM:

```text
theumst.com      A  165.227.23.136
www.theumst.com  A  165.227.23.136
```

For CN:

```text
theumst.cn      A  8.153.84.223
www.theumst.cn  A  8.153.84.223
```

Verify from PowerShell:

```powershell
Resolve-DnsName theumst.com
Resolve-DnsName www.theumst.com
Resolve-DnsName theumst.cn
Resolve-DnsName www.theumst.cn
```

## 2.4 Cloud firewalls

The DigitalOcean and Aliyun network firewalls must permit inbound TCP traffic on:

```text
22   SSH
80   HTTP / certificate validation
443  HTTPS
```

The deployment script configures UFW on the server when UFW exists, but it cannot
change a provider-level cloud firewall.

---

# 3. Run the website locally from source

Open PowerShell in the extracted project directory.

## 3.1 Start all services

```powershell
docker compose --env-file .env -f compose.local.yml up --build -d
```

The first build downloads Docker images and installs frontend/backend dependencies.
Wait until all services are healthy:

```powershell
docker compose --env-file .env -f compose.local.yml ps
curl.exe -f http://localhost:8000/health
curl.exe -f http://localhost:8000/health/db
curl.exe -f http://localhost:8000/health/qdrant
curl.exe -f http://localhost:8000/health/assets
```

## 3.2 Open the local applications

```text
Public website:   http://localhost:5173
Dashboard:        http://localhost:5174/dashboard/profile/
FastAPI docs:     http://localhost:8000/docs
Qdrant dashboard: http://localhost:6333/dashboard
```

## 3.3 Create and promote Christopher locally

1. Open `http://localhost:5173/signup`.
2. Create exactly one account with username `christopher`.
3. Run:

```powershell
.\dev\bat\make_christopher_superadmin.bat local
```

The promotion script refuses zero or multiple case-insensitive Christopher
accounts and then grants the unique account `superadmin` authority.

## 3.4 Local logs and shutdown

```powershell
docker compose --env-file .env -f compose.local.yml logs -f
docker compose --env-file .env -f compose.local.yml down
```

Delete all local Docker data only when intentionally resetting the database:

```powershell
docker compose --env-file .env -f compose.local.yml down -v
```

---

# 4. Deploy theumst.com from source to a live website

The COM deployment is designed to run from one command after the prerequisites in
section 2 are complete.

## 4.1 Deploy

From PowerShell:

```powershell
.\dev\bat\deploy_com.bat
```

Equivalent Git Bash command:

```bash
./dev/sh/agent_deploy.sh COM
```

The script installs the server software, packages the code and COM-only secrets into one compressed archive, uploads that single file, extracts it on the server, builds the Docker stack, issues the Let's Encrypt certificate, installs Nginx, and checks the public site. The local archive and remote `/tmp` archive are deleted automatically after extraction. COM also installs Certbot renewal hooks that stop
Nginx before standalone validation and restart it afterward.

A successful run ends with:

```text
Deployment complete: https://theumst.com
```

The bulk source transfer is one `.tar.gz` file rather than one network operation per project file. The archive is extracted under `/tmp` as the SSH user, then the release is moved into `/var/www` with `sudo`; the SSH user never needs permission to create sibling directories directly under `/var/www`. The previous server source tree is retained as `<REMOTE_ROOT>.previous` until the replacement Docker stack starts successfully, then removed automatically.

## 4.2 Create and promote Christopher on COM

If the account does not yet exist:

1. Open `https://theumst.com/signup`.
2. Create the unique username `christopher`.
3. Run:

```powershell
.\dev\bat\make_christopher_superadmin.bat COM
```

## 4.3 Verify COM

```powershell
curl.exe -f https://theumst.com/
curl.exe -f https://theumst.com/health
curl.exe -f https://theumst.com/health/db
curl.exe -f https://theumst.com/health/qdrant
curl.exe -f https://theumst.com/health/assets
```

Open:

```text
Website:  https://theumst.com
Dashboard: https://theumst.com/dashboard/profile/
API docs: https://theumst.com/docs
```

---

# 5. Deploy theumst.cn from source to a live website

## 5.1 Deploy

From PowerShell:

```powershell
.\dev\bat\deploy_cn.bat
```

Equivalent Git Bash command:

```bash
./dev/sh/agent_deploy.sh CN
```

The CN certificate is configured for an interactive DNS challenge. If the
certificate is not already present, Certbot displays one or more TXT records.
For each prompt:

1. Copy the TXT record name and value shown by Certbot.
2. Add the record in the DNS provider exactly as shown.
3. Keep earlier TXT values in place if Certbot asks for another value at the same
   `_acme-challenge` name.
4. Wait until the value resolves publicly. Verify in another PowerShell window:

   ```powershell
   Resolve-DnsName -Type TXT _acme-challenge.theumst.cn
   ```

5. Return to Certbot and press Enter.
6. Do not remove the TXT values until Certbot reports success.

After certificate issuance, the same script installs Nginx and performs the public
health checks. Manual DNS certificates do not renew unattended; rerun the CN
certificate/deployment flow before expiry. A successful run ends with:

```text
Deployment complete: https://theumst.cn
```

## 5.2 Create and promote Christopher on CN

1. Open `https://theumst.cn/signup` if the account does not exist.
2. Create the unique username `christopher`.
3. Run:

```powershell
.\dev\bat\make_christopher_superadmin.bat CN
```

## 5.3 Verify CN

```powershell
curl.exe -f https://theumst.cn/
curl.exe -f https://theumst.cn/health
curl.exe -f https://theumst.cn/health/db
curl.exe -f https://theumst.cn/health/qdrant
curl.exe -f https://theumst.cn/health/assets
```

---

# 6. Redeploy an update

Run the same target command again:

```powershell
.\dev\bat\deploy_com.bat
```

or:

```powershell
.\dev\bat\deploy_cn.bat
```

Docker rebuilds changed layers, existing PostgreSQL/Qdrant/storage volumes remain,
and idempotent SQL migrations are reapplied by the backend at startup.

---

# 7. Roles and dashboard access

Dashboard access points are rows in `access` and are assigned through
`authority_access_map`.

| Authority | Profile | API keys | Admin | Superadmin |
|---|---:|---:|---:|---:|
| user | yes | yes | no | no |
| admin | yes | yes | yes | no |
| superadmin | yes | yes | yes | yes |

The Admin page contains Qdrant search and object-storage management. Arbitrary
PostgreSQL execution exists only on the Superadmin page.

The public team page contains only:

- Chris;
- Randall — Strategy Advisor.

---

# 8. API keys

A new key is a regular read key:

- 120 requests per rolling one-hour database window;
- default page size 25;
- maximum page size 100.

Admins and superadmins may upgrade their own active key to a master key. A master
key has no application rate limit and can:

- read up to 1,000 knowledge objects per request;
- submit book-and-section-scoped knowledge objects;
- attach structured semantic projections and vectors;
- create storage folders;
- write text objects;
- upload files.

Supply keys as either:

```http
X-API-Key: <key>
```

or:

```http
Authorization: Bearer <key>
```

The full key is displayed only once at creation.

## Reading API

```bash
curl -H "X-API-Key: $UMST_API_KEY" \
  "https://theumst.com/api/v1/knowledge?language_id=1&limit=25&offset=0"
```

Available filters include:

```text
grimoire_id
section_id
type
language_id
limit
offset
```

## Master knowledge submission

Every submitted object must identify both a book and a section:

```json
{
  "book": {
    "isbn": "978-0-000000-00-0",
    "version": "1"
  },
  "section": {
    "section_number": "1.2"
  },
  "knowledge": {
    "language_id": 1,
    "type": "example",
    "statement": "A row containing 0 = 1 makes the system inconsistent.",
    "working": "The final augmented row represents a contradiction.",
    "is_default_in_crystal": true,
    "likes": 0
  },
  "embeddings": []
}
```

```bash
curl -X POST https://theumst.com/api/v1/knowledge \
  -H "X-API-Key: $UMST_MASTER_KEY" \
  -H "Content-Type: application/json" \
  --data @knowledge.json
```

Embeddings may also be attached later:

```bash
curl -X POST https://theumst.com/api/v1/knowledge/42/embeddings \
  -H "X-API-Key: $UMST_MASTER_KEY" \
  -H "Content-Type: application/json" \
  --data @embeddings.json
```

The PostgreSQL `embedding_id` UUID is used as the corresponding Qdrant point ID.

## Master storage API

Create a folder:

```bash
curl -X POST https://theumst.com/api/v1/storage/folders \
  -H "X-API-Key: $UMST_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"path":"books","name":"artin"}'
```

Upload a file:

```bash
curl -X POST https://theumst.com/api/v1/storage/files \
  -H "X-API-Key: $UMST_MASTER_KEY" \
  -F folder=books/artin \
  -F file=@chapter.pdf
```

---

# 9. Qdrant

PostgreSQL stores semantic-projection structure and indexing state. Qdrant stores
the vectors. The Admin page supports filtered Qdrant similarity search.

Raw-vector search works immediately. Text-to-vector Admin search additionally
requires an OpenAI-compatible embeddings provider in `.env`:

```dotenv
EMBEDDING_API_URL=
EMBEDDING_API_KEY=
EMBEDDING_MODEL=
```

Its output dimension must equal `QDRANT_VECTOR_SIZE`.

Qdrant is intentionally reachable only inside Docker in production. Do not publish
port 6333 on a public server.

---

# 10. Operations

## Remote logs

From Git Bash:

```bash
source dev/sh/_common.sh
load_env
remote_logs COM
remote_logs CN
```

## PostgreSQL backup

COM example:

```bash
source dev/sh/_common.sh
load_env
remote_context COM
ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" \
  "cd '$REMOTE_ROOT' && $(remote_sudo) docker compose --env-file .env -f compose.deploy.yml exec -T db pg_dump -U postgres theumst" \
  > theumst-com.sql
```

## Qdrant backup

Use Qdrant snapshots rather than copying a live Docker volume. Create snapshots
through the Qdrant API from inside the server network, then copy the snapshot to
protected storage.

## Stop a remote stack

```bash
source dev/sh/_common.sh
load_env
remote_stop COM
```

or:

```bash
source dev/sh/_common.sh
load_env
remote_stop CN
```

---

# 11. Tests

Backend:

```bash
cd backend/python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

On Windows PowerShell:

```powershell
cd backend\python
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q
```

Frontend production builds:

```bash
cd frontend/webpage && npm ci && npm run build
cd ../dashboard && npm ci && npm run build
```

Deployment-script syntax:

```bash
bash -n dev/sh/*.sh
```

---

# 12. Troubleshooting

## SSH key not found

Confirm the key exists at:

```text
%USERPROFILE%\.ssh\chris-theumst-com.pem
%USERPROFILE%\.ssh\chris-theumst-cn.pem
```

Keep `SSH_KEY_DIR=__AUTO__` in `.env` when using `deploy_com.bat` or
`deploy_cn.bat`. The wrappers now translate `%USERPROFILE%\.ssh` correctly for
both WSL (`/mnt/c/...`) and Git Bash (`/c/...`). For a custom key directory, set
an absolute value such as `SSH_KEY_DIR=C:/keys/theumst` and rerun the same batch
file.

## Certificate validation fails

Confirm:

- the domain resolves to the selected server;
- provider firewalls allow ports 80 and 443;
- no unrelated process is occupying port 80;
- for CN, the TXT record shown by Certbot resolves publicly before pressing Enter.

Then rerun the same deployment command.

## Production containers fail to become healthy

Connect and inspect logs:

```bash
source dev/sh/_common.sh
load_env
remote_logs COM
```

Check the target-only server environment:

```bash
source dev/sh/_common.sh
load_env
remote_context COM
ssh "${SSH_OPTIONS[@]}" -i "$KEY" "$REMOTE" \
  "cd '$REMOTE_ROOT' && $(remote_sudo) docker compose --env-file .env -f compose.deploy.yml ps"
```

## Resetting data

Never run `down -v` on a production server unless intentionally deleting the
PostgreSQL database, Qdrant vectors, and local storage volume.

---

# 13. Security notice

The included `.env` contains the deployment credentials supplied for this build.
It is excluded from Git and uploaded to each server with mode `600`.

Because these credentials were transmitted as message text and are also present in
the downloadable archive, rotate them after the first successful deployment:

- DigitalOcean Spaces access key and secret;
- Aliyun OSS access key and secret;
- both server sudo passwords;
- PostgreSQL password;
- Qdrant API key.

After rotation, update only the local `.env` and rerun the deployment command for
the relevant target. The script regenerates the target-specific remote `.env`.
