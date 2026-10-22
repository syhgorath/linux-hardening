# Destek matrisi

| Dağıtım | Sürüm | Durum | Not |
|---|---|---|---|
| Ubuntu | 26.04 LTS | Desteklenir, test edildi (Proxmox VM) | Lynis 58 -> 77, idempotent |
| Ubuntu | 24.04 LTS | Planlanmadı | Eklenebilir (aşağıya bak) |
| Debian | 13 (trixie) | Desteklenir, **konteynerde test edildi** | `--check` `failed=0`, gerçek koşu `failed=0`, ikinci koşu `changed=0` (Colima'da systemd'li konteyner, `auditd` atlanarak); gerçek bir Debian 13 VM'inde ve `auditd` ile henüz DENENMEDİ; Raspberry Pi OS (Debian tabanlı) ayrıca denenmedi; Proxmox hostu bilerek reddedilir |
| Raspberry Pi OS (Debian 13 arm64 tabanlı) | 13 | `rpi` profili **Planlandı** (sshpocket Pi'yi `debian-13` görür); `debian-13` profili + `hardening_platform=raspberry-pi`; **yalnızca arm64 Debian konteynerinde, Pi işaretleriyle denendi, Pi donanımında DEĞİL** | usb-storage engeli Pi'de varsayılan kapalı; SD kart aşınması, RTC ve Pi kernel'i denenmedi. Tasarım: docs/design/raspberry-pi.md |
| Ubuntu Server 26.04 (Raspberry Pi üzerinde) | 26.04 LTS | `ubuntu-26.04` profiliyle kapıdan GEÇER, `hardening_platform=raspberry-pi` kabul edilir, **denenmedi** | SD kart yazma aşınması, `/tmp` ve `journald` farkları, ARM mimarisi hiç sınanmadı; çalışacağına dair iddia yok |
| Proxmox VE hostu | 9 (Debian 13) | `proxmox` profili **Planlandı**; host `hardening_platform=proxmox-host` + `hardening_pve_apply=true` ile sertleştirilebilir (TEK düğüm; **iç içe Proxmox 9.2'de denendi**, VM'li ve kümeli host DENENMEDİ); platform seçilmeden **bilerek reddedilir** | `/etc/pve` varsa `generic` platformda rol durur, `hardening_allow_unsupported` bile atlatmaz; üstündeki Ubuntu VM'leri etkilenmez. SALT OKUNUR durum raporu: `playbooks/pve-report.yml`. Güvenlik duvarı ayrı bir playbook'la yönetilir (`playbooks/pve-firewall.yml`, TEK düğüm, varsayılan yalnızca ÖNİZLEME). `-e hardening_platform=proxmox-host` ile `--check` ÖNİZLEMESİ serbest; GERÇEK koşu ayrıca `hardening_pve_apply=true` ister |

## Yeni sürüm / dağıtım ekleme
1. `vars/<dagitim>-<surum>.yml` oluştur (örn. `vars/ubuntu-24.04.yml`), `vars/ubuntu-26.04.yml`'den kopyala.
2. `roles/hardening_preflight/defaults/main.yml` içindeki `hardening_supported_os` listesine ekle.
3. Test VM'de sırasıyla: `audit.yml` -> `harden.yml --check --diff` -> `harden.yml` -> ikinci çalıştırmada `changed=0`.
4. Bu tabloyu güncelle, farkları `decisions.md`'ye yaz.
5. Dağıtıma özel bir rol gerekiyorsa (örn. Proxmox firewall) ayrı bir rol yaz; ortak roller değişmez.

Desteklenmeyen sistemde zorla çalıştırmak (önerilmez): `-e hardening_allow_unsupported=true`.

**Proxmox VE hostunda çalışmaz, bayrak atlatamaz:** `/etc/pve` ya da `/usr/bin/pveversion` varsa rol en başta durur (`--check`'te de). `hardening_allow_unsupported=true` bu denetimi atlatmaz ve Proxmox için ayrı bir bayrak yoktur. Proxmox **üstündeki** Ubuntu VM'leri etkilenmez.

Makine-okunur karşılığı `component.yml` içindeki `profiles` alanıdır; tutarlılığı `scripts/check-consistency.py` denetler.
