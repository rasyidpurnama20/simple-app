# Fixtures

`sample-data-2020-2026-obe-spec-v5.compact.json` adalah normalisasi aman dari dataset sintetis v5 yang diberikan untuk pengembangan. Katalog kurikulum, pemetaan, dan agregat capaian dipertahankan lengkap; empat riwayat mahasiswa sintetis dipilih sebagai data demonstrasi agar instalasi lokal tetap ringan.

Jalankan `python manage.py import_obe_sample` untuk mengimpor fixture ini secara transaksional dan idempotent. File v5 lengkap dapat diberikan melalui opsi `--path`; importer selalu memvalidasi schema sebelum menulis data.

Fixture tidak boleh berisi credential atau data produksi. Provenance, checksum attachment, status kelengkapan, dan strategi seleksi wajib dicatat di `importMetadata`.
