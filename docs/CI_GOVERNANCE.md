# Tata Kelola CI dan Branch

## Required quality checks

Workflow `quality-gate` berjalan pada setiap pull request dan push ke `main`. Merge hanya layak dilakukan ketika job berikut hijau:

- `test`: lint, format, type check, migration drift/reversibility, architecture, test dua kali, coverage total dan coverage modul kritis minimal 85%, serta dependency audit.
- `secret-scan`: pemindaian seluruh history dengan Gitleaks.
- `sbom`: CycloneDX SBOM Python.
- `image-evidence`: build image release candidate dan immutable image ID.

Artefak setiap kandidat rilis terdiri dari JUnit test report, XML/JSON coverage, migration plan, SBOM, dan image digest.

## Branch protection `main`

Repository administrator wajib menerapkan ruleset berikut pada `main`:

1. Require a pull request before merging dengan minimal satu approval non-author.
2. Dismiss stale approvals dan require review from Code Owners.
3. Require conversation resolution.
4. Require status checks `test`, `secret-scan`, `sbom`, dan `image-evidence` agar up to date.
5. Block force push, deletion, dan direct push; rules berlaku juga untuk administrator.
6. Bypass hanya untuk akun break-glass bernama, dibatasi waktu, dan wajib memiliki audit incident.

`CODEOWNERS` memastikan perubahan selalu meminta review owner. Ruleset GitHub tetap merupakan kontrol server-side dan tidak dapat digantikan oleh file workflow.

## Rehearsal negatif

| Skenario | Kontrol yang harus gagal | Bukti otomatis |
|---|---|---|
| Kode lint/type error | Ruff/Mypy | job `test` |
| Migration drift atau irreversible | Django check/reversibility checker | migration plan + helper tests |
| Test order/state leak | dua eksekusi dengan proses/hash seed berbeda | JUnit + log job |
| Coverage modul kritis <85% | critical coverage checker | coverage JSON |
| Dependency rentan | `pip-audit` | log job |
| Secret/canary credential | Gitleaks full-history scan | job `secret-scan` |
| Rollback migration tidak tersedia | reversibility checker | helper test + migration plan |

Perubahan pada workflow juga diuji oleh `tests/test_quality_gate_contract.py` agar kontrol dan artefak PR-03 tidak hilang tanpa sengaja.
