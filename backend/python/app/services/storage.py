from __future__ import annotations

import mimetypes
import os
import shutil
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

from ..config import get_settings


def storage_mode() -> str:
    return get_settings().server


def clean_key(value: str = "") -> str:
    key = str(value or "").replace("\\", "/").strip("/")
    if key.startswith("/") or ".." in key.split("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    return key


def child_key(folder: str, name: str) -> str:
    clean_name = clean_key(name).split("/")[-1]
    return "/".join(part for part in (clean_key(folder), clean_name) if part)


def local_root() -> Path:
    raw = get_settings().local_storage_dir
    root = Path.home() / "theumst_storage" if not raw or raw == "__AUTO__" else Path(os.path.expandvars(raw)).expanduser()
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def local_path(key: str = "") -> Path:
    root = local_root()
    path = (root / clean_key(key)).resolve()
    if path != root and root not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid path")
    return path


def _iso(ts: float | int | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


@lru_cache(maxsize=8)
def _spaces_client_cached(region: str, endpoint: str, access_key: str, secret_key: str):
    import boto3

    bucket = os.getenv("DO_SPACES_BUCKET") or ""
    if endpoint and bucket and f"://{bucket}." in endpoint:
        scheme, rest = endpoint.split("://", 1)
        endpoint = f"{scheme}://{rest[len(bucket) + 1:]}"
    return boto3.client(
        "s3",
        region_name=region or None,
        endpoint_url=endpoint or None,
        aws_access_key_id=access_key or None,
        aws_secret_access_key=secret_key or None,
    )


def _spaces_client():
    return _spaces_client_cached(
        os.getenv("DO_SPACES_REGION") or "",
        os.getenv("DO_SPACES_ENDPOINT") or "",
        os.getenv("DO_SPACES_ACCESS_KEY_ID") or "",
        os.getenv("DO_SPACES_SECRET_ACCESS_KEY") or "",
    )


@lru_cache(maxsize=8)
def _oss_bucket_cached(endpoint: str, bucket_name: str, access_key: str, secret_key: str):
    import oss2

    auth = oss2.Auth(access_key, secret_key)
    return oss2.Bucket(auth, endpoint, bucket_name)


def _oss_bucket():
    return _oss_bucket_cached(
        os.getenv("ALIYUN_OSS_ENDPOINT") or "",
        os.getenv("ALIYUN_OSS_BUCKET") or "",
        os.getenv("ALIYUN_OSS_ACCESS_KEY_ID") or "",
        os.getenv("ALIYUN_OSS_SECRET_ACCESS_KEY") or "",
    )


def list_items(prefix: str = "") -> list[dict]:
    mode = storage_mode()
    prefix = clean_key(prefix)
    storage_prefix = f"{prefix}/" if prefix else ""

    if mode == "LOCAL":
        folder = local_path(prefix)
        if not folder.exists() or not folder.is_dir():
            raise HTTPException(status_code=404, detail="Folder not found")
        result = []
        for item in sorted(folder.iterdir(), key=lambda path: (path.is_file(), path.name.lower())):
            stat = item.stat()
            result.append({
                "name": item.name,
                "key": child_key(prefix, item.name),
                "type": "folder" if item.is_dir() else "file",
                "size": 0 if item.is_dir() else stat.st_size,
                "modified": _iso(stat.st_mtime),
            })
        return result

    if mode == "COM":
        response = _spaces_client().list_objects_v2(
            Bucket=os.getenv("DO_SPACES_BUCKET"), Prefix=storage_prefix, Delimiter="/"
        )
        folders = [{
            "name": item["Prefix"].rstrip("/").split("/")[-1],
            "key": item["Prefix"].rstrip("/"),
            "type": "folder", "size": 0, "modified": "",
        } for item in response.get("CommonPrefixes", [])]
        files = [{
            "name": item["Key"].split("/")[-1],
            "key": item["Key"], "type": "file", "size": item.get("Size", 0),
            "modified": item["LastModified"].isoformat() if item.get("LastModified") else "",
        } for item in response.get("Contents", []) if item["Key"] != storage_prefix and not item["Key"].endswith("/")]
        return folders + files

    if mode == "CN":
        import oss2

        result = []
        for item in oss2.ObjectIterator(_oss_bucket(), prefix=storage_prefix, delimiter="/"):
            if item.is_prefix():
                result.append({
                    "name": item.key.rstrip("/").split("/")[-1],
                    "key": item.key.rstrip("/"), "type": "folder", "size": 0, "modified": "",
                })
            elif item.key != storage_prefix and not item.key.endswith("/"):
                result.append({
                    "name": item.key.split("/")[-1], "key": item.key, "type": "file",
                    "size": getattr(item, "size", 0), "modified": _iso(getattr(item, "last_modified", 0)),
                })
        return result

    raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN")


def read_bytes(key: str) -> bytes:
    key = clean_key(key)
    mode = storage_mode()
    if mode == "LOCAL":
        path = local_path(key)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        return path.read_bytes()
    if mode == "COM":
        return _spaces_client().get_object(Bucket=os.getenv("DO_SPACES_BUCKET"), Key=key)["Body"].read()
    if mode == "CN":
        return _oss_bucket().get_object(key).read()
    raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN")


def write_bytes(key: str, data: bytes) -> str:
    key = clean_key(key)
    if not key:
        raise HTTPException(status_code=400, detail="A file path is required")
    mode = storage_mode()
    if mode == "LOCAL":
        path = local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    elif mode == "COM":
        _spaces_client().put_object(
            Bucket=os.getenv("DO_SPACES_BUCKET"), Key=key, Body=data,
            ContentType=media_type_for(key),
        )
    elif mode == "CN":
        _oss_bucket().put_object(key, data, headers={"Content-Type": media_type_for(key)})
    else:
        raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN")
    return key


def health() -> dict:
    """Verify the active storage destination without creating a probe object."""
    mode = storage_mode()
    if mode == "LOCAL":
        root = local_root()
        return {"ok": root.is_dir() and os.access(root, os.R_OK | os.W_OK), "mode": mode}
    if mode == "COM":
        bucket = os.getenv("DO_SPACES_BUCKET") or ""
        if not bucket:
            raise HTTPException(status_code=503, detail="Object storage is not configured")
        _spaces_client().list_objects_v2(Bucket=bucket, MaxKeys=1)
        return {"ok": True, "mode": mode}
    if mode == "CN":
        _oss_bucket().get_bucket_info()
        return {"ok": True, "mode": mode}
    raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN")



def public_url(key: str) -> str:
    """Return the stable URL stored beside an object-storage key."""
    from urllib.parse import quote

    key = clean_key(key)
    mode = storage_mode()
    if mode == "LOCAL":
        base = (os.getenv("LOCAL_URL") or "http://localhost:8080").rstrip("/")
        return f"{base}/api/v1/storage/{quote(key, safe='/')}"
    if mode in {"COM", "CN"}:
        base = get_settings().public_webpage_url.rstrip("/")
        return f"{base}/api/v1/storage/{quote(key, safe='/')}"
    raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN")


def signed_read_url(key: str, *, expires_seconds: int = 900) -> str:
    """Create a short-lived direct read URL while keeping cloud buckets private."""
    key = clean_key(key)
    expires = max(60, min(int(expires_seconds), 3600))
    mode = storage_mode()
    if mode == "LOCAL":
        return public_url(key)
    if mode == "COM":
        bucket = os.getenv("DO_SPACES_BUCKET") or ""
        if not bucket:
            raise HTTPException(status_code=500, detail="DO_SPACES_BUCKET is not configured")
        return _spaces_client().generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )
    if mode == "CN":
        return _oss_bucket().sign_url("GET", key, expires)
    raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN")

def create_folder(key: str) -> str:
    key = clean_key(key)
    if not key:
        raise HTTPException(status_code=400, detail="A folder path is required")
    mode = storage_mode()
    if mode == "LOCAL":
        local_path(key).mkdir(parents=True, exist_ok=True)
    elif mode == "COM":
        _spaces_client().put_object(Bucket=os.getenv("DO_SPACES_BUCKET"), Key=f"{key.rstrip('/')}/", Body=b"")
    elif mode == "CN":
        _oss_bucket().put_object(f"{key.rstrip('/')}/", b"")
    else:
        raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN")
    return key


def delete(key: str) -> None:
    key = clean_key(key)
    if not key:
        raise HTTPException(status_code=400, detail="Select a file or folder")
    mode = storage_mode()
    if mode == "LOCAL":
        path = local_path(key)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
        return
    prefix = f"{key.rstrip('/')}/"
    if mode == "COM":
        client = _spaces_client()
        bucket = os.getenv("DO_SPACES_BUCKET")
        response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        objects = [{"Key": item["Key"]} for item in response.get("Contents", [])]
        if objects:
            client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
        client.delete_object(Bucket=bucket, Key=key)
        return
    if mode == "CN":
        import oss2

        bucket = _oss_bucket()
        keys = [item.key for item in oss2.ObjectIterator(bucket, prefix=prefix)]
        if keys:
            bucket.batch_delete_objects(keys)
        bucket.delete_object(key)
        return
    raise HTTPException(status_code=400, detail="SERVER must be LOCAL, COM, or CN")


def media_type_for(key: str) -> str:
    return mimetypes.guess_type(key)[0] or "application/octet-stream"
