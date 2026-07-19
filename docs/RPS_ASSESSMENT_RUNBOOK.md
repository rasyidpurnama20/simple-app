# Runbook RPS dan Asesmen

## Lifecycle resmi

RPS mengikuti urutan `draft Pengampu → gpm_review → prodi_approval → published`. Maker, reviewer, dan approver wajib berbeda. Pengembalian membuat komentar per field dan menghapus checksum approval lama. Setiap transisi memakai `lock_version`; update yang berangkat dari layar lama ditolak.

Sebelum pengajuan, `validate_rps()` memeriksa:

- referensi dan materi pembelajaran;
- CPMK-RPS terpisah dari CPMK program, pemetaan CPL, Sub-CPMK, indikator observable, dan total bobot 100%;
- 16 minggu reguler, UTS minggu 8, UAS minggu 16, metode, waktu, dan tanggal semester;
- snapshot instrumen published sebelum pengajaran, total asesmen 100%, serta jejak setiap indikator.

`publish_rps(..., strict=True)` hanya menerima checksum review dan approval yang sama dengan payload saat ini. Snapshot publikasi menyimpan seluruh payload dan checksum untuk replay. RPS published tidak dapat diedit; gunakan `clone_rps()` dengan alasan revisi untuk membuat versi berikutnya.

## Rencana dan realisasi pembelajaran

`WeeklyPlan` menyimpan outcome, indikator, topik, metode, aktivitas, tugas, serta waktu tatap muka/terstruktur/mandiri. Desain mengikuti snapshot RPS. Setelah published, Pengampu hanya mencatat realisasi melalui `record_week_execution()` atau reschedule beralasan melalui `reschedule_week()`.

Laporan `planned_vs_actual()` menampilkan selisih menit per minggu. Deviasi wajib diberi alasan pada catatan aktual dan dipakai GPM sebagai evidence review.

## Blueprint dan instrumen

Rencana asesmen harus berjumlah tepat 100%, setiap instrumen memiliki tujuan, peserta, jadwal, mode, attempt, assessor, evidence class, blueprint, dan pemetaan outcome. `publish_assessment_plan()` menolak kode duplikat, mapping/blueprint kosong, evidence yang tidak diwajibkan, jadwal sebelum perkuliahan, atau rubrik belum published.

Instrumen dan butir menjadi immutable setelah published/dipakai. Perubahan desain dilakukan pada versi baru. Kunci jawaban hanya muncul dari selector ketika caller memiliki izin eksplisit `can_view_answer_key=True`.

## Rubrik, grading, dan regrade

Rubrik mendukung analytic, holistic, checklist, numeric, dan pass/fail. Kriteria harus memetakan indikator/Sub-CPMK dan total bobotnya tepat 100%. Interval level performa tidak boleh overlap.

`grade_with_rubric()` menghitung ulang nilai dari response version, instrument version, rubric version, nilai per kriteria, dan assessor. Second marker dapat merekonsiliasi hasil melalui `moderate_score()`. Setelah rubrik dipakai, seluruh desainnya immutable.

Regrade tidak mengubah score lama. `regrade_submission()` membutuhkan alasan dan rubrik dengan `public_id` baru, lalu membuat score baru yang menyimpan `supersedes_score` dan audit before/after.

## Ujian kelas paralel

Setiap question set UTS/UAS menyimpan checksum blueprint dan soal. GPM membandingkan coverage serta difficulty, mencatat alasan bila soal berbeda, lalu Prodi yang berbeda menyetujui equivalence review. Question set hanya dapat dirilis setelah approval. Kebijakan `strict_same_question` dapat mewajibkan soal identik; default mengizinkan soal berbeda hanya bila ekuivalen dan disetujui. Setelah ujian, `analyze_parallel_results()` menandai disparity di atas threshold untuk tindak lanjut mutu tanpa memodifikasi nilai mahasiswa.

## Kehadiran, submission, dan koreksi nilai

Eligibility UAS dihitung dari roster aktif dan IRS approved. Denominator hanya aktivitas terlaksana; cancelled/exempt tidak dihitung. Snapshot menyimpan persen, count, activity ID, reason code, rule version, source version, dan official override bila ada.

Submission memakai draft yang dapat diganti, final ber-receipt checksum yang immutable, serta reopening resmi beralasan. Deadline, late policy, attempt, anggota grup, dan duplikasi evidence divalidasi. Feedback menunjuk kriteria/outcome. Perubahan nilai published memakai `ScoreRevision`: maker dan checker berbeda, score lama dipertahankan, dan score baru menyimpan recalculation serta `supersedes_score`.

## Seed demo v5

Seed default mengimpor irisan kanonik `MIK1624101` dari schema v5: satu RPS, satu CPMK-RPS, tiga Sub-CPMK, tiga indikator, 16 minggu, enam instrumen (10+20+10+20+20+20), dua rubrik, dan butir terkontrol. Status sumber `published-demo/fixture-only` disimpan sebagai provenance, tetapi record aplikasi tetap `draft` karena kurikulum sumber masih `review`.

Jalankan:

```bash
python manage.py seed_demo
python manage.py shell -c "from obe.learning.models import RPSVersion; print(RPSVersion.objects.get().content['source_status'])"
```

Jangan memaksa status official published sebelum blocker kurikulum v5 diselesaikan dan workflow approval dijalankan ulang.
