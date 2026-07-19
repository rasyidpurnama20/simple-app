# Runbook Kurikulum PR-19–PR-24

## Tujuan dan batas aman

Runbook ini mengoperasikan versi kurikulum, katalog PL/CPL/BK/CPMK/mata kuliah, paket JSON/CSV, dan weighted traceability. Versi aktif/arsip beserta child record bersifat immutable. Perubahan selalu dimulai dari import atau clone `draft`.

Dataset demo adalah bukti uji, bukan paket siap aktivasi: terdapat 129 SKS wajib (gate tepat 126) dan CPMK22/CPMK27 tidak memiliki inbound mapping. Jangan mengoreksi ketiga finding itu secara otomatis.

## Seed dan diagnosis

```bash
docker compose exec web python manage.py import_obe_sample
docker compose exec web python manage.py shell
```

Di shell Django:

```python
from obe.curriculum.models import CurriculumVersion
from obe.curriculum.services import allocation_report, catalog_report, traceability_report

curriculum = CurriculumVersion.objects.get(program_code="S1-INFORMATIKA", version=1)
catalog_report(curriculum)
allocation_report(curriculum)
traceability_report(curriculum)
```

Interpretasi wajib:

- `catalog.credit_valid=false` sampai katalog wajib tepat 126 SKS dan pilihan minimal 18 SKS;
- `allocation.totals_valid=true` hanya menyatakan jumlah bobot tepat, bukan approval manusia;
- `allocation.valid=false` bila ada mapping tanpa `approval_reference` atau sisa `unallocated`;
- `traceability.valid=false` bila ada gap, orphan, arah terbalik, atau cycle.

## Approval dan aktivasi

```python
from obe.curriculum.services import (
    activate, approve_allocations, approve_curriculum, submit_for_review,
)
from obe.shared.services import ActorContext

approve_allocations(
    curriculum,
    actor=ActorContext("allocation-approver", "Prodi", "curriculum"),
    approval_reference="SK-PRODI-2026-001",
)
curriculum = submit_for_review(
    curriculum, actor=ActorContext("reviewer", "GPM", "curriculum")
)
curriculum = approve_curriculum(
    curriculum,
    actor=ActorContext("approver", "Ketua Prodi", "curriculum"),
    documents=[{"type": "SK", "reference": "SK-PRODI-2026-001"}],
)
curriculum = activate(
    curriculum,
    actor=ActorContext("activator", "Administrator Akademik", "curriculum"),
    integrity_verified=True,
)
```

Empat identity harus berbeda. Aktivasi menjalankan ulang gate katalog, allocation, traceability, dan integrity; menyimpan checksum; lalu mengarsipkan versi aktif yang periodenya overlap dalam transaksi yang sama.

## Clone, diff, dan trace

```python
from datetime import date
from obe.curriculum.services import clone_curriculum, curriculum_diff, trace_paths

draft = clone_curriculum(
    curriculum,
    actor=ActorContext("maker-v2", "Tim Kurikulum", "curriculum"),
    effective_from=date(2027, 8, 1),
)
curriculum_diff(curriculum, draft)
trace_paths(draft, node_type="PL", node_id="PL01")
trace_paths(draft, node_type="CPMK", node_id="CPMK01", reverse=True)
```

Mapping hasil clone tidak membawa approval lama. Reviewer wajib memeriksa dan menyetujui ulang bobot pada versi baru.

## Paket JSON dan CSV

```python
from obe.curriculum.package import (
    export_csv_bundle, export_json_package, import_csv_bundle, import_json_package,
)

json_bytes = export_json_package(curriculum)
csv_files = export_csv_bundle(curriculum)
imported = import_json_package(json_bytes, actor=ActorContext("importer"))
same = import_csv_bundle(csv_files, actor=ActorContext("importer"))
```

Manifest/checksum wajib cocok. Import checksum yang sama idempoten dan mengembalikan versi yang sudah ada. Field asing, schema tidak didukung, atau perubahan isi setelah checksum langsung ditolak.

## Rollback aktivasi

```python
from obe.curriculum.services import rollback_activation

restored = rollback_activation(
    current=active_v2,
    target=archived_v1,
    actor=ActorContext("rollback-operator", "Administrator Akademik", "curriculum"),
)
```

Target harus arsip dari program yang sama, pernah disetujui, dan checksum-nya masih cocok. Operasi mengarsipkan versi saat ini dan mengaktifkan target secara atomik serta membuat audit/outbox event.

## Recovery

Jika import, approval, aktivasi, atau rollback gagal, transaksi database menjaga status sebelumnya. Simpan error report, correlation ID, checksum sumber, dan dokumen approval; perbaiki sumber pada versi draft/clone, lalu ulangi gate. Jangan mengedit record aktif/arsip atau menurunkan gate.
