# Kontrak API

Base path: `/api/v1/`. Authentication baseline memakai secure Django session dan CSRF.

## Semantic analytics

`GET /api/v1/analytics/semantic/?metric=attainment&cohort=2024`

Metric: `attainment`, `grade_distribution`, atau `coverage`.

Envelope selalu memuat:

```json
{
  "schema_version": "1.0",
  "metric_version": "1.0",
  "rule_version": "CURRENT-AABBC/1",
  "filters": {},
  "cohort": "2024",
  "source_versions": {},
  "generated_at": "2026-07-19T00:00:00+07:00",
  "privacy_scope": "self",
  "denominator": 0,
  "missing_count": 0,
  "warnings": [],
  "reason_codes": [],
  "units": "percent",
  "dimensions": [],
  "series": [],
  "data": []
}
```

Response menyertakan ETag dan cache private. Error DRF dinormalisasi menjadi `{"error":{"code":"...","detail":...}}`. Dataset besar wajib memakai async export dan audit export.

Health endpoints: `GET /healthz/` untuk liveness dan `GET /readyz/` untuk kesiapan database.

## Attainment trace dan quality loop

- `GET /api/v1/analytics/attainment/<snapshot_uuid>/trace/?direction=forward|backward&start=<node>` mengembalikan node/edge dua arah sampai finding/action CQI, version/status/owner/source/permission, gate terpisah, serta daftar gap yang tidak disembunyikan.
- `GET /api/v1/quality/portfolios/<public_uuid>/` mengembalikan portfolio terscope beserta denominator, source version, incomplete section, evidence manifest, dan checksum.
- `GET /api/v1/quality/findings/` mengembalikan perbandingan Provus actual/target/gap/coverage/confidence.
- `GET /api/v1/quality/reports/<public_uuid>/` mengembalikan report PPEPP berversi dan approval history.
- `POST /api/v1/quality/feedback/` menerima feedback akademik/nonakademik. `anonymous=true` tidak menyimpan FK reporter; `retaliation_risk=true` memaksa klasifikasi `restricted`.
- `GET /api/v1/quality/feedback/<public_uuid>/` hanya untuk reporter nonanonim, responsible actor yang diizinkan, atau reviewer. Pembukaan kasus tercatat pada audit append-only.
