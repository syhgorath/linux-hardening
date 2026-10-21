# Proxmox VE hostu (iskelet, işlevsiz)

> **Koruma YAPILDI (v0.4.0 sonrası):** `hardening_preflight` artık Proxmox hostunda (`/etc/pve` ya da `/usr/bin/pveversion`) `hardening_allow_unsupported` dahil HİÇBİR bayrakla atlatılamayacak şekilde durur. Proxmox hostunu SERTLEŞTİRME hâlâ yok ve aşağıdaki açık sorular cevaplanmadan yazılmaz.
>
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
Bu yüzden platform bir profil değil, **paket değişkeni** olur (**karar verildi**, bkz. "Açık sorular" 5).

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

## Gerçek Proxmox VE 9.2 keşfi (2026-10-21, iç içe Proxmox VM'i, SALT OKUNUR; verification-log 40)
Normal kullanıcı (`claude`) + SSH anahtarıyla, hiçbir şey değiştirilmeden:
- **Sürüm:** `pve-manager 9.2.21`, Debian 13.7 (trixie), çekirdek `7.0.14-25-pve`. **Tek düğüm**: `corosync` etkin değil (küme yok).
- **`sudo` KURULU DEĞİL.** Proxmox varsayılan kurulumunda yoktur (`sudo` grubu var, paket yok). Bu paketin tüm rolleri `become: sudo` ister: **önkoşul `apt-get install sudo` + kullanıcıya sudoers**. Debian 13'ün sudo'su klasiktir (sudo-rs değil), yani Ansible'ın parolalı `become`'ı çalışır.
- **Firewall:** `pve-firewall` servisi etkin (`pvefw-logger` dahil), `ufw` kurulu değil. Yani bu pakette `ufw` yerine `pve-firewall` yönetilecek (aşama 4).
- **SSH:** `PermitRootLogin yes` (Proxmox varsayılanı), `sshd_config.d/` boş, `ssh.service` etkin, `ssh.socket` kapalı. Web arayüzü `:8006`, `pvedaemon` `127.0.0.1:85`.
- **Ağ:** tek köprü `vmbr0` (yönetim adresi köprünün üzerinde). `net.ipv4.ip_forward=0`, `net.bridge.bridge-nf-call-iptables=0` bu hostta; VM'ler köprü üzerinden L2 ise forward gerekmez, NAT/yönlendirme kullanılırsa gerekir (kernel rolünün sysctl'leri bu yüzden istisna ister).
- **Zaman/günlük:** `chrony` etkin (`systemd-timesyncd` kapalı), `rsyslog` kapalı (yalnız `journald`).
- **apt:** Debian ve `pve-no-subscription` kaynakları etkin; `pve-enterprise` ve `ceph-enterprise` KAPALI. Yani `apt` çalışır (abonelik 401 hatası yok).
- **PATH:** `/usr/sbin` normal kullanıcının PATH'inde değil (`sysctl`, `pve-firewall`, `sshd`): araçlar mutlak yolla ya da root olarak çağrılmalı.
- **Koruma:** Debian 13 profili eklendikten sonra bile `harden.yml --check` bu hostta `Bu sunucu bir Proxmox VE hostu` diyerek durdu; `-e hardening_allow_unsupported=true` ile de durdu.

