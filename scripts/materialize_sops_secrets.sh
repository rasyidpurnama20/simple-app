#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ $# -ne 3 ]]; then
  echo "Pemakaian: $0 <staging|production|exam-edge> <encrypted.yaml> <output-directory>" >&2
  exit 2
fi

profile="$1"
encrypted_file="$2"
output_directory="$3"
case "$profile" in
  staging|production) mappings=(database_url:database_url django_secret_key:obe_secret_key litellm_api_key:litellm_api_key) ;;
  exam-edge) mappings=(database_url:edge_database_url django_secret_key:edge_secret_key exam_signing_key:edge_signing_key exam_sync_token:edge_sync_token) ;;
  *) echo "Profil tidak dikenal." >&2; exit 2 ;;
esac

command -v sops >/dev/null || { echo "sops belum terpasang." >&2; exit 1; }
[[ -f "$encrypted_file" ]] || { echo "Berkas terenkripsi tidak ditemukan." >&2; exit 1; }
install -d -m 700 "$output_directory"

for mapping in "${mappings[@]}"; do
  source_key="${mapping%%:*}"
  destination="${mapping##*:}"
  temporary="${output_directory}/.${destination}.tmp"
  trap 'rm -f "$temporary"' EXIT
  sops --decrypt --extract "[\"${source_key}\"]" "$encrypted_file" >"$temporary"
  [[ -s "$temporary" ]] || { echo "Nilai ${source_key} kosong." >&2; exit 1; }
  chmod 600 "$temporary"
  mv -f "$temporary" "${output_directory}/${destination}"
  trap - EXIT
done

echo "Secret untuk ${profile} tersedia dengan mode privat; nilainya tidak ditampilkan."
