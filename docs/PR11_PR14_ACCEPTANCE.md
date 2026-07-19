# Penerimaan PR-11–PR-14

| PR | Kontrol | Bukti utama | Status |
|---|---|---|---|
| 11 | TLS/header/rate limit, input/output/upload/redirect/SSRF guard, jaringan deny-by-default, admin VPN/SSH key | `shared/security.py`, middleware, Nginx/Compose/Ansible, security control manifest dan tests | Implemented |
| 12 | Login/logout/reset/expiry/lock/MFA, role dan assignment scoped, permission tunggal, anti-IDOR/self-approval | `identity/models.py`, `identity/services.py`, adapters, auth views dan negative matrix tests | Implemented |
| 13 | Jejak lengkap append-only, payload sensitif terpisah, hash-chain, retention, search dan signed export | `shared/audit.py`, trigger migration, audit tests | Implemented |
| 14 | Flag berversi enam state, scope lengkap, evidence/rollback, kill switch dan job snapshot | `shared/feature_flags.py`, job guard dan rollback tests | Implemented |

Gate lokal mensyaratkan seluruh quality gate, migration reversibility, dan finding otomatis critical/high = 0. DAST/pentest staging dan sign-off institusi tetap gate rilis lapangan.
