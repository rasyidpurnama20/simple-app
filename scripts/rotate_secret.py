#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from obe.shared.secret_rotation import SECRET_FILE_NAMES, revoke_previous, rotate_secret


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rotasi secret OBE ke berkas privat tanpa mencetak nilainya"
    )
    parser.add_argument("secret_type", choices=sorted(SECRET_FILE_NAMES))
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--revoke-previous", action="store_true")
    args = parser.parse_args()
    if args.revoke_previous:
        changed = revoke_previous(args.directory, args.secret_type)
        print("Versi sebelumnya dicabut." if changed else "Tidak ada versi sebelumnya.")
        return
    result = rotate_secret(args.directory, args.secret_type)
    print(f"Rotasi selesai pada {result['rotated_at']}; nilai secret tidak ditampilkan.")


if __name__ == "__main__":
    main()
