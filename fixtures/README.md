# Fixtures

Fixture akademik baseline dibuat secara deterministik dan idempotent melalui `python manage.py seed_demo`. Pendekatan command dipilih agar relasi, password lokal acak, constraint, serta perubahan schema tetap tervalidasi oleh model dan service.

File fixture statis tambahan harus anonim, memiliki provenance dan schema version, serta tidak boleh berisi NIM, nilai, credential, atau data institusi nyata.
