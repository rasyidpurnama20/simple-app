# Tutorial Pengampu

## Tujuan

Pengampu memakai katalog dan pemetaan capaian untuk menyiapkan RPS, asesmen, serta bukti yang konsisten pada mata kuliah yang ditugaskan.

## Masuk dan pilih mata kuliah

1. Masuk di <http://localhost:8000/accounts/login/> dengan username `pengampu`.
2. Buka **Katalog** dan cari `MIK1624101` — Dasar Sistem.
3. Catat semester, SKS, dan jenis mata kuliah sebagai baseline penyusunan RPS.

## Periksa capaian mata kuliah

1. Buka <http://localhost:8000/api/v1/analytics/semantic/?metric=attainment&course=MIK1624101>.
2. Pastikan outcome yang muncul adalah CPL yang dipetakan ke mata kuliah tersebut.
3. Gunakan nilai aktual dan target hanya sebagai bukti agregat; nilai tersebut bukan pengganti rubrik atau nilai mahasiswa.

## Kerjakan tugas pengampu

1. Buka **Tugas Saya**.
2. Cari **Periksa pemetaan CPMK dan bukti asesmen**.
3. Sebelum menyatakan siap, pastikan CPMK, bobot asesmen, rubrik, dan evidence requirement konsisten. Workflow penerbitan tetap mengikuti draft Pengampu → review GPM → approval Prodi.

## Hasil yang diharapkan

- Mata kuliah dan CPMK ditelusuri dari katalog yang sama.
- Data agregat tidak dipakai untuk menimpa nilai individual.
- Pengampu tidak dapat mereview atau menyetujui RPS miliknya sendiri.
