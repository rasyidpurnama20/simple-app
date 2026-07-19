# Runbook Baseline Keamanan

## Kontrol aktif

- Nginx hanya membuka HTTPS; TLS 1.2/1.3, HSTS, CSP, frame deny, MIME sniff protection, referrer policy, body/time limits, serta rate zone terpisah untuk login, file, export, AI, analytics berat, dan API.
- Middleware aplikasi mengulang CSP dan pembatasan rate, menolak admin di luar `OBE_ADMIN_NETWORKS`, mengunci akun setelah kegagalan berulang, dan membatalkan sesi ketika assignment berubah.
- Database, Valkey, RabbitMQ, AI, metrics, dan Exam Edge tidak mempublikasikan port. Jaringan application, data, AI, telemetry, administration, dan Exam Edge bersifat internal; hanya proxy berada pada zona public.
- SSH dibatasi ke CIDR VPN dan public key administrator bernama melalui Ansible. Password/interactive SSH tidak menjadi jalur deployment aplikasi.
- Redirect eksternal, URL outbound, nama upload, object access, dan assignment diperiksa server-side. Django template tetap auto-escape dan query ORM tetap terparameterisasi.

## Verifikasi OWASP

Jalankan `./scripts/check.sh`, lalu authenticated DAST di staging terhadap Top 10, IDOR, privilege escalation, SSRF, stored/reflected XSS, CSRF, brute force, path traversal, polyglot/insecure upload, serta cache leakage. Simpan laporan privat dan perbarui `security-controls.json` hanya dengan ringkasan severity; jangan commit payload eksploit atau data mahasiswa.

Release diblokir bila temuan critical/high lebih dari nol. Owner `security` menutup temuan jaringan, `platform` aplikasi, `prodi` matrix akses, dan `auditor` jejak/tamper. Bukti otomatis dalam repositori adalah baseline, bukan pengganti penetration test lingkungan nyata.

## Respons insiden

Aktifkan kill switch terkait, cabut assignment/session/secret terdampak, simpan correlation ID dan audit export bertanda tangan, kemudian lakukan forward-fix. Audit tidak diubah atau dihapus untuk “membersihkan” insiden.
