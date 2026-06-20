import hashlib
import mimetypes
import os
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from passlib.context import CryptContext
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=False)

FRONTEND = ROOT / "frontend"
WEBPAGE_DIST = FRONTEND / "webpage" / "dist"
DASHBOARD_DIST = FRONTEND / "dashboard" / "dist"
PUBLIC_IMAGES = FRONTEND / "assets" / "images"
COOKIE = "theumst_session"
SESSION_DAYS = int(os.getenv("SESSION_DAYS", "7"))

DEV_URLS = {
    "app": "theumst backend",
    "health": "/health",
    "api": "/api",
    "local_webpage": "http://localhost:5173",
    "local_dashboard": "http://localhost:5174",
}

WEBPAGE_HTML_ROUTES = {"news", "about", "wiki", "get", "login", "signup"}
BLOCKED_WEB_PATH_PREFIXES = ("backend/", "config/", "dev/")

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
app = FastAPI()

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if PUBLIC_IMAGES.exists():
    app.mount("/images", StaticFiles(directory=PUBLIC_IMAGES), name="images")


def safe_dist_file(dist: Path, path: str):
    target = (dist / path).resolve()
    return target if target.is_file() and dist.resolve() in target.parents else None


def serve_vue_app(dist: Path, path: str, not_built_detail: str):
    index = dist / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail=not_built_detail)

    if path and (target := safe_dist_file(dist, path)):
        return FileResponse(target)

    return FileResponse(index)


def is_blocked_web_path(path: str):
    clean = path.strip("/")
    return clean.startswith(BLOCKED_WEB_PATH_PREFIXES) or any(
        part.startswith(".") for part in clean.split("/") if part
    )


def serve_webpage(path: str = ""):
    if is_blocked_web_path(path):
        raise HTTPException(status_code=404)
    if not (WEBPAGE_DIST / "index.html").exists() and not path:
        return DEV_URLS
    return serve_vue_app(
        WEBPAGE_DIST,
        path,
        "Webpage Vue app is not built. Use Vite on localhost:5173 during local testing.",
    )


def connect():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "theumst"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
        cursor_factory=RealDictCursor,
    )


def h(value):
    return hashlib.sha256(value.encode()).hexdigest()


def wants_json(request: Request):
    accept = request.headers.get("accept", "")
    return "application/json" in accept or request.headers.get("x-requested-with") == "fetch"


def auth_redirect_or_json(request: Request, redirect_path: str, status_code: int = 303):
    if wants_json(request):
        return JSONResponse({"ok": True, "redirect": redirect_path})
    return RedirectResponse(redirect_path, status_code=status_code)


def auth_error_or_redirect(request: Request, redirect_path: str, detail: str, status_code: int = 400):
    if wants_json(request):
        return JSONResponse({"ok": False, "detail": detail}, status_code=status_code)
    return RedirectResponse(redirect_path, status_code=303)


def current_user(request):
    token = request.cookies.get(COOKIE)
    if not token:
        return None

    with connect() as con, con.cursor() as cur:
        cur.execute(
            """
            SELECT u.user_id, u.username, u.email, u.alias, u.description,
                   a.name AS authority_type
            FROM web_session s
            JOIN "user" u ON u.user_id = s.user_id
            JOIN authority a ON a.authority_id = u.authority_id
            WHERE s.token_hash = %s
              AND s.revoked_at IS NULL
              AND s.expires_at > now()
            """,
            (h(token),),
        )
        return cur.fetchone()


def require_user(request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401)
    return user


def require_role(request, roles):
    user = require_user(request)
    if user["authority_type"] not in roles:
        raise HTTPException(status_code=403)
    return user


def start_session(response, user_id):
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    with connect() as con, con.cursor() as cur:
        cur.execute(
            "INSERT INTO web_session (user_id, token_hash, expires_at) VALUES (%s, %s, %s)",
            (user_id, h(token), expires),
        )
    response.set_cookie(COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True, samesite="lax")


def storage_mode():
    return os.getenv("SERVER", "LOCAL").upper()


def clean_key(value=""):
    key = str(value or "").replace("\\", "/").strip("/")
    if key.startswith("/") or ".." in key.split("/"):
        raise HTTPException(status_code=400, detail="Invalid path.")
    return key


def child_key(folder, name):
    name = clean_key(name).split("/")[-1]
    return "/".join(part for part in [clean_key(folder), name] if part)


def local_root():
    raw = os.getenv("LOCAL_STORAGE_DIR", "__AUTO__")
    if not raw or raw == "__AUTO__":
        root = Path.home() / "theumst_storage"
    else:
        root = Path(os.path.expandvars(raw)).expanduser()
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def local_path(key=""):
    root = local_root()
    path = (root / clean_key(key)).resolve()
    if path != root and root not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid path.")
    return path


