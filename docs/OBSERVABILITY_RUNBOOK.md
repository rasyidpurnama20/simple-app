# Runbook observability dan SLO

OBE mengirim metrics, traces, dan logs melalui OTLP HTTP ke OpenTelemetry Collector. Collector mengekspor metrics ke Prometheus, traces ke Tempo, dan logs teredaksi ke Loki; Grafana memprovision data source dan dashboard operasi secara otomatis.

Referensi konfigurasi mengikuti dokumentasi resmi [OpenTelemetry Django](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/django/django.html), [OpenTelemetry Celery](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/celery/celery.html), dan [Prometheus alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/).

## SLO

| Indikator | Target |
|---|---:|
| Core read p95 | ≤2,5 detik |
| Error ratio | <1% |
| Autosave ujian p95 | ≤1,5 detik |
| Availability pilot | ≥99,5% |

Telemetry hanya menerima route template, status, queue, task name, outcome, model alias, classification, correlation ID, dan angka agregat. Nama, NIM, nilai mentah, jawaban ujian, token, prompt, request/response body, SQL, serta file path dibuang di aplikasi dan collector.

## Alert dan respons

| Alert | Tindakan pertama |
|---|---|
| Disk >80% | hentikan job batch, periksa retention dan kapasitas |
| Queue saturation | identifikasi queue/worker, hentikan producer non-kritis |
| DB pool >90% | periksa slow query, concurrency, dan kebocoran koneksi |
| Backup terlambat | jalankan backup manual lalu verifikasi Restic |
| AI circuit open | pertahankan rules-only, periksa gateway secara terpisah |
| Exam Edge offline | pertahankan operasi lokal, periksa link dan cursor sync |

Telusuri insiden menggunakan `correlation_id` yang sama pada response header, log, span, outbox, inbox, dan job. Routing Alertmanager nyata wajib dipasok melalui konfigurasi privat operator sebelum staging.
