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