def iso_from_timestamp(ts):
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def do_client():
    import boto3

    bucket = os.getenv("DO_SPACES_BUCKET")
    endpoint = os.getenv("DO_SPACES_ENDPOINT")
    if endpoint and bucket and f"://{bucket}." in endpoint:
        scheme, rest = endpoint.split("://", 1)
        endpoint = f"{scheme}://{rest[len(bucket) + 1:]}"

    return boto3.client(
        "s3",
        region_name=os.getenv("DO_SPACES_REGION"),
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("DO_SPACES_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("DO_SPACES_SECRET_ACCESS_KEY"),
    )


def oss_bucket():
    import oss2

    auth = oss2.Auth(os.getenv("ALIYUN_OSS_ACCESS_KEY_ID"), os.getenv("ALIYUN_OSS_SECRET_ACCESS_KEY"))
    return oss2.Bucket(auth, os.getenv("ALIYUN_OSS_ENDPOINT"), os.getenv("ALIYUN_OSS_BUCKET"))


def storage_list(prefix=""):
    mode = storage_mode()
    prefix = clean_key(prefix)
    if prefix:
        prefix += "/"

    if mode == "LOCAL":
        folder = local_path(prefix)
        if not folder.exists():
            raise HTTPException(status_code=404, detail="Folder not found.")
        items = []
        for item in sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            stat = item.stat()
            items.append({
                "name": item.name,
                "key": child_key(prefix, item.name),
                "type": "folder" if item.is_dir() else "file",
                "size": 0 if item.is_dir() else stat.st_size,
                "modified": iso_from_timestamp(stat.st_mtime),
            })
        return items

    if mode == "COM":
        client = do_client()
        response = client.list_objects_v2(
            Bucket=os.getenv("DO_SPACES_BUCKET"),
            Prefix=prefix,
            Delimiter="/",
        )
        folders = [{
            "name": p["Prefix"].rstrip("/").split("/")[-1],
            "key": p["Prefix"].rstrip("/"),
            "type": "folder",
            "size": 0,
            "modified": "",
        } for p in response.get("CommonPrefixes", [])]
        files = [{
            "name": obj["Key"].split("/")[-1],
            "key": obj["Key"],
            "type": "file",
            "size": obj.get("Size", 0),
            "modified": obj.get("LastModified", "").isoformat() if obj.get("LastModified") else "",
        } for obj in response.get("Contents", []) if obj["Key"] != prefix and not obj["Key"].endswith("/")]
        return folders + files

    if mode == "CN":
        import oss2

        bucket = oss_bucket()
        items = []
        for obj in oss2.ObjectIterator(bucket, prefix=prefix, delimiter="/"):
            if obj.is_prefix():
                items.append({
                    "name": obj.key.rstrip("/").split("/")[-1],
                    "key": obj.key.rstrip("/"),
                    "type": "folder",
                    "size": 0,
                    "modified": "",
                })
            elif obj.key != prefix and not obj.key.endswith("/"):
                items.append({
                    "name": obj.key.split("/")[-1],
                    "key": obj.key,
                    "type": "file",
                    "size": getattr(obj, "size", 0),
                    "modified": iso_from_timestamp(getattr(obj, "last_modified", 0)),
                })
        return items

    raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN.")


def storage_read(key):
    key = clean_key(key)
    mode = storage_mode()

    if mode == "LOCAL":
        path = local_path(key)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="File not found.")
        return path.read_bytes()

    if mode == "COM":
        obj = do_client().get_object(Bucket=os.getenv("DO_SPACES_BUCKET"), Key=key)
        return obj["Body"].read()

    if mode == "CN":
        return oss_bucket().get_object(key).read()

    raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN.")


def storage_write(key, data):
    key = clean_key(key)
    if not key:
        raise HTTPException(status_code=400, detail="Please enter a file path.")
    mode = storage_mode()

    if mode == "LOCAL":
        path = local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return

    if mode == "COM":
        do_client().put_object(Bucket=os.getenv("DO_SPACES_BUCKET"), Key=key, Body=data)
        return

    if mode == "CN":
        oss_bucket().put_object(key, data)
        return

    raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN.")


def storage_create_folder(key):
    key = clean_key(key)
    if not key:
        raise HTTPException(status_code=400, detail="Please enter a folder name.")
    mode = storage_mode()

    if mode == "LOCAL":
        local_path(key).mkdir(parents=True, exist_ok=True)
        return

    folder_key = key.rstrip("/") + "/"
    if mode == "COM":
        do_client().put_object(Bucket=os.getenv("DO_SPACES_BUCKET"), Key=folder_key, Body=b"")
        return

    if mode == "CN":
        oss_bucket().put_object(folder_key, b"")
        return

    raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN.")


