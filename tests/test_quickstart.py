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
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_LOG"\nexit 0\n',
        encoding="utf-8",
    )
    docker.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["DOCKER_LOG"] = str(docker_log)

    result = subprocess.run(  # noqa: S603
        ["/bin/sh", str(scripts / "quickstart.sh"), "--clean"],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "OBE Apps siap: http://localhost:8000" in result.stdout
    assert f"Password      : {demo_password(tmp_path / '.env')}" in result.stdout
    calls = docker_log.read_text(encoding="utf-8")
    assert "compose down --remove-orphans" in calls
    assert "compose up --build --detach --remove-orphans" in calls
    assert "compose exec -T web python -c" in calls
