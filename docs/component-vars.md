# Bileşen değişkenleri (`component.yml` → `vars`)

sshpocket bu değişkenleri kullanıcıdan alır, **kendisi doğrular** ve `-e @dosya` ile geçirir. Alan şeması sshpocket paket
standardının §6'sıyla aynıdır; varsayılanlar rollerin `defaults/main.yml` dosyalarıyla **aynı** olmak zorundadır
(`scripts/check-consistency.py` denetler). Eski biçim (yalnızca ad listesi) geçiş için kabul edilir.

| Değişken | Tür | Zorunlu | Varsayılan | Anlam / dikkat |
|---|---|---|---|---|
| `hardening_ssh_allow_from` | `list[cidr]` | **evet** | yok (`[]`) | SSH'a izin verilen yönetim ağları. Boşken `harden.yml` (ufw/ssh) **durur**. Kontrol makinesinin sunucudan görünen adresi bu listede olmalı, yoksa erişim koruması durdurur. **Sunucuya bağlanabileceğin tüm ağları yaz (VPN + LAN + ...):** ufw yalnızca bunlardan SSH'a izin verir; yalnızca VPN yazarsan LAN'dan SSH kesilir ve geri alma güvenlik ağı bunu yakalamaz. |
| `hardening_scan_dir` | `path` | hayır | kullanıcı klasörü: `$XDG_DATA_HOME` (yoksa `~/.local/share`) altında `linux-hardening/scans` | Lynis raporları ve `summary.json` buraya yazılır. **Hassas veri:** dizin 0700, dosyalar 0600; paket klasörü USB/paylaşımlı olabileceğinden varsayılan paketin dışındadır (#37). sshpocket bunu zaten her zaman kendi kullanıcı klasörüne yönlendirir. HOME/XDG de yoksa ve değer verilmemişse `audit.yml` durur. |
| `hardening_ufw_prune_ssh` | `bool` | hayır | `false` | `false`: `allow_from`'dan çıkardığın ağın SSH kuralı firewall'da kalıyorsa **uyarır** (sunucu değişkenden daha açıktır). `true`: bu kuralları **siler**. Yalnızca bu rolün yazdığı biçime (`ufw allow from <ağ> to any port <ssh portu> proto tcp`) bakar; ağlar normalleştirilerek karşılaştırılır; `extra_allow`'dakilere ve kontrol makinesinin adresini kapsayan kurala dokunmaz; `allow_from` boşsa ya da adres bilinmiyorsa hiçbir şey silmez. Silmeden sonra `allow_from`'daki bir ağın kuralı eksikse `ufw` etkinleştirilmeden durur. `warn_if: true`. |
| `hardening_rollback_enabled` | `bool` | hayır | `true` | `false` = geri alma güvenlik ağı **kapalı**; erişim kaybında sunucu kendini geri almaz. `warn_if: false` → arayüz uyarı göstermeli. |
| `hardening_rollback_timeout` | `int` (30–3600) | hayır | `300` | Doğrulanmazsa sunucunun kendini geri alma süresi (saniye). Aralık dışı ya da sayı olmayan değerde playbook, ufw/ssh'a **dokunmadan** durur. |

`min`/`max` sınırlarını bileşen sahibi belirler; değerler önerisi değil, rolün uyguladığı doğrulamayla aynıdır
(`roles/hardening_rollback/tasks/main.yml`).
