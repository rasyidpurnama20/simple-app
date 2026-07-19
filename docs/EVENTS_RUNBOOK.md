# Runbook transactional outbox dan domain event

`create_outbox_event` harus dipanggil dalam transaksi yang sama dengan perubahan domain. Publisher mengirim envelope setelah commit dan tidak menghapus riwayat. Crash setelah publish dapat menghasilkan delivery ulang; inbox dan consumer cursor membuat side effect tetap idempoten.

Envelope wajib memuat `event_id`, `event_type`, `aggregate_id`, `version`, `occurred_at`, `actor`, `correlation_id`, `payload_schema`, `payload`, dan `sensitivity`. Publisher menerima schema `1.0` dan `1.1`, payload maksimum 128 KiB, serta consumer eksplisit.

Consumer melakukan pemeriksaan berikut secara transaksional:

1. kombinasi consumer/event ID belum pernah diproses;
2. schema didukung;
3. version tepat satu tingkat setelah cursor;
4. side effect, inbox, dan cursor commit bersama.

Event lama, duplikat, out-of-order, atau schema asing berstatus `rejected`. Handler gagal berstatus `failed` dan dapat dijalankan ulang setelah restart. `last_error` hanya menyimpan tipe error dan fingerprint.

## Rekonsiliasi

- Outbox `publishing` yang melewati lease dikembalikan ke `pending`.
- Retry memakai backoff eksponensial maksimal lima percobaan; terminal menjadi `dead` tanpa menghapus event.
- Bandingkan outbox `published` dengan inbox per consumer menggunakan `event_id` dan correlation ID.
- Replay hanya dilakukan untuk inbox hilang/failed dan tetap mengikuti urutan aggregate version.
