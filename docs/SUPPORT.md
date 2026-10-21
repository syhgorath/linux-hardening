# Destek matrisi

| Dağıtım | Sürüm | Durum | Not |
|---|---|---|---|
| Ubuntu | 26.04 LTS | Desteklenir, test edildi (Proxmox VM) | Lynis 58 -> 77, idempotent |
| Ubuntu | 24.04 LTS | Planlanmadı | Eklenebilir (aşağıya bak) |
| Debian | 13 (trixie) | Desteklenir, **konteynerde test edildi** | `--check` `failed=0`, gerçek koşu `failed=0`, ikinci koşu `changed=0` (Colima'da systemd'li konteyner, `auditd` atlanarak); gerçek bir Debian 13 VM'inde ve `auditd` ile henüz DENENMEDİ; Raspberry Pi OS (Debian tabanlı) ayrıca denenmedi; Proxmox hostu bilerek reddedilir |
| Raspberry Pi OS / Proxmox VE | – | Planlandı, **henüz yok** | Firewall, ip_forward, SD kart farkları var |
| Ubuntu Server 26.04 (Raspberry Pi üzerinde) | 26.04 LTS | `ubuntu-26.04` profiliyle kapıdan GEÇER, **denenmedi** | SD kart yazma aşınması, `/tmp` ve `journald` farkları, ARM mimarisi hiç sınanmadı; çalışacağına dair iddia yok |
| Proxmox VE hostu | 9 (Debian 13) | **Çalışmaz, bilerek reddedilir** | `/etc/pve` varsa `generic` platformda rol durur, `hardening_allow_unsupported` bile atlatmaz; üstündeki Ubuntu VM'leri etkilenmez. SALT OKUNUR durum raporu: `playbooks/pve-report.yml`. Güvenlik duvarı ayrı bir playbook'la yönetilir (`playbooks/pve-firewall.yml`, TEK düğüm, varsayılan yalnızca ÖNİZLEME). `-e hardening_platform=proxmox-host` ile yalnızca `--check` ÖNİZLEMESİ çalışır (iç içe Proxmox 9.2'de denendi); gerçek koşu REDDEDİLİR (pve-firewall yönetimi yok) |

## Yeni sürüm / dağıtım ekleme
1. `vars/<dagitim>-<surum>.yml` oluştur (örn. `vars/ubuntu-24.04.yml`), `vars/ubuntu-26.04.yml`'den kopyala.
2. `roles/hardening_preflight/defaults/main.yml` içindeki `hardening_supported_os` listesine ekle.
3. Test VM'de sırasıyla: `audit.yml` -> `harden.yml --check --diff` -> `harden.yml` -> ikinci çalıştırmada `changed=0`.
4. Bu tabloyu güncelle, farkları `decisions.md`'ye yaz.
5. Dağıtıma özel bir rol gerekiyorsa (örn. Proxmox firewall) ayrı bir rol yaz; ortak roller değişmez.

Desteklenmeyen sistemde zorla çalıştırmak (önerilmez): `-e hardening_allow_unsupported=true`.

**Proxmox VE hostunda çalışmaz, bayrak atlatamaz:** `/etc/pve` ya da `/usr/bin/pveversion` varsa rol en başta durur (`--check`'te de). `hardening_allow_unsupported=true` bu denetimi atlatmaz ve Proxmox için ayrı bir bayrak yoktur. Proxmox **üstündeki** Ubuntu VM'leri etkilenmez.

Makine-okunur karşılığı `component.yml` içindeki `profiles` alanıdır; tutarlılığı `scripts/check-consistency.py` denetler.
