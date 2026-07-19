# Runbook Identity dan Scoped Permission

Prodi membuat user melalui `provision_user`, lalu memberi assignment menggunakan `grant_assignment`. Assignment memuat role, aksi, scope object, periode, waktu mulai, expiry, pemberi, dan revocation. Self-assignment, self-approval, assignment kedaluwarsa, scope berbeda, dan akses mahasiswa ke owner lain ditolak.

Semua UI/API/file/analytics/AI/task memakai `obe.identity.services.authorize` atau adapter pada `obe.identity.permissions`. Background job menyimpan permission epoch; perubahan role membatalkan sesi dan job lama sebelum side effect dimulai.

Account lock default terjadi setelah lima kegagalan selama 15 menit. Reset credential memakai token Django sekali pakai. MFA opsional memakai challenge acak sekali pakai, hash-only di database, expiry lima menit, maksimal lima percobaan, dan pengiriman ke email akun.

Saat mencabut assignment, wajib isi alasan. Verifikasi negative matrix meliputi direct URL, object ID manipulation, revoked/expired assignment, cache leakage, concurrent role change, dan owner mahasiswa lain.
