from __future__ import annotations

import hashlib
import shlex
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



def test_backend_container_uses_unambiguous_asgi_module():
    dockerfile = (ROOT / "backend/python/Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.count('"app.main:app"') == 2
    assert '"app:app"' not in dockerfile


def test_production_proxy_is_loopback_only_and_matches_host_nginx():
    compose_text = (ROOT / "compose.deploy.yml").read_text(encoding="utf-8")
    assert '127.0.0.1:${HTTP_PORT:-8080}:80' in compose_text
    for name in ("nginx.server.com.conf", "nginx.server.cn.conf"):
        text = (ROOT / "config" / name).read_text(encoding="utf-8")
        assert "proxy_pass http://127.0.0.1:8080;" in text
        assert "proxy_pass http://127.0.0.1:8000;" not in text


def test_master_book_ingestion_has_a_route_scoped_one_gibibyte_limit():
    host = (ROOT / "config/nginx.server.com.conf").read_text(encoding="utf-8")
    internal = (ROOT / "config/nginx.docker.conf").read_text(encoding="utf-8")
    for text in (host, internal):
        assert "client_max_body_size 50m;" in text
        route = text.split("location = /api/v1/books/ingest-archive", 1)[1].split("}", 1)[0]
        assert "client_max_body_size 1g;" in route


def test_compose_files_are_valid_yaml_and_have_required_services():
    for name in ("compose.local.yml", "compose.deploy.yml"):
        document = yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))
        assert {"db", "qdrant", "backend", "demo"}.issubset(document["services"])
    production = yaml.safe_load((ROOT / "compose.deploy.yml").read_text(encoding="utf-8"))
    assert "nginx" in production["services"]
    assert production["services"]["nginx"]["depends_on"]["demo"]["condition"] == "service_started"


def test_production_demo_is_isolated_and_proxy_protected():
    dockerfile = (ROOT / "frontend/demo/Dockerfile").read_text(encoding="utf-8")
    nginx = (ROOT / "config/nginx.docker.conf").read_text(encoding="utf-8")
    assert "FROM nginx:1.27-alpine AS production" in dockerfile
    assert "auth_request /_demo_auth;" in nginx
    assert "proxy_pass http://demo:80;" in nginx
    assert "error_page 401 403 = @demo_gate;" in nginx
    assert "location @demo_gate" in nginx
    assert "absolute_redirect off;" in nginx
    assert "return 303 /dashboard/demo/;" in nginx


def test_agent_deployment_and_complete_readme_are_present():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/operations.md" in readme
    operations = (ROOT / "docs/operations.md").read_text(encoding="utf-8")
    assert "COM" in operations and "CN" in operations
    assert "backup" in operations.lower()
    script = (ROOT / "dev/sh/agent_deploy.sh").read_text(encoding="utf-8")
    assert 'remote_full_deploy "$TARGET"' in script
    assert 'chmod 600 "$RUNTIME_SSH_KEY_DIR/$KEY_NAME"' in script
    assert 'trap cleanup_runtime_key EXIT' in script



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
    # Git Bash canonicalises the Windows temporary directory to /tmp while
    # WSL and native shells may preserve a drive-qualified path.  The contract
    # is that remote_context uses the supplied wrapper directory and key name,
    # not that every Bash implementation prints the same path spelling.
    normalized = completed.stdout.replace("\\", "/")
    assert normalized.endswith("/windows-profile/.ssh/chris-theumst-com.pem")

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
    upload = text.split("remote_upload() {", 1)[1].split("\nremote_start() {", 1)[0]
    start = text.split("remote_start() {", 1)[1].split(
        "\nremote_apply_reviewed_migrations() {",
        1,
    )[0]
    release = text.split("remote_full_deploy() {", 1)[1]

    assert "$SUDO mkdir -p '$REMOTE_ROOT'" in permissions
    assert "up --build -d --no-deps backend demo" in start
    assert "up -d --no-deps --force-recreate nginx" in start
    assert "--remove-orphans" not in start
    for section in (upload, start, release):
        assert '$SUDO rm -rf \\"\\$previous\\"' not in section
        assert "$SUDO rm -rf '${REMOTE_ROOT}.previous'" not in section


def _bash_result(commands: list[str]) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash is not installed")
    return subprocess.run(
        [bash, "-c", "\n".join([
            "set -euo pipefail",
            "source " + shlex.quote((ROOT / "dev/sh/_common.sh").as_posix()),
            *commands,
        ])],
        capture_output=True, text=True,
    )


def _source_revision(directory: Path) -> subprocess.CompletedProcess[str]:
    return _bash_result([
        "ROOT=" + shlex.quote(directory.as_posix()),
        "release_source_revision",
    ])


