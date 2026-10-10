# Yol haritası

Sıra bağlayıcı değildir. Kararlar ve istisnalar: [decisions.md](decisions.md); denenenler: [verification-log.md](verification-log.md).

## Yakın
| İş | Not |
|---|---|
| Küçük Lynis maddeleri | `libpam-tmpdir`, `debsums`, `apt-listchanges`, fail2ban `jail.local`, AIDE SHA256. Sunucu davranışını değiştirir: canlı doğrulama gerekir |
| `hosts: "hardening:ubuntu"` geçişini bitir | Eski `ubuntu` grubu kaldırılınca "host pattern" uyarısı da gider (BREAKING olarak işaretlenir) |
| Tarama klasörü zaman damgası | Klasör adı yerel saatle, `summary.json` UTC; tek biçime getirilebilir |
| Yeni sürüm (0.1.x) | `scripts/release.sh` PyYAML/.venv iyileştirmesi (#26) `main`'de, v0.1.0 paketinde **yok** |

## Orta
| İş | Not |
|---|---|
| Gerçek ağ/ufw düzeyi kesinti denemesi | Mevcut denemeler sshd katmanında engelle yapıldı |
| İkinci sunucu/yapılandırma | Tek VM ile sınırlı kanıtı genişletmek |
| CIS Ubuntu 26.04 Benchmark karşılaştırması | Hazır rol/OpenSCAP içeriği çıkınca; şimdilik "yaklaşım" |
| Zaman senkronizasyonu rolü | Snapshot dönüşünde saat geride kaldı; `chrony` yapılandırması bir hardening maddesi olabilir |
| Çok sunuculu çalıştırma | `serial`/`any_errors_fatal`: bir sunucudaki hata diğerlerini durdurmalı mı |

## Uzak
| İş | Not |
|---|---|
| Raspberry Pi / Proxmox profilleri | Firewall (Proxmox `pve-firewall`), `ip_forward`, SD kart yazım aşınması farklı; ayrı roller |
| Başka Ubuntu sürümü (24.04) | `docs/SUPPORT.md` adımları |
| Tarama sonuçlarını karşılaştırma | `summary.json`'dan öncesi/sonrası (sshpocket arayüzü ile) |

## sshpocket entegrasyonu (o repoda)
Bileşen yükleyici, sözleşmeyi okuyan ayrıştırıcı, menü ve güvenlik kapıları sshpocket tarafında; takip:
syhgorath/sshpocket#3.
