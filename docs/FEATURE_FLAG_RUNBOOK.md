# Runbook Feature Flag dan Kill Switch

Flag baru selalu versi 1 `disabled`. Aktivasi membuat versi baru dan memerlukan owner, tanggal aktivasi, target user, acceptance evidence, rollback plan, alasan, serta assignment `feature_flag.manage`.

Scope yang didukung: global, module, role, cohort, mata kuliah, dan environment. State: `disabled`, `internal`, `pilot`, `general`, `deprecated`, `retired`. Permission diperiksa sebelum flag sehingga flag tidak pernah memberikan hak akses.

Kill switch terdaftar untuk AI, analytics berat, notification, export, integration write, dan Secure Exam sync. Perubahan kill switch membatalkan job yang belum menjalankan side effect. Flag biasa mempertahankan snapshot bagi job yang sudah berjalan agar rollback UI tidak merusak core atau memerlukan migration darurat.