def test_release_revision_accepts_explicit_export_metadata(tmp_path):
    revision = "a1" * 20
    (tmp_path / "RELEASE_REVISION").write_text(revision + "\n")
    result = _source_revision(tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == revision


@pytest.mark.parametrize("invalid", ["", "a" * 39, "g" * 40, "a" * 40 + "\nother"])
def test_release_revision_rejects_invalid_export_metadata(tmp_path, invalid):
    (tmp_path / "RELEASE_REVISION").write_text(invalid)
    result = _source_revision(tmp_path)
    assert result.returncode != 0
    assert "40 hexadecimal" in result.stderr


def test_release_revision_requires_exact_repository_root_and_clean_head(tmp_path):
    git = shutil.which("git")
    if not git:
        pytest.skip("git is not installed")
    def run_git(*args):
        return subprocess.run([git, "-C", str(tmp_path), *args], check=True, capture_output=True, text=True).stdout.strip()

    run_git("init")
    run_git("config", "user.name", "Deployment fixture")
    run_git("config", "user.email", "deployment@example.invalid")
    (tmp_path / "app.txt").write_text("committed source\n")
    run_git("add", "app.txt")
    run_git("commit", "-m", "Fixture source")
    revision = run_git("rev-parse", "HEAD")
    result = _source_revision(tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == revision
    nested = tmp_path / "nested-export"
    nested.mkdir()
    assert _source_revision(nested).returncode != 0
    (tmp_path / "app.txt").write_text("uncommitted edit\n")
    assert _source_revision(tmp_path).returncode != 0
    run_git("restore", "app.txt")
    (tmp_path / "untracked.txt").write_text("extra source\n")
    assert _source_revision(tmp_path).returncode != 0


@pytest.mark.parametrize("tamper", [False, True])
def test_upload_verifies_transferred_bytes_before_changing_source(tmp_path, tamper):
    source = tmp_path / "source"
    destination = tmp_path / "remote-app"
    source.mkdir()
    destination.mkdir()
    revision = "b2" * 20
    (source / "RELEASE_REVISION").write_text(revision + "\n")
    (source / "compose.deploy.yml").write_text("services: {}\n")
    (source / "app.txt").write_text("new application\n")
    (destination / "app.txt").write_text("previous application\n")
    remote_archive = tmp_path / "remote-upload.tar.gz"
    remote_stage = tmp_path / "remote-incoming"
    archive_copy = tmp_path / "retained-upload.tar.gz"
    # Run the real packaging/extraction commands against temporary directories.
    # Only transport, target configuration and ownership changes are substituted.
    result = _bash_result([
        *[
            name + '="$(normalize_host_path ' + shlex.quote(path.as_posix()) + ')"'
            for name, path in [
                ("ROOT", source), ("TEST_REMOTE_ROOT", destination),
                ("TEST_REMOTE_ARCHIVE", remote_archive),
                ("TEST_REMOTE_STAGE", remote_stage), ("TEST_ARCHIVE_COPY", archive_copy),
            ]
        ],
        "remote_context() { TARGET_SERVER=COM; REMOTE_ROOT=$TEST_REMOTE_ROOT; SSH_OPTIONS=(); KEY=unused; REMOTE=local; SSH_USER=fixture; }",
        "remote_sudo() { :; }",
        "build_remote_env() { printf 'SERVER=COM\\n' > \"$2\"; }",
        "chown() { :; }; export -f chown",
        "scp() { cp \"${@: -2:1}\" \"$TEST_ARCHIVE_COPY\"; cp \"$TEST_ARCHIVE_COPY\" \"$TEST_REMOTE_ARCHIVE\"; "
        + ("printf 'changed in transit' >> \"$TEST_REMOTE_ARCHIVE\"; " if tamper else "") + "}",
        "ssh() { local script=\"${@: -1}\"; script=${script//\"$remote_stage\"/\"$TEST_REMOTE_STAGE\"}; script=${script//\"$remote_archive\"/\"$TEST_REMOTE_ARCHIVE\"}; bash -c \"$script\"; }",
        "remote_upload COM",
    ])
    digest = hashlib.sha256(archive_copy.read_bytes()).hexdigest()
    assert "Deployment archive SHA-256: " + digest in result.stdout
    assert "Source revision: " + revision in result.stdout
    if tamper:
        assert result.returncode != 0
        assert "SHA-256 mismatch" in result.stderr
        assert (destination / "app.txt").read_text() == "previous application\n"
        assert not Path(str(destination) + ".previous").exists()
        assert not remote_stage.exists()
        assert remote_archive.exists()
    else:
        assert result.returncode == 0, result.stderr
        assert (destination / "app.txt").read_text() == "new application\n"
        assert (destination / "RELEASE_REVISION").read_text().strip() == revision
        assert (destination / "DEPLOYMENT_ARCHIVE_SHA256").read_text().strip() == digest
        assert (destination / ".env").read_text() == "SERVER=COM\n"
        assert (Path(str(destination) + ".previous") / "app.txt").read_text() == "previous application\n"
        assert not remote_archive.exists()
