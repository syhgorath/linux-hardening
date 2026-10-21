# Tasarım notu: Raspberry Pi desteği

**Durum:** UYGULANDI (kısmen) ve arm64 Debian KONTEYNERİNDE denendi; **Pi donanımında DENENMEDİ**. Raspberry Pi OS imajı indirilmedi (indirme için kullanıcıya sorulur).

## Karar: yeni profil değil, küçük bir platform gevşetmesi
- Raspberry Pi OS, Debian 13 (trixie) arm64 tabanlıdır ve `os-release` `ID=debian`, `VERSION_ID=13` verir; sshpocket profili bu yüzden zaten **`debian-13`** olur. `component.yml`'deki `rpi` profili (`planned`) bu nedenle tek başına algılanamaz; Proxmox'taki gibi **platform paket değişkeni** (`hardening_platform: raspberry-pi`) kullanıldı.
- Pi üzerinde Ubuntu Server 26.04 da aynı değişkenle çalışır (`ubuntu-26.04` profili). Ubuntu-on-Pi için `/boot/firmware/config.txt` işareti de kullanılır.
- Pi algılama işaretleri (`hardening_rpi_markers`): `/etc/rpi-issue` ve `/boot/firmware/config.txt`. **Gerçek bir imajda doğrulanmadı**; konteynerde bu dosyalar elle oluşturuldu.

## Ne değişir
| Konu | Davranış |
|---|---|
| Pi algılandı ama platform `generic` | Rol DURMAZ (Proxmox'un aksine; Pi'de Debian/Ubuntu sıradan çalışır); yalnızca NOT düşer |
| `hardening_platform=raspberry-pi`, Pi değil | DURUR; `hardening_allow_unsupported` atlatamaz |
| `usb-storage` engeli | Pi'de varsayılan KAPALI: Pi USB diskten/SSD'den açılır ya da USB depolama kullanır, engel sistem diskine erişimi keser. `hardening_rpi_strict=true` ile açılır (`warn_if: true`) |
| rp_filter, `/tmp` ve `/dev/shm` noexec, ssh, sudo, journald | DEĞİŞMEZ (Proxmox'un `hardening_platform_relaxed` gevşetmesi Pi'yi kapsamaz; test eder) |
| Varsayılan `pi` kullanıcısının `NOPASSWD` sudoers dosyası (`010_pi-nopasswd`) | Rol DOKUNMAZ (Ansible `become` buna dayanabilir); konteynerde korunduğu görüldü |

## Bilerek yapılmayan / bilinmeyen
- **SD kart aşınması:** `journald` kalıcı depolama (`Storage=persistent`), `auditd` günlükleri ve günlük AIDE taraması SD kartı daha çok yazar. Bu sürümde ayrı bir seçenek YOK; gerçek Pi'de ölçülmeden tahmin edilmedi. Gerekirse `hardening_aide_scheduled_check=false` ve `hardening_journald_*` ile elle azaltılır.
- Gerçek saat donanımı (RTC) olmayan Pi'de `chrony` ve ilk açılış saati: DENENMEDİ.
- Pi çekirdeği ve `/boot/firmware` ayarları (cmdline.txt, config.txt) rollerce hiç değiştirilmez.
- SSH parola girişi kapatılır (tüm platformlar gibi): yalnızca parolayla bağlanan bir Pi'de anahtarı önce kurun; `hardening_verify_access` yeni bağlantıyı doğrular ve başarısızsa geri alır.
- Wi-Fi/Bluetooth kapatma (CIS 3.1.2) yapılmaz.

## Test
Birim: `test/test_rpi_platform.py` (algılama, reddetme, `generic` + Pi, strict, usb-storage koşulu, Proxmox gevşetmesinin Pi'yi kapsamaması; mutasyonlarla doğrulandı). Gerçek koşu: Colima'da arm64 Debian 13 konteyneri, Pi işaretleri ve `pi` kullanıcısı eklenmiş: `docs/verification-log.md` madde 44.
