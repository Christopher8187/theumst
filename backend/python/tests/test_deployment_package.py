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



def test_windows_deploy_wrappers_pass_userprofile_ssh_directory():
    for name in ("deploy_com.bat", "deploy_cn.bat"):
        text = (ROOT / "dev/bat" / name).read_text(encoding="utf-8")
        assert 'set "THEUMST_SSH_KEY_DIR=%USERPROFILE%\\.ssh"' in text
        assert "THEUMST_SSH_KEY_DIR/p" in text


def test_shell_normalizes_raw_windows_ssh_directory():
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash is not installed")

    command = "\n".join([
        f"source {str(ROOT / 'dev/sh/_common.sh')!r}",
        r"normalize_host_path 'C:\Users\Chris\.ssh'",
    ])
    completed = subprocess.run(
        [bash, "-c", command],
        check=True,
        capture_output=True,
        text=True,
    )
    normalized = completed.stdout.strip()
    assert normalized in {
        "/c/Users/Chris/.ssh",
        "/mnt/c/Users/Chris/.ssh",
    }


def test_shell_remote_context_uses_windows_wrapper_key_directory(tmp_path):
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash is not installed")

    key_dir = tmp_path / "windows-profile" / ".ssh"
    key_dir.mkdir(parents=True)
    expected_key = key_dir / "chris-theumst-com.pem"
    expected_key.write_text("test key placeholder", encoding="utf-8")

    command = "\n".join([
        "set -euo pipefail",
        f"export THEUMST_SSH_KEY_DIR={str(key_dir)!r}",
        f"source {str(ROOT / 'dev/sh/_common.sh')!r}",
        "remote_context COM",
        "printf '%s' \"$KEY\"",
    ])
    completed = subprocess.run(
        [bash, "-c", command],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout == str(expected_key)

def test_shell_deployment_scripts_parse_when_bash_is_available():
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash is not installed")
    scripts = sorted((ROOT / "dev/sh").glob("*.sh"))
    subprocess.run([bash, "-n", *map(str, scripts)], check=True)


def test_remote_upload_uses_one_compressed_archive_not_recursive_scp():
    text = (ROOT / "dev/sh/_common.sh").read_text(encoding="utf-8")
    upload = text.split("remote_upload() {", 1)[1].split("\nremote_start() {", 1)[0]

    assert 'tar -czf "$archive"' in upload
    assert 'scp "${SSH_OPTIONS[@]}" -i "$KEY" "$archive"' in upload
    assert "scp \"${SSH_OPTIONS[@]}\" -i \"$KEY\" -r" not in upload
    assert upload.count('scp "${SSH_OPTIONS[@]}"') == 1
    assert "tar -xzf '$remote_archive'" in upload
    assert 'remote_stage="/tmp/${archive_name%.tar.gz}.incoming"' in upload
    assert "incoming='${REMOTE_ROOT}.incoming'" not in upload
    assert r"$SUDO mv \"\$incoming\" '$REMOTE_ROOT'" in upload
    assert "$SUDO chown -R '$SSH_USER:$SSH_USER' '$REMOTE_ROOT'" in upload
    assert "rm -f '$remote_archive'" in upload
    assert 'rm -rf -- "$work_dir"' in upload


def test_remote_nginx_install_reuses_files_from_uploaded_archive():
    text = (ROOT / "dev/sh/_common.sh").read_text(encoding="utf-8")
    install = text.split("remote_install_nginx_site() {", 1)[1].split(
        "\nremote_external_health() {", 1
    )[0]

    assert "scp " not in install
    assert "$REMOTE_ROOT/config/$NGINX_CONF" in install
    assert "$REMOTE_ROOT/config/certbot-renewal-pre.sh" in install
    assert "$REMOTE_ROOT/config/certbot-renewal-post.sh" in install


def test_remote_release_paths_use_sudo_under_var_www():
    text = (ROOT / "dev/sh/_common.sh").read_text(encoding="utf-8")
    permissions = text.split("remote_permissions() {", 1)[1].split("\nbuild_remote_env() {", 1)[0]
    start = text.split("remote_start() {", 1)[1].split("\nremote_stop() {", 1)[0]

    assert "$SUDO mkdir -p '$REMOTE_ROOT'" in permissions
    assert "$SUDO rm -rf '${REMOTE_ROOT}.previous'" in start
