# Runbook Audit Append-Only

`record_change` menyimpan actor, role/assignment, waktu, IP, user-agent, aksi, object, ringkasan before/after, alasan, correlation ID, outcome, previous hash, dan integrity hash. Key sensitif otomatis diredaksi; payload yang memang diperlukan dipisahkan ke `AuditSensitivePayload` dengan retention tersendiri.

Update/delete melalui ORM ditolak. PostgreSQL memasang trigger untuk menolak update/delete langsung; SQLite test memasang update guard. Koreksi selalu event baru. `verify_audit_chain` dipakai saat restore dan insiden, sedangkan `export_audit` menghasilkan payload dengan SHA-256 dan signature aplikasi.

Hanya assignment `audit.view`, `audit.export`, dan—bila UI sensitif ditambahkan—`audit.sensitive` yang boleh mengaksesnya. Job retention hanya menghapus payload sensitif yang sudah lewat masa simpan; ringkasan audit dan hash-chain tetap ada.
