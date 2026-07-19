# Acceptance PR-08–PR-10

| PR | Bukti otomatis | Gate lingkungan |
|---|---|---|
| 08 | queue bounded/DLQ, payload guard, worker isolation, idempotent job, progress, cancellation, stale-result/lease tests | restart RabbitMQ, crash worker, queue-full, poison-message rehearsal |
| 09 | commit/rollback, retry/dead state, immutable history, inbox duplicate/out-of-order/schema/restart tests | broker disconnect setelah send, reconciliation pada PostgreSQL/RabbitMQ staging |
| 10 | SLO constants, attribute redaction, correlation propagation, dashboard/alert/collector contracts | deploy stack digest-pinned, alert fire/recover, trace/log/metric correlation, 24 jam availability pilot |

Gate kode dinyatakan lulus jika seluruh quality gate repo berhasil, duplicate side effect tetap nol, event commit tidak hilang, dan telemetry contract tidak memuat field sensitif. Gate lingkungan membutuhkan host staging dan tidak diklaim oleh unit test.
