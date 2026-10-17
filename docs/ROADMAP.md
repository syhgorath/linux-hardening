# Yol haritası

Sıra bağlayıcı değildir. Kararlar ve istisnalar: [decisions.md](decisions.md); denenenler: [verification-log.md](verification-log.md).

## Yakın
| İş | Not |
|---|---|
| Küçük Lynis maddeleri | `libpam-tmpdir`, `debsums`, `apt-listchanges`, fail2ban `jail.local`, AIDE SHA256. Sunucu davranışını değiştirir: canlı doğrulama gerekir |
| Eski `ubuntu` grubunu kaldır | Uyarı artık çıkmıyor (#35, olmayan grup seçilmiyor); kaldırmak yalnızca bir temizlik ve BREAKING olarak işaretlenir |
| Tarama klasörü zaman damgası | Klasör adı yerel saatle, `summary.json` UTC; tek biçime getirilebilir |
| v0.2.1 yayını | Hazırlandı (#35 grup uyarısı, #36 ansible-core 2.24 hazırlığı, #37 `scan_dir` kullanıcı klasörü, #38 invoke, #39 `allow_from` uyarısı). Etiket, imza ve Release bakımcıda |

## Orta
| İş | Not |
|---|---|
| Gerçek ağ/ufw düzeyi kesinti denemesi | Mevcut denemeler sshd katmanında engelle yapıldı |
| İkinci sunucu/yapılandırma | Tek VM ile sınırlı kanıtı genişletmek |
| CIS Ubuntu 26.04 Benchmark karşılaştırması | Hazır rol/OpenSCAP içeriği çıkınca; şimdilik "yaklaşım" |
| auditd kapsamı | Kurallar play sonunda yükleniyor (P3), auditd'den önce başlayan süreçler denetlenmiyor (P1), `time-change` kuralı chrony'yi kapsamıyor (P2). **Tasarım notu var (kod yok):** [design/auditd-kapsam.md](design/auditd-kapsam.md) |
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
