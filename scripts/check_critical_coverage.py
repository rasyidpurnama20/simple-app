#!/usr/bin/env python3
import json
import sys
from pathlib import Path

CRITICAL_DOMAINS = {
    "assessment",
    "curriculum",
    "identity",
    "learning",
    "secure_exam",
    "shared",
}
MINIMUM = 85.0


def domain_coverage(report: dict, domain: str) -> float:
    statements = covered = 0
    prefix = f"obe/{domain}/"
    for filename, details in report.get("files", {}).items():
        if not filename.startswith(prefix) or "/migrations/" in filename:
            continue
        summary = details["summary"]
        statements += int(summary["num_statements"])
        covered += int(summary["covered_lines"])
    if statements == 0:
        raise ValueError(f"Tidak ada data coverage untuk modul kritis {domain}")
    return covered * 100 / statements


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "coverage.json")
    report = json.loads(path.read_text(encoding="utf-8"))
    failures = []
    for domain in sorted(CRITICAL_DOMAINS):
        percent = domain_coverage(report, domain)
        print(f"{domain}: {percent:.2f}%")
        if percent < MINIMUM:
            failures.append(f"{domain} {percent:.2f}% < {MINIMUM:.0f}%")
    if failures:
        print("Critical coverage gate gagal: " + "; ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
