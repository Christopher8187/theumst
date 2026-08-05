from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]


def _env_keys() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip("'\"")
    return values


def test_complete_environment_contains_both_remote_targets():
    values = _env_keys()
    required = {
        "SERVER",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "QDRANT_API_KEY",
        "SSH_KEY_COM",
        "SSH_USER_COM",
        "SSH_HOST_COM",
        "REMOTE_ROOT_COM",
        "DOMAIN_COM",
        "DO_SPACES_BUCKET",
        "DO_SPACES_ACCESS_KEY_ID",
        "DO_SPACES_SECRET_ACCESS_KEY",
        "SSH_KEY_CN",
        "SSH_USER_CN",
        "SSH_HOST_CN",
        "REMOTE_ROOT_CN",
        "DOMAIN_CN",
        "ALIYUN_OSS_BUCKET",
        "ALIYUN_OSS_ACCESS_KEY_ID",
        "ALIYUN_OSS_SECRET_ACCESS_KEY",
    }
    assert values["SERVER"] == "COM"
    assert not sorted(key for key in required if not values.get(key))


def test_production_proxy_is_loopback_only_and_matches_host_nginx():
    compose_text = (ROOT / "compose.deploy.yml").read_text(encoding="utf-8")
    assert '127.0.0.1:${HTTP_PORT:-8080}:80' in compose_text
    for name in ("nginx.server.com.conf", "nginx.server.cn.conf"):
        text = (ROOT / "config" / name).read_text(encoding="utf-8")
        assert "proxy_pass http://127.0.0.1:8080;" in text
        assert "proxy_pass http://127.0.0.1:8000;" not in text


def test_compose_files_are_valid_yaml_and_have_required_services():
    for name in ("compose.local.yml", "compose.deploy.yml"):
        document = yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))
        assert {"db", "qdrant", "backend"}.issubset(document["services"])
    production = yaml.safe_load((ROOT / "compose.deploy.yml").read_text(encoding="utf-8"))
    assert "nginx" in production["services"]


def test_agent_deployment_and_complete_readme_are_present():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Deploy theumst.com from source to a live website" in readme
    assert "Deploy theumst.cn from source to a live website" in readme
    assert "Create and promote Christopher" in readme
    script = (ROOT / "dev/sh/agent_deploy.sh").read_text(encoding="utf-8")
    assert 'remote_full_deploy "$TARGET"' in script


def test_shell_deployment_scripts_parse_when_bash_is_available():
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash is not installed")
    scripts = sorted((ROOT / "dev/sh").glob("*.sh"))
    subprocess.run([bash, "-n", *map(str, scripts)], check=True)
