# Status Implementasi

Baseline ini menyediakan aplikasi runnable, schema/migration, service deterministik, UI awal, asset offline, deployment manifests, dan quality gate. Status ini bukan sign-off production.

| Area | Tersedia | Gate lanjutan lingkungan institusi |
|---|---|---|
| Platform | Modular boundary, lima profil, SOPS, immutable-digest Compose, Ansible, PostgreSQL concurrency guard, private evidence CAS, bounded queues, outbox/inbox, OTLP telemetry, scoped RBAC/MFA, append-only audit, versioned flags/kill switches, migrations dan rules | Host-kosong/reboot/restore rehearsal, authenticated DAST/pentest, broker/worker fault injection, alert rehearsal, load test, image digest approval |
| OBE core | Versioned curriculum, seed 5/12/18/31/77, registry 11 rule dan 2 package cohort, deterministic decision/replay, override/banding, integrity validation gate, RPS, asesmen, evidence, attainment, CQI models | UAT workflow penuh, golden calculation institusi, dan rekonsiliasi keputusan terhadap SIA |
| Analytics | Semantic JSON contract, ETag, local ECharts, table fallback | Semua 8 visual, low-n policy, data 10× pilot |
| AI | LiteLLM-only gateway, data-class guard, AI-off fallback | Golden eval, model benchmark, quota tuning |
| Secure Exam | Authoring/session/response schema, signed bundle, Edge Compose | Encryption key ceremony, SEB/VLAN, 40-seat rehearsal, UPS/power test |
| Academic lifecycle | Status, IRS decision, result, GPA/progress, task/notification schema | Integrasi SIA, kalender institusi, MBKM/PKL/KKN/TA UAT |
| Operations | Server/Edge Compose, specialized workers, Nginx TLS, Ansible, SOPS, Restic, OTel/Prometheus/Loki/Tempo/Grafana, idempotent ops/runbooks | Staging cold deploy, off-host restore, 24-hour SLO/alert rehearsal, DR and go-live sign-off |

Release wajib diblokir sampai UAT critical 100%, total UAT ≥90%, mismatch angka 0, temuan critical/high 0, dan seluruh sign-off PR-87/PR-88 selesai.
