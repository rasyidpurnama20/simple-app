# Tutorial Pengampu

## Tujuan

Pengampu memakai katalog dan pemetaan capaian untuk menyiapkan RPS, asesmen, serta bukti yang konsisten pada mata kuliah yang ditugaskan.

## Masuk dan pilih mata kuliah

1. Masuk di <http://localhost:8000/accounts/login/> dengan username `pengampu`.
2. Akses RPS, asesmen, file, AI, dan background job mengikuti assignment mata kuliah/periode yang sama; URL object di luar scope akan ditolak.
3. Buka **Katalog** dan cari `MIK1624101` — Dasar Sistem.
4. Catat semester, SKS, dan jenis mata kuliah sebagai baseline penyusunan RPS.

## Periksa capaian mata kuliah

1. Buka <http://localhost:8000/api/v1/analytics/semantic/?metric=attainment&course=MIK1624101>.
2. Pastikan outcome yang muncul adalah CPL yang dipetakan ke mata kuliah tersebut.
3. Gunakan nilai aktual dan target hanya sebagai bukti agregat; nilai tersebut bukan pengganti rubrik atau nilai mahasiswa.

## Kerjakan tugas pengampu

1. Buka **Tugas Saya**.
2. Cari **Periksa pemetaan CPMK dan bukti asesmen**.
3. Sebelum menyatakan siap, pastikan CPMK, bobot asesmen, rubrik, dan evidence requirement konsisten. Workflow penerbitan tetap mengikuti draft Pengampu → review GPM → approval Prodi.

## Tindak lanjuti keputusan akademik

1. Buka explanation keputusan mata kuliah dan periksa rule code/version, field aktual, kondisi, evidence row, serta source version.
2. Jika input sumber keliru, koreksi melalui gradebook/kehadiran resmi lalu minta revalidation; decision snapshot lama tidak boleh diedit.
3. Jika pengecualian sah diperlukan, ajukan override dengan reason code, alasan, dokumen evidence immutable, dampak, dan expiry.
4. Pengampu sebagai maker tidak boleh menyetujui override sendiri. Effective outcome berubah menjadi `overridden` hanya setelah checker berwenang menyetujui.

## Hasil yang diharapkan

- Mata kuliah dan CPMK ditelusuri dari katalog yang sama.
- Data agregat tidak dipakai untuk menimpa nilai individual.
- Pengampu tidak dapat mereview atau menyetujui RPS miliknya sendiri.
