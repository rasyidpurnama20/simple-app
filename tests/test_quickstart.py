import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_script(script: Path, cwd: Path, env: dict[str, str] | None = None):
    return subprocess.run(  # noqa: S603
        ["/bin/sh", str(script)],
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def copy_setup_files(tmp_path: Path) -> Path:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(ROOT / ".env.example", tmp_path / ".env.example")
    shutil.copy2(ROOT / "scripts/setup-local.sh", scripts / "setup-local.sh")
    return scripts


def demo_password(env_file: Path) -> str:
    line = next(
        line
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if line.startswith("OBE_DEMO_PASSWORD=")
    )
    return line.partition("=")[2]


def test_setup_repairs_blank_password_and_is_idempotent(tmp_path):
    scripts = copy_setup_files(tmp_path)
    shutil.copy2(tmp_path / ".env.example", tmp_path / ".env")

    first = run_script(scripts / "setup-local.sh", tmp_path)
    assert first.returncode == 0, first.stderr
    password = demo_password(tmp_path / ".env")
    assert len(password) == 32

    second = run_script(scripts / "setup-local.sh", tmp_path)
    assert second.returncode == 0, second.stderr
    assert demo_password(tmp_path / ".env") == password


def test_quickstart_cleans_old_containers_and_reports_credentials(tmp_path):
    scripts = copy_setup_files(tmp_path)
    shutil.copy2(ROOT / "scripts/quickstart.sh", scripts / "quickstart.sh")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    docker_log = tmp_path / "docker.log"
    docker = fake_bin / "docker"
    docker.write_text(
        '#!/bin/sh\nprintf "%s %s\\n" "${OBE_HTTP_PORT:-unset}" "$*" >> "$DOCKER_LOG"\nexit 0\n',
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["DOCKER_LOG"] = str(docker_log)

    result = subprocess.run(  # noqa: S603
        ["/bin/sh", str(scripts / "quickstart.sh"), "--clean", "--port", "8088"],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Mengunduh image Nginx melalui Docker Compose" in result.stdout
    assert "OBE Apps siap: http://localhost:8088" in result.stdout
    assert f"Password      : {demo_password(tmp_path / '.env')}" in result.stdout
    calls = docker_log.read_text(encoding="utf-8")
    assert "8088 compose pull nginx" in calls
    assert "8088 compose down --remove-orphans" in calls
    assert "8088 compose up --build --detach --remove-orphans" in calls
    assert "8088 compose exec -T nginx nginx -t" in calls
    assert "8088 compose exec -T nginx wget -q --spider http://127.0.0.1/healthz/" in calls
    assert calls.index("compose pull nginx") < calls.index("compose up --build")


def test_quickstart_rejects_invalid_port_before_using_docker(tmp_path):
    scripts = copy_setup_files(tmp_path)
    shutil.copy2(ROOT / "scripts/quickstart.sh", scripts / "quickstart.sh")

    result = subprocess.run(  # noqa: S603
        ["/bin/sh", str(scripts / "quickstart.sh"), "--port", "invalid"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "port harus berupa angka 1-65535" in result.stderr


def test_nginx_runtime_contract_is_self_contained_and_health_checked():
    nginx = (ROOT / "deploy/nginx/nginx.conf").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "/etc/nginx/proxy_params" not in nginx
    for header in ("Host", "X-Real-IP", "X-Forwarded-For", "X-Forwarded-Proto"):
        assert f"proxy_set_header {header}" in nginx
    assert "${OBE_HTTP_PORT:-8000}:80" in compose
    assert "web: {condition: service_healthy}" in compose
    assert '["CMD", "wget", "-q", "--spider", "http://127.0.0.1/healthz/"]' in compose
    assert "docker compose config --quiet" in workflow
    assert "--add-host web:127.0.0.1" in workflow
    assert "nginx:1.28.0-alpine nginx -t" in workflow
