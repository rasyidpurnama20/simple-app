# Template Modul Domain

Salin seluruh file `.tmpl` ke `obe/<nama_domain>`, hapus suffix `.tmpl`, lalu ganti `{{ module_name }}` dan `{{ ModuleName }}`. Daftarkan AppConfig dan URL, buat migration nyata dengan Django, kemudian tambahkan domain ke architecture test.

Template sengaja memuat URL, permission, service, API, migration, test, audit helper, serta feature flag sejak awal. Model domain lain tidak boleh diimpor langsung.
