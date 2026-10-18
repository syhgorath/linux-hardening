# Yol haritası

Sıra bağlayıcı değildir. Kararlar ve istisnalar: [decisions.md](decisions.md); denenenler: [verification-log.md](verification-log.md).

## Yakın
| İş | Not |
|---|---|
| CIS Grup 2 (davranış değiştirir, **hepsi varsayılan KAPALI**, her biri kendi değişkeniyle) | Core dump kapatma, kabuk `TMOUT`, parola `INACTIVE`, `/tmp` ve `/dev/shm` `noexec`, `su` kısıtı, günlük dosyası izinleri, kullanıcı dot dizinleri, **`telnet`/`ftp`/`tnftp` kaldırma** (madde numaraları: [cis-esleme.md](cis-esleme.md)). `telnet`/`ftp` notu: port açmazlar (güvenlik riski yaratmaz) ama `telnet host port` ile port yoklayan betikleri ve `ftp` yedek akışlarını kırar; kaldırma `apt remove` (purge değil), geri alma `apt install`. Çalıştırılamaz yapma (`chmod`/`dpkg-statoverride`) CIS denetimini geçmez ve güncellemede bozulur, önerilmez. README "Dikkat" bölümünde uyarı var |
| Senaryo temeli (3 sunucu: web / docker / redis+log+backup) | `hardening_ufw_extra_allow` değişkenini `component.yml`'e aç (sshpocket görsün); grup ve sunucu portlarının birleşmesi için ikinci liste değişkeni (Ansible listeleri ezer, birleştirmez); sonra `examples/` (`group_vars`/`host_vars`) ve HOWTO. Docker sunucusu için ayrı rol tasarımı. Önce açık sorular: özel ağ yapısı, yedek yönü, Docker port yayını |
| Küçük Lynis maddeleri | `libpam-tmpdir`, `debsums`, `apt-listchanges`, fail2ban `jail.local`, AIDE SHA256. Sunucu davranışını değiştirir: canlı doğrulama gerekir |
| Eski `ubuntu` grubunu kaldır | Uyarı artık çıkmıyor (#35, olmayan grup seçilmiyor); kaldırmak yalnızca bir temizlik ve BREAKING olarak işaretlenir |
| Tarama klasörü zaman damgası | Klasör adı yerel saatle, `summary.json` UTC; tek biçime getirilebilir |
| v0.2.2 yayını | Hazırlandı (ufw eski SSH kuralı uyarısı/opsiyonel silme, auditd kuralları hemen yükleme ve önceki süreçler uyarısı, bilinen çakışmalar belgesi, tasarım notları). Etiket, imza ve Release bakımcıda |

## Orta
| İş | Not |
|---|---|
| Gerçek ağ/ufw düzeyi kesinti denemesi | Mevcut denemeler sshd katmanında engelle yapıldı |
| İkinci sunucu/yapılandırma | Tek VM ile sınırlı kanıtı genişletmek |
| CIS eşlemesinin devamı | Madde numaralı eşleme var: [cis-esleme.md](cis-esleme.md). Kalan ❌ maddeler "Grup 2" ve "Grup 3" olarak ayrıldı (aşağıdaki "Yakın" satırı ve PAM/zaman/AIDE tasarım notları) |
| auditd kapsamı | Kurallar play sonunda yükleniyor (P3), auditd'den önce başlayan süreçler denetlenmiyor (P1), `time-change` kuralı chrony'yi kapsamıyor (P2). **Tasarım notu var (kod yok):** [design/auditd-kapsam.md](design/auditd-kapsam.md) |
| `pam_faillock` / `pam_pwhistory` | CIS 5.3 PAM maddeleri; kilitlenme riski yüksek. **Tasarım notu var (kod yok):** [design/pam-faillock.md](design/pam-faillock.md) |
| Zaman senkronizasyonu rolü | Snapshot dönüşünde saat geride kaldı; `chrony` yapılandırması bir hardening maddesi olabilir. **Tasarım notu var (kod yok):** [design/zaman-ntp.md](design/zaman-ntp.md) |
| Çok sunuculu çalıştırma | `serial`/`any_errors_fatal`: bir sunucudaki hata diğerlerini durdurmalı mı |

## Uzak
| İş | Not |
|---|---|
| Raspberry Pi / Proxmox profilleri | Firewall (Proxmox `pve-firewall`), `ip_forward`, SD kart yazım aşınması farklı; ayrı roller. **Proxmox hostu:** tasarım notu ve boş iskelet var, işlevsiz: [design/proxmox-host.md](design/proxmox-host.md) |
| Başka Ubuntu sürümü (24.04) | `docs/SUPPORT.md` adımları |
| Tarama sonuçlarını karşılaştırma | `summary.json`'dan öncesi/sonrası (sshpocket arayüzü ile) |

## sshpocket entegrasyonu (o repoda)
Bileşen yükleyici, sözleşmeyi okuyan ayrıştırıcı, menü ve güvenlik kapıları sshpocket tarafında; takip:
syhgorath/sshpocket#3.