def storage_delete(key):
    key = clean_key(key)
    if not key:
        raise HTTPException(status_code=400, detail="Please select a file or folder.")
    mode = storage_mode()

    if mode == "LOCAL":
        path = local_path(key)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        return

    if mode == "COM":
        client = do_client()
        bucket = os.getenv("DO_SPACES_BUCKET")
        keys = [key]
        response = client.list_objects_v2(Bucket=bucket, Prefix=key.rstrip("/") + "/")
        keys += [obj["Key"] for obj in response.get("Contents", [])]
        for i in range(0, len(keys), 1000):
            client.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in keys[i:i + 1000]]})
        return

    if mode == "CN":
        bucket = oss_bucket()
        keys = [key]
        import oss2
        keys += [obj.key for obj in oss2.ObjectIterator(bucket, prefix=key.rstrip("/") + "/")]
        for i in range(0, len(keys), 1000):
            bucket.batch_delete_objects(keys[i:i + 1000])
        return

    raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN.")


@app.get("/")
def webpage_home():
    return serve_webpage()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/auth/signup")
async def signup(request: Request):
    form = await request.form()
    username = form.get("username", "").strip()
    email = form.get("email", "").strip().lower()
    password = form.get("password", "")

    if not username or not email or not password:
        return auth_error_or_redirect(request, "/signup?error=missing", "Username, email, and password are required.", 400)

    try:
        with connect() as con, con.cursor() as cur:
            cur.execute(
                """
                INSERT INTO "user" (authority_id, username, email, password_hash, alias, description)
                VALUES (1, %s, %s, %s, %s, '')
                RETURNING user_id
                """,
                (username, email, pwd.hash(password), username),
            )
            user_id = cur.fetchone()["user_id"]
    except psycopg2.errors.UniqueViolation:
        return auth_error_or_redirect(request, "/signup?error=exists", "Username or email is already used.", 409)
    except psycopg2.Error as exc:
        print("Signup database error:", exc)
        return auth_error_or_redirect(request, "/signup?error=database", "Database error during signup.", 500)

    response = auth_redirect_or_json(request, "/dashboard/profile/")
    start_session(response, user_id)
    return response


@app.post("/auth/login")
async def login(request: Request):
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")

    with connect() as con, con.cursor() as cur:
        cur.execute('SELECT user_id, password_hash FROM "user" WHERE username = %s OR email = %s', (username, username.lower()))
        user = cur.fetchone()

    if not user or not pwd.verify(password, user["password_hash"]):
        return auth_error_or_redirect(request, "/login?error=bad-login", "Incorrect username or password.", 401)

    response = auth_redirect_or_json(request, "/dashboard/profile/")
    start_session(response, user["user_id"])
    return response


@app.post("/auth/signout")
def signout(request: Request):
    token = request.cookies.get(COOKIE)
    if token:
        with connect() as con, con.cursor() as cur:
            cur.execute("UPDATE web_session SET revoked_at = now() WHERE token_hash = %s", (h(token),))
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE)
    return response


@app.get("/dashboard")
def dashboard_no_slash():
    return RedirectResponse("/dashboard/", status_code=303)


