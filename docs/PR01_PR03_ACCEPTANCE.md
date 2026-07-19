# Acceptance PR-01–PR-03

Sumber normatif: `Spesifikasi_Utama_Pengembangan_OBE_Apps_PR-01-PR-88.md`, SHA-256 `f404527ecfd3b81000e8fcb640a469147c60d0308ef2930fdbe3811eae610be2`. Dokumen lain di repository adalah bukti implementasi, bukan sumber requirement baru.

| Requirement | Bukti implementasi | Verifikasi |
|---|---|---|
| PR-01 arsitektur dan ruang lingkup | domain modular, teknologi baseline, PostgreSQL source of truth, empat role utama dan scoped assignments, AI-off | `ARCHITECTURE.md`, settings/Compose, identity tests, AI-off tests |
| PR-01 ownership, flow, network, NFR | owner matrix, aliran data, enam zona, SLO/RPO/RTO, keputusan accepted | `ARCHITECTURE.md` |
| PR-02 struktur repository | domain packages, deploy, docs, fixtures, scripts, tests | layout repository dan `fixtures/README.md` |
| PR-02 batas dan graph | AST dependency graph, cycle/direct-model/direct-AI guard | `tests/test_architecture.py` |
| PR-02 template modul | template URL, permission, service, API, migration, test, audit, flag | `docs/module-template` dan contract test |
| PR-02 evolusi schema/API | expand/migrate/contract, versioning, reversibility | README dan `ARCHITECTURE.md` |
| PR-03 pipeline | lint, format, type, migration, test, coverage, dependency/secret scan, SBOM | `.github/workflows/ci.yml` |
| PR-03 artefak RC | JUnit, coverage XML/JSON, migration plan, SBOM, image ID | artifact upload pada CI |
| PR-03 PR contract | tujuan, schema, security, evidence, flag, rollback, data impact | PR template dan CODEOWNERS |
| PR-03 negative gates | migration/coverage helper tests, double test run, dependency dan secret scan | `test_quality_gate_contract.py`, CI logs |
| PR-03 server-side protection | PR + 1 approval + required checks + no direct push/bypass | ruleset yang dirinci di `CI_GOVERNANCE.md` |

Catatan: status server-side branch ruleset harus diverifikasi di GitHub Settings oleh repository administrator karena workflow tidak dapat menerapkan proteksi terhadap branch yang menjalankan workflow itu sendiri.
