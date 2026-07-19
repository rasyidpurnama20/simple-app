#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from obe.deployment import load_environment_file, operation_plan, validate_deployment_environment


def main() -> None:
    parser = argparse.ArgumentParser(description="Operasi deployment OBE yang repeatable")
    parser.add_argument(
        "action",
        choices=["deploy", "migrate", "rollback", "restore", "rotate-secret", "smoke-test"],
    )
    parser.add_argument("--compose-file", type=Path, default=Path("deploy/server/compose.yml"))
    parser.add_argument("--deployment-env-file", type=Path, default=Path(".env"))
    parser.add_argument("--data-root", type=Path, default=Path("/srv/obe"))
    parser.add_argument("--image", default="")
    parser.add_argument("--component", default="")
    parser.add_argument("--snapshot", default="latest")
    parser.add_argument("--secret-type", default="")
    parser.add_argument("--secret-directory", type=Path)
    parser.add_argument("--base-url", default="https://127.0.0.1")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.action in {"deploy", "migrate", "rollback"}:
        if args.deployment_env_file.is_file():
            for name, value in load_environment_file(args.deployment_env_file).items():
                os.environ.setdefault(name, value)
        validate_deployment_environment(os.environ)
    plan = operation_plan(
        args.action,
        compose_file=args.compose_file,
        data_root=args.data_root,
        image=args.image,
        component=args.component,
        snapshot=args.snapshot,
        secret_type=args.secret_type,
        secret_directory=args.secret_directory,
        base_url=args.base_url,
    )
    for command in plan:
        if args.dry_run:
            print(" ".join(command.argv))
            continue
        command_env = os.environ.copy()
        command_env.update(dict(command.environment))
        subprocess.run(command.argv, check=True, env=command_env)  # noqa: S603


if __name__ == "__main__":
    main()