@app.get("/dashboard/{path:path}")
def dashboard_vue(path: str, request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if path.startswith("admin") and user["authority_type"] not in ("admin", "superadmin"):
        return RedirectResponse("/dashboard/profile/", status_code=303)
    if path.startswith("superadmin") and user["authority_type"] != "superadmin":
        return RedirectResponse("/dashboard/profile/", status_code=303)

    return serve_vue_app(DASHBOARD_DIST, path, "Dashboard Vue app is not built.")


@app.get("/api/me")
def get_me(request: Request):
    user = require_user(request)
    return {"user": dict(user)}


@app.put("/api/me")
async def update_me(request: Request):
    user = require_user(request)
    data = await request.json()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip().lower()
    alias = data.get("alias", "").strip()
    description = data.get("description", "").strip()

    if not username or not email:
        raise HTTPException(status_code=400, detail="Username and email are required.")

    try:
        with connect() as con, con.cursor() as cur:
            cur.execute(
                """
                UPDATE "user"
                SET username = %s, email = %s, alias = %s, description = %s
                WHERE user_id = %s
                RETURNING user_id, username, email, alias, description
                """,
                (username, email, alias, description, user["user_id"]),
            )
            row = dict(cur.fetchone())
            row["authority_type"] = user["authority_type"]
            return {"user": row}
    except psycopg2.Error:
        raise HTTPException(status_code=400, detail="Username or email is already used.")


@app.get("/api/api-keys")
def list_api_keys(request: Request):
    user = require_user(request)
    with connect() as con, con.cursor() as cur:
        cur.execute(
            """
            SELECT api_key_id, name, key_prefix, created_at, last_used_at, revoked_at
            FROM api_key
            WHERE user_id = %s
            ORDER BY api_key_id DESC
            """,
            (user["user_id"],),
        )
        return {"keys": [dict(row) for row in cur.fetchall()]}


@app.post("/api/api-keys")
async def create_api_key(request: Request):
    user = require_user(request)
    data = await request.json()
    name = data.get("name", "").strip()

    if not name:
        raise HTTPException(status_code=400, detail="Please enter a key name.")

    raw_key = "umst_" + secrets.token_urlsafe(32)
    with connect() as con, con.cursor() as cur:
        cur.execute(
            """
            INSERT INTO api_key (user_id, name, password_hash, key_prefix, key_hash)
            VALUES (%s, %s, '', %s, %s)
            RETURNING api_key_id, name, key_prefix, created_at
            """,
            (user["user_id"], name, raw_key[:14], h(raw_key)),
        )
        row = dict(cur.fetchone())
    row["key"] = raw_key
    return row


@app.post("/api/admin/sql")
async def run_admin_sql(request: Request):
    require_role(request, {"admin", "superadmin"})
    sql = (await request.json()).get("sql", "").strip()
    if not sql:
        raise HTTPException(status_code=400, detail="Please enter SQL code.")

    try:
        with connect() as con, con.cursor() as cur:
            cur.execute(sql)
            if cur.description:
                rows = [dict(row) for row in cur.fetchall()]
                return {"rows": rows, "row_count": len(rows)}
            return {"rows": [], "row_count": cur.rowcount}
    except psycopg2.Error as exc:
        raise HTTPException(status_code=400, detail=str(exc).strip())


@app.get("/api/admin/storage")
def list_admin_storage(request: Request, path: str = ""):
    require_role(request, {"admin", "superadmin"})
    path = clean_key(path)
    return {"mode": storage_mode(), "path": path, "items": storage_list(path)}


@app.get("/api/admin/storage/read")
def read_admin_storage(request: Request, path: str):
    require_role(request, {"admin", "superadmin"})
    data = storage_read(path)
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="This file is not UTF-8 text. Use download instead.")
    return {"path": clean_key(path), "content": content}


@app.get("/api/admin/storage/download")
def download_admin_storage(request: Request, path: str):
    require_role(request, {"admin", "superadmin"})
    key = clean_key(path)
    data = storage_read(key)
    filename = key.split("/")[-1] or "download"
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return StreamingResponse(
        iter([data]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/admin/storage/write")
async def write_admin_storage(request: Request):
    require_role(request, {"admin", "superadmin"})
    data = await request.json()
    storage_write(data.get("path", ""), data.get("content", "").encode("utf-8"))
    return {"ok": True}


@app.post("/api/admin/storage/folder")
async def create_admin_storage_folder(request: Request):
    require_role(request, {"admin", "superadmin"})
    data = await request.json()
    storage_create_folder(child_key(data.get("path", ""), data.get("name", "")))
    return {"ok": True}


@app.post("/api/admin/storage/upload")
async def upload_admin_storage(request: Request, file: UploadFile = File(...), folder: str = Form("")):
    require_role(request, {"admin", "superadmin"})
    storage_write(child_key(folder, file.filename), await file.read())
    return {"ok": True}


@app.delete("/api/admin/storage")
async def delete_admin_storage(request: Request, path: str):
    require_role(request, {"admin", "superadmin"})
    storage_delete(path)
    return {"ok": True}


@app.post("/api/superadmin/make-admin")
async def make_admin(request: Request):
    require_role(request, {"superadmin"})
    identifier = (await request.json()).get("identifier", "").strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="Please enter a user.")

    with connect() as con, con.cursor() as cur:
        cur.execute(
            """
            UPDATE "user"
            SET authority_id = (SELECT authority_id FROM authority WHERE name = 'admin')
            WHERE username = %s OR email = %s
            RETURNING user_id, username, email
            """,
            (identifier, identifier.lower()),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Could not find user.")
    return {"user": dict(row)}


@app.delete("/api/api-keys/{api_key_id}")
def revoke_api_key(api_key_id: int, request: Request):
    user = require_user(request)
    with connect() as con, con.cursor() as cur:
        cur.execute(
            "UPDATE api_key SET revoked_at = now() WHERE api_key_id = %s AND user_id = %s",
            (api_key_id, user["user_id"]),
        )
    return {"ok": True}


@app.get("/index.html")
def old_index_html():
    return RedirectResponse("/", status_code=303)


@app.get("/{page_name}.html")
def old_html_page(page_name: str):
    if page_name not in WEBPAGE_HTML_ROUTES:
        raise HTTPException(status_code=404)
    return RedirectResponse(f"/{page_name}", status_code=303)


@app.get("/{path:path}")
def webpage_vue(path: str):
    return serve_webpage(path)
