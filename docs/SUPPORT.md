# Destek matrisi

| Dağıtım | Sürüm | Durum | Not |
|---|---|---|---|
| Ubuntu | 26.04 LTS | Desteklenir, test edildi (Proxmox VM) | Lynis 58 -> 77, idempotent |
| Ubuntu | 24.04 LTS | Planlanmadı | Eklenebilir (aşağıya bak) |
| Raspberry Pi OS / Proxmox VE | – | Planlandı, **henüz yok** | Firewall, ip_forward, SD kart farkları var |

## Yeni sürüm / dağıtım ekleme
1. `vars/<dagitim>-<surum>.yml` oluştur (örn. `vars/ubuntu-24.04.yml`), `vars/ubuntu-26.04.yml`'den kopyala.
2. `roles/hardening_preflight/defaults/main.yml` içindeki `hardening_supported_os` listesine ekle.
3. Test VM'de sırasıyla: `audit.yml` -> `harden.yml --check --diff` -> `harden.yml` -> ikinci çalıştırmada `changed=0`.
4. Bu tabloyu güncelle, farkları `decisions.md`'ye yaz.
5. Dağıtıma özel bir rol gerekiyorsa (örn. Proxmox firewall) ayrı bir rol yaz; ortak roller değişmez.

Desteklenmeyen sistemde zorla çalıştırmak (önerilmez): `-e hardening_allow_unsupported=true`.