### Aşama 2 YAPILDI: salt okunur rapor (`playbooks/pve-report.yml`)
`hardening_pve_report` rolü (harden.yml'e bağlı DEĞİL) Proxmox'un durumunu okur ve iki liste üretir: **uyarı** (bugünkü gerçek açık: firewall devre dışı, root+parola SSH, çalışmayan servis, dışa açık MTA, ufw ile çakışma) ve **not** (sertleştirme tasarımı için). Ortak rollerin `--check`'te Proxmox'ta ne yapmak İSTEDİĞİ de görüldü (koruma yalnızca önizleme için `hardening_proxmox_markers=[]` ile atlatıldı, hiçbir şey değiştirilmedi): `base` (postfix → dma, unattended-upgrades, usb-storage), `auth`, `kernel` (sysctl, modül kara listesi), `files` (**`/tmp` ve `/dev/shm` noexec**), `auditd`, `fail2ban`, `aide` (VM disklerini taramamalı), `ufw` (**Proxmox'ta çalışmamalı**), `ssh` (`PermitRootLogin no`, küme için `prohibit-password` gerekir), `sudo`. Aşama 3 bunları platform değişkenine bağlı geçersiz kılmalarla çözecek.

### Aşama 3 YAPILDI (yalnızca `--check`): `hardening_platform` ve platform bağlantıları
- `hardening_platform` (`generic` \| `proxmox-host`) paket değişkeni; preflight gerçek platformu doğrular: Proxmox + `generic` → DURUR; `proxmox-host` + Proxmox değil → DURUR; `proxmox-host` + gerçek koşu → DURUR (yalnız `--check`); geçersiz değer → DURUR. `hardening_allow_unsupported` hiçbirini atlatmaz.
- **Kesin yasaklar** (Proxmox'ta hiçbir ayarla çalışmaz): `hardening_base` MTA değişimi, `hardening_ufw` rolü (harden.yml `when`).
- **Politika** (varsayılan Proxmox'ta KAPALI, `hardening_pve_strict=true` ile açılır): `/tmp` ve `/dev/shm` `noexec`, `usb-storage` engeli.
- **AIDE**: `hardening_aide_pve_excludes` (`!yol` satırları, veritabanı ilk üretilmeden önce). Denenmedi.
- Neden varsayılan DEĞER değiştirmek yerine `when` + tek anahtar: `component.yml` varsayılanı rol varsayılanıyla birebir aynı olmalı ve sshpocket şemasına yeni anahtar eklemek istemedik.
- Sonraki: `ssh` (`PermitRootLogin`, küme), `kernel` sysctl/modül gözden geçirmesi, aşama 4 (`pve-firewall` + geri alma ağı kapsamı), sonra gerçek koşu.

## Açık sorular (cevaplanmadan kod yazılmaz)
1. **Root ve SSH. KISMEN CEVAPLANDI (2026-10-21):** kullanıcı root ile yönetmiyor (normal kullanıcı + sudo), tek düğüm; Proxmox'un `PermitRootLogin yes` varsayılanı ve ileride küme düğümleri arası root SSH'ı hâlâ açık konu. Ubuntu rollerimiz `root` ile bağlanmayı reddeder ve root girişini kapatır. Proxmox yönetimi ve (varsa) küme
   düğümleri arası işlemler `root` ile yapılıyor olabilir. *Doğrulanmadı.* Hangi hesapla yönetilecek, küme var mı?
2. **Firewall. CEVAPLANDI (2026-10-21): `pve-firewall` kullanılabilir** (host'ta etkin). Kümeli kapsam (datacenter/node/VM) kümesiz tek düğümde şimdilik sorun değil. Orijinal soru: `pve-firewall` mı, nftables/ufw mu? Kümeli kurulumda kural kapsamı (datacenter / node / VM) ne olmalı?
   `ufw` rolü Proxmox hostunda **çalışmamalı**; korumanın şekli?
3. **`ip_forward` ve köprüler.** `kernel` rolünün sysctl'leri VM ağını bozabilir (yönlendirme gerekir). Hangi ayarlar istisna?
4. **Erişim kaybı güvenlik ağı.** `hardening_rollback` yalnızca sshd drop-in ve ufw'yi geri alır. Proxmox firewall'u için
   geri alma ne yapacak?
5. **Platform nasıl bildirilecek. CEVAPLANDI (2026-10-21, kullanıcı onayı): paket değişkeni.** Platform mantığı bu pakette kalır, sshpocket yalnızca çalıştırıcıdır:
   - Platform bir **paket değişkenidir** (`hardening_platform`, öneri: `generic` | `proxmox-host` | `raspberry-pi`); sshpocket bunu `-e` ile geçirebilir, `/etc/os-release` algılamasının genişlemesi GEREKMEZ.
   - Paketin `hardening_preflight` rolü gerçek platformu **doğrular** (örn. `/etc/pve` var mı) ve seçilenle uyuşmazsa DURUR. Bu korumanın yarısı yapıldı: `/etc/pve` ya da `/usr/bin/pveversion` varsa rol `hardening_allow_unsupported` ile bile durur (v0.4.0 sonrası).
   - Debian desteklenmeye başlayınca `component.yml` `profiles` listesine `debian-13` eklenir; sshpocket'in profil kapısı geçer, ama platform kararını paket verir.
   - Sshpocket'e düşen: bir "platform" seçimi göstermek ve değişkeni iletmek. Bunun sshpocket'te kolay olup olmadığı o tarafın kararıdır (bu depodan görülemez).
   - Proxmox/RPi sertleştirmesi bu karardan SONRA da yazılmaz: aşağıdaki diğer sorular (1-4, 6, 7) cevaplanmadan kod yok.
6. **Hangi Debian/Proxmox sürümleri.** Desteklenecek sürüm aralığı (test ortamı gerekir).
7. **Test ortamı. CEVAPLANDI (2026-10-21): iç içe Proxmox VM'i** (Proxmox VE 9.2, tek düğüm) kuruldu ve erişilebilir; Docker LAB'ı uygun değil. Snapshot kullanıcıda.

## Uygulama sırası (öneri)
1. Yukarıdaki açık soruları kapat (bu not güncellenir).
2. Debian tabanı için OS katmanı (`vars/`, `hardening_supported_os`) ve profil.
3. `hardening_platform` + preflight doğrulaması (yanlış platformda **dur**).
4. `hardening_pve_access`, sonra `hardening_pve_firewall`; her biri ayrı PR, test hostunda doğrulanır.
