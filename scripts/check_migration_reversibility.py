#!/usr/bin/env python3
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def irreversible_operations(path: Path) -> list[str]:
    errors = []
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        operation = node.func.attr
        keywords = {keyword.arg for keyword in node.keywords}
        if operation == "RunPython" and len(node.args) < 2 and "reverse_code" not in keywords:
            errors.append(f"{path}: RunPython wajib memiliki reverse_code")
        if operation == "RunSQL" and len(node.args) < 2 and "reverse_sql" not in keywords:
            errors.append(f"{path}: RunSQL wajib memiliki reverse_sql")
    return errors


def main() -> int:
    failures = []
    for path in ROOT.glob("obe/*/migrations/[0-9]*.py"):
        failures.extend(irreversible_operations(path))
    if failures:
        raise SystemExit("\n".join(failures))
    print("Migration reversibility checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
