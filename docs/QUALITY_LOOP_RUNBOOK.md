# Runbook Attainment, Portfolio, Provus/CQI, PPEPP, dan Feedback

## Alur operasional

1. Pengampu membuat formula attainment `draft` dengan distribution tepat 100% dan path lengkap PL→CPL→CPMK program→CPMK-RPS→Sub-CPMK→indikator→item→criterion→instrument.
2. GPM mereview formula; Prodi sebagai aktor ketiga mengaktifkannya. Formula aktif tidak diedit—perubahan membuat versi baru.
3. Score published dan evidence verified dihitung menjadi snapshot. Semua input, weight, normalized value, formula/source version, denominator, coverage, missing data, dan reason code disimpan.
4. GPM membuka trace maju/balik sampai finding/action CQI. Gate curriculum, learning, RPS, assessment, execution, score, attainment, dan CQI berdiri terpisah; node `gap`, `blocked`, `pending`, atau `rejected` wajib ditindaklanjuti, bukan disembunyikan.
5. Pengampu/GPM menghasilkan portfolio draft. Hanya evidence verified dan snapshot valid yang menjadi klaim; bagian lain tampil sebagai `incomplete_sections`.
6. Provus membandingkan actual dengan standard. Gap di bawah target diberi root cause dan CQI action ber-owner, deadline, success indicator, approval, serta evidence sebelum/sesudah.
7. Laporan PPEPP dirangkai dari RPS, asesmen, kehadiran, score, attainment, evidence, complaint, finding, CQI, dan effectiveness. Workflow: Pengampu → GPM → Prodi → TPMF → publish.
8. Feedback dosen/mahasiswa diverifikasi, ditautkan ke objek mutu, diberi owner/deadline, dan baru ditutup setelah evidence tersedia.

## API baca dan feedback

```text
GET  /api/v1/analytics/attainment/<snapshot_uuid>/trace/?direction=forward|backward
GET  /api/v1/quality/portfolios/<public_uuid>/
GET  /api/v1/quality/findings/
GET  /api/v1/quality/reports/<public_uuid>/
POST /api/v1/quality/feedback/
GET  /api/v1/quality/feedback/<public_uuid>/
```

Semua endpoint memakai session authentication dan scoped permission. Student portfolio wajib memasok `owner_id`; direct object URL tidak dapat melewati permission service.

## Recalculation dan regenerasi

- Jangan mengubah snapshot lama. Jalankan calculation dengan `previous_snapshot` dan alasan; diff menyimpan actual/coverage/formula sebelum–sesudah.
- Perubahan data setelah portfolio published membuat portfolio versi baru dengan `supersedes`; versi lama menjadi `superseded`.
- Perubahan laporan published masuk `correction`, lalu dibuat report version baru dengan `correction_of`.
- Export memverifikasi package checksum sebelum menghasilkan HTML/CSV/PDF portfolio atau JSON/HTML/PDF laporan.

## Respons insiden

- `EVIDENCE_NOT_VERIFIED`, `SCORE_NOT_PUBLISHED`, `MISSING_SOURCE`, `UNALLOCATED_SOURCE`, `TRACE_PATH_MISMATCH`, atau integrity blocker: hentikan agregasi resmi.
- Checksum export tidak cocok: jangan distribusikan paket; regenerasi dari source versions yang masih tersedia.
- Tindakan `ineffective`: reopen dengan alasan dan baseline baru; jangan menandainya effective secara manual.
- Risiko retaliasi: batasi kasus sebagai `restricted`, jangan menyalin identitas ke report/CQI, dan audit setiap akses.
