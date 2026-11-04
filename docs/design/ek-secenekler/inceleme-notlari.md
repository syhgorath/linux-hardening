# Dış kaynak incelemesi: bir Linux güvenlik blogu (2026-11-05)

**Durum:** Yalnızca FİKİR notu. Kod, cümle ya da yapılandırma kopyalanmadı; sitenin adı ve metni repoya yazılmaz. Bir blogun yaklaşık beş yazısı okundu (ana sayfa, systemd servis sertleştirmesi, çekirdek modül kara listesi, sysctl, "kontrol listesi yerine otomasyon" yazısı, auditd ayarı). Site baştan sona taranmadı.

## Çıkan fikirler ve bizdeki durum

| Fikir | Bizde durum | Aday |
|---|---|---|
| systemd servis sandbox ayarları (`ProtectClock`, `ProtectHostname`, `KeyringMode`, `RestrictNamespaces`, `NoExecPaths` vb.) ve ölçüm için `systemd-analyze security` | Ölçüm raporu EKLENDİ (`hardening_systemd_security_report`). Uygulama (drop-in) YOK | [ubuntu.md](ubuntu.md) U-B8 (servis başına VM'de denenmeden eklenmez) |
| Çekirdek modül kara listesi: `blacklist` yalnızca otomatik yüklemeyi engeller, `install ... /bin/true` daha güçlü, `kernel.modules_disabled=1` en güçlüsü | Zaten var (`disable_filesystem_modules`, `disable_network_protocols`, `kernel_modules_disabled`, `firewire-core` kara listede) | Yok |
| Ctrl+Alt+Del: sysctl tek başına yetmez, asıl karar `ctrl-alt-del.target` biriminde | Yok | U-B10 |
| auditd: kural sırası önemli, gürültülü olayları en başta dışla, `auditctl -s` ile `lost`/`backlog` izle | `backlog_limit` ve `-e 2` var; dışlama ve durum raporu yok | U-B11, U-C4 |
| "Kontrol listesi yerine yapılandırma yönetimi + düzenli denetim; otomasyona tek başına güvenme" | Tasarımımızla örtüşüyor: Ansible + `audit` + `preview` + `verify_access`. Düzenli kayma özeti yok | U-C5 |
| Sysctl yazısı: çoğu anahtar eğitim amaçlı, somut ek anahtar önermiyor | Zaten kapsanıyor | Yok |

## Sınır

Bu liste bloğun yalnızca okunan yazılarına dayanır. Gerçek sunucuda bu fikirlerin hiçbiri denenmedi; her aday yine README'deki kurallarla (varsayılan pasif, test, "DENENMEDİ" işareti) eklenir.
