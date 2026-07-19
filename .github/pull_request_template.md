## Tujuan

Jelaskan masalah, outcome pengguna, dan requirement PR-01–PR-88 yang dicakup.

## Perubahan

- [ ] Kode/service/UI
- [ ] Schema atau migration
- [ ] API/semantic contract
- [ ] Dokumentasi/runbook

## Keamanan dan privasi

Jelaskan RBAC/object scope, data class, audit, secret, upload, AI, atau Secure Exam yang terdampak.

## Pengujian dan bukti

Cantumkan unit/integration/contract/UAT, coverage, screenshot, benchmark, atau rehearsal evidence.

## Feature flag dan rollout

Sebutkan flag, state awal, target, owner, acceptance evidence, dan activation plan.

## Rollback dan dampak data

Jelaskan rollback aplikasi/migration, backward compatibility, rekonsiliasi, dan apakah data turunan perlu dibangun ulang.

## Checklist

- [ ] Tidak ada direct cross-domain model import
- [ ] Tidak ada direct AI/model access di luar gateway
- [ ] Migration deterministic dan reversible atau memiliki forward-fix plan
- [ ] Aksi kritis memiliki audit dan negative permission test
- [ ] AI-off tidak memblokir critical path
- [ ] Dokumentasi dan traceability diperbarui

