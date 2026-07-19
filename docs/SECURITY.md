# Keamanan

- TLS, HSTS, secure cookie, CSRF, CSP, frame deny, referrer policy, MIME sniff protection.
- Rate limit berlapis dan terpisah untuk login, reset credential, API, file, export, AI, serta analytics berat.
- Satu permission service memeriksa role, aksi, object scope, period, expiry, dan revocation.
- Bukti berada di private content-addressed storage dan hanya diunduh melalui object permission.
- Audit kritis memakai DB guard dan hash-chain append-only; payload sensitif terpisah, export ditandatangani, dan koreksi adalah event baru.
- Secret dikelola dengan SOPS, divalidasi saat startup, dirotasi tanpa downtime, dan dapat dicabut oleh host/operator berwenang sesuai [runbook secret](SECRETS_RUNBOOK.md).
- Filter bersama meredaksi secret dari log, error/API response, tracing, dan payload; task event Celery dinonaktifkan agar argumen tidak menjadi telemetry.
- Data `restricted-exam` tidak boleh masuk provider AI eksternal.
- Exam VLAN internal dan deny-by-default; tidak memiliki route Internet/AI.

Prosedur verifikasi serta pembagian owner tersedia pada [Security Runbook](SECURITY_RUNBOOK.md), [Identity Runbook](IDENTITY_RUNBOOK.md), [Audit Runbook](AUDIT_RUNBOOK.md), dan [Feature Flag Runbook](FEATURE_FLAG_RUNBOOK.md).

Laporkan kerentanan secara privat kepada security owner institusi. Jangan membuka issue publik yang memuat data mahasiswa, credential, nilai, soal, jawaban, atau path bukti.
