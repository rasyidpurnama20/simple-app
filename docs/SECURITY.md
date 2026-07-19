# Keamanan

- TLS, HSTS, secure cookie, CSRF, CSP, frame deny, referrer policy, MIME sniff protection.
- Rate limit terpisah untuk login dan API; endpoint file/export/AI wajib menambah policy khusus saat diaktifkan.
- Satu permission service memeriksa role, aksi, object scope, period, expiry, dan revocation.
- Bukti berada di private content-addressed storage dan hanya diunduh melalui object permission.
- Audit kritis append-only; koreksi adalah event baru.
- Secret dikelola dengan SOPS, divalidasi saat startup, dirotasi tanpa downtime, dan dapat dicabut oleh host/operator berwenang sesuai [runbook secret](SECRETS_RUNBOOK.md).
- Filter bersama meredaksi secret dari log, error/API response, tracing, dan payload; task event Celery dinonaktifkan agar argumen tidak menjadi telemetry.
- Data `restricted-exam` tidak boleh masuk provider AI eksternal.
- Exam VLAN internal dan deny-by-default; tidak memiliki route Internet/AI.

Laporkan kerentanan secara privat kepada security owner institusi. Jangan membuka issue publik yang memuat data mahasiswa, credential, nilai, soal, jawaban, atau path bukti.
