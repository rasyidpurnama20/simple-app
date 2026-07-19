# Audit penerimaan PR-05–PR-07

| PR | Kriteria | Implementasi | Bukti |
|---|---|---|---|
| 05 | Compose server/edge, digest immutable, health/startup/resource/restart | `deploy/server`, `deploy/exam-edge`, preflight `obe.deployment` | contract test compose dan digest |
| 05 | Ansible host/TLS/firewall/backup/monitor/deploy | role `deploy/ansible/roles/obe` | idempotent task contract + staging rehearsal runbook |
| 05 | deploy/migrate/rollback/restore/rotate/smoke | `scripts/obe_ops.py`, `scripts/smoke_test.py` | deterministic operation-plan tests |
| 05 | maintenance dan volume terpisah | sentinel middleware, `/srv/obe/{component}` | middleware/compose tests |
| 06 | PostgreSQL, connection limits, schema/index/constraints | settings + migrations `0002_*` | migration drift/reversibility dan DB tests |
| 06 | UUID/version/effective/actors/optimistic lock | `VersionedModel`, `create_versioned`, `update_versioned` | stale-write/effective-period tests |
| 06 | transaction/deadlock/FK/query budget/p95 | shared services dan query middleware | rollback, retry, orphan protection, p95 tests |
| 07 | private content-addressed immutable repository | manifest/evidence services dan migrations | duplicate/tamper/permission-mode tests |
| 07 | AV/size/MIME/quota/status | ClamAV INSTREAM dan state machine | scan/quota/transition tests |
| 07 | scoped, expiring, audited download | evidence token/download endpoints | unauthorized/expiry/audit/checksum tests |
| 07 | encrypted off-host backup dan restore | Restic timer, inventory/restore verifier | selective/full restore checksum tests |

Host-kosong, reboot, TLS nyata, off-host Restic, serta benchmark dengan data institusi adalah gate lingkungan staging. Kode, preflight, dan prosedurnya tersedia; bukti lapangan harus dilampirkan sebelum promosi production.
