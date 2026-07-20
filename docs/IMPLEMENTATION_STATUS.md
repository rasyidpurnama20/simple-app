# Status Implementasi

Baseline ini menyediakan aplikasi runnable, schema/migration, service deterministik, UI awal, asset offline, deployment manifests, dan quality gate. Status ini bukan sign-off production.

| Area | Tersedia | Gate lanjutan lingkungan institusi |
|---|---|---|
| Platform | Modular boundary, lima profil, SOPS, immutable-digest Compose, Ansible, PostgreSQL concurrency guard, private evidence CAS, bounded queues, outbox/inbox, OTLP telemetry, scoped RBAC/MFA, append-only audit, versioned flags/kill switches, migrations dan rules | Host-kosong/reboot/restore rehearsal, authenticated DAST/pentest, broker/worker fault injection, alert rehearsal, load test, image digest approval |
| OBE core | Lifecycle kurikulum maker-reviewer-approver-activator, paket JSON/CSV ber-checksum, seed exact 5/12/18/31/77, weighted trace dua arah, RPS checksum approval/16 minggu, CPMK-RPS/Sub-CPMK/indikator, blueprint asesmen 100%, rubrik/butir/grading/regrade berversi, registry rule/package, decision/replay, integrity gate, evidence, formula/snapshot attainment fail-closed, trace eksekusi dua arah, portfolio reproducible, Provus/CQI effectiveness, PPEPP empat aktor, feedback privat | Keputusan Prodi atas 129 SKS wajib dan CPMK22/CPMK27 tanpa mapping, UAT dokumen RPS/kalender/moderasi, golden calculation/target institusi, assignment TPMF aktual, policy feedback anonim, rekonsiliasi SIA |
| Analytics | Semantic JSON contract, ETag, local ECharts, table fallback | Semua 8 visual, low-n policy, data 10× pilot |
| AI | LiteLLM-only gateway, data-class guard, AI-off fallback | Golden eval, model benchmark, quota tuning |
| Secure Exam | Authoring/session/response schema, signed bundle, Edge Compose | Encryption key ceremony, SEB/VLAN, 40-seat rehearsal, UPS/power test |
| Academic lifecycle | Status, IRS decision, result, GPA/progress, task/notification schema | Integrasi SIA, kalender institusi, MBKM/PKL/KKN/TA UAT |
| Operations | Server/Edge Compose, specialized workers, Nginx TLS, Ansible, SOPS, Restic, OTel/Prometheus/Loki/Tempo/Grafana, idempotent ops/runbooks | Staging cold deploy, off-host restore, 24-hour SLO/alert rehearsal, DR and go-live sign-off |

Release wajib diblokir sampai UAT critical 100%, total UAT ≥90%, mismatch angka 0, temuan critical/high 0, dan seluruh sign-off PR-87/PR-88 selesai.

Dataset v5 saat ini sengaja tetap `review`: katalog sumber memuat 129 SKS wajib (gate tepat 126) dan tidak menyediakan relasi untuk CPMK22 serta CPMK27. Validator PR-19–PR-24 mendeteksi ketiganya sebagai blocker; aplikasi tidak membuat koreksi atau equal-split otomatis.

Irisan learning/assessment v5 `MIK1624101` tersedia untuk demonstrasi PR-25–PR-29. Provenance `published-demo/fixture-only` dipertahankan, tetapi RPS aplikasi di-seed sebagai `draft`; publikasi resmi hanya melalui review GPM, approval Prodi, checksum yang sama, dan gate validasi lengkap.
