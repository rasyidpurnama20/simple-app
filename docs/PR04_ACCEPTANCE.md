# Audit penerimaan PR-04

| Kriteria spesifikasi | Implementasi | Bukti otomatis/operasional |
|---|---|---|
| Lima profil terpisah | `config/settings/{local,test,staging,production,exam_edge}.py` | validasi profil silang saat startup |
| Tidak ada secret di repo | `*_FILE`, template environment nonsecret, contoh SOPS terenkripsi | gitleaks CI + contract test SOPS |
| Startup fail-fast | `config/settings/runtime.py` | test missing/expired secret, URL, dan security mode |
| Rotasi/revokasi | `obe/shared/secret_rotation.py`, CLI rotasi | test overlap, permission `0600`, dan revoke |
| Zero downtime | Django fallbacks, fallback signature Exam Edge, overlap upstream | unit test session/signature contract + runbook |
| Tidak bocor ke output | filter log/error/API, OTel redaction, Celery events off | test accidental log/payload exposure |
| Prosedur operator | `docs/SECRETS_RUNBOOK.md`, `deploy/sops/README.md` | checklist rotasi dan insiden |

Secret scan CI harus hijau. Validasi rotasi PostgreSQL, LiteLLM, dan endpoint sync di staging tetap menjadi bukti lingkungan sebelum promosi production karena memerlukan layanan upstream institusi.
