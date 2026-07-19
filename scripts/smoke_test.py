#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import ssl
import time
import urllib.request


def probe(base_url: str, path: str, *, attempts: int = 10) -> dict:
    context = ssl.create_default_context()
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(
                f"{base_url.rstrip('/')}{path}", timeout=5, context=context
            ) as response:
                if response.status == 200:
                    return json.loads(response.read())
        except (OSError, ValueError):
            if attempt == attempts - 1:
                raise
            time.sleep(2)
    raise RuntimeError("Probe tidak mencapai status sehat")


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test health/readiness OBE")
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    assert probe(args.base_url, "/healthz/")["status"] == "ok"
    assert probe(args.base_url, "/readyz/")["status"] == "ready"
    print("Smoke test health/readiness lulus.")


if __name__ == "__main__":
    main()
