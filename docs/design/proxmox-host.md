# Proxmox VE hostu (iskelet, işlevsiz)

> **Durum: tasarım notu + boş iskelet.** Burada hiçbir sertleştirme yazılı değil ve `harden.yml` bu dosyalara bağlı değil.
> Amaç, Proxmox hostu desteği eklendiğinde dosyaların nereye geleceğini önceden görmek. Karar bekleyen konular aşağıda.

## Kapsam
- **Kapsam içi:** Proxmox VE'nin **kendisi** (hipervizör hostu).
- **Kapsam dışı:** Proxmox üstünde çalışan sanal makineler. Onlar sıradan Ubuntu'dur ve mevcut `ubuntu-26.04` profiliyle çalışır
  (test VM'imiz böyle). Raspberry Pi ayrı bir iştir (`docs/ROADMAP.md`).

## İki katman (neden "profil" yetmiyor)
| Katman | Ne | Nerede |
|---|---|---|
| **OS** | Proxmox VE, Debian tabanlıdır; sürümü/dağıtımı `/etc/os-release`'ten gelir | `vars/<dagitim>-<surum>.yml`, `hardening_supported_os`, `component.yml` `profiles` (Debian sürümü eklenince) |
| **Platform** | "Bu bir Proxmox hostu" bilgisi | yeni değişken `hardening_platform` (öneri: `generic` \| `proxmox-host`) ve preflight doğrulaması |

sshpocket profili yalnızca `os-release` `ID-VERSION_ID`'den algılar; `proxmox` bir profil kimliği olarak **algılanamaz**.
Bu yüzden platform bir profil değil, **paket değişkeni** olmalı (karar bekliyor, bkz. "Açık sorular").

## Dosya haritası (bu dalda oluşturulanlar)
```
docs/design/proxmox-host.md                       # bu not
roles/hardening_pve_firewall/                     # ufw yerine pve-firewall (iskelet)
  defaults/main.yml
  tasks/main.yml
roles/hardening_pve_access/                       # root/SSH/küme erişimi: Ubuntu kuralları burada çakışır (iskelet)
  defaults/main.yml
  tasks/main.yml
roles/hardening_preflight/tasks/platform.yml      # "gerçekten Proxmox mu?" denetimi (iskelet; main.yml'den ÇAĞRILMIYOR)
```
İleride gelecekler (henüz yok): `vars/debian-<surum>.yml`, `hardening_platform` değişkeni (`component.yml` `vars` + rol `defaults`),
`harden.yml`'de `when: hardening_platform == 'proxmox-host'` ile platform rolleri, `ufw` rolünün Proxmox'ta çalışmaması için koruma.

## Ortak kalanlar / ayrılanlar
- **Ortak (değişmez):** `base`, `auth`, `kernel` (sysctl farkları hariç), `auditd`, `fail2ban`, `aide`, `hardening_rollback`,
  erişim kaybı korumaları ve doğrulama.
- **Ayrılan:** firewall (`hardening_ufw` yerine `hardening_pve_firewall`), root/SSH/küme erişimi (`hardening_pve_access`),
  `ip_forward` gibi sysctl istisnaları.

## Açık sorular (cevaplanmadan kod yazılmaz)
1. **Root ve SSH.** Ubuntu rollerimiz `root` ile bağlanmayı reddeder ve root girişini kapatır. Proxmox yönetimi ve (varsa) küme
   düğümleri arası işlemler `root` ile yapılıyor olabilir. *Doğrulanmadı.* Hangi hesapla yönetilecek, küme var mı?
2. **Firewall.** `pve-firewall` mı, nftables/ufw mu? Kümeli kurulumda kural kapsamı (datacenter / node / VM) ne olmalı?
   `ufw` rolü Proxmox hostunda **çalışmamalı**; korumanın şekli?
3. **`ip_forward` ve köprüler.** `kernel` rolünün sysctl'leri VM ağını bozabilir (yönlendirme gerekir). Hangi ayarlar istisna?
4. **Erişim kaybı güvenlik ağı.** `hardening_rollback` yalnızca sshd drop-in ve ufw'yi geri alır. Proxmox firewall'u için
   geri alma ne yapacak?
5. **Platform nasıl bildirilecek.** Değişken (öneri) mi, sshpocket profil algılamasının genişlemesi mi? Bu karar sshpocket
   tarafını da etkiler.
6. **Hangi Debian/Proxmox sürümleri.** Desteklenecek sürüm aralığı (test ortamı gerekir).
7. **Test ortamı.** Gerçek bir Proxmox hostu (ya da iç içe sanallaştırma) gerekir; Docker LAB'ı bunun için uygun değil.

## Uygulama sırası (öneri)
1. Yukarıdaki açık soruları kapat (bu not güncellenir).
2. Debian tabanı için OS katmanı (`vars/`, `hardening_supported_os`) ve profil.
3. `hardening_platform` + preflight doğrulaması (yanlış platformda **dur**).
4. `hardening_pve_access`, sonra `hardening_pve_firewall`; her biri ayrı PR, test hostunda doğrulanır.
