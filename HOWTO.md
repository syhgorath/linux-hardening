# HOWTO: Ubuntu 26.04 hardening (adım adım)

Bu dosya "ne neydi, nerede ne yapacağım" sorusunun cevabıdır.
**Mac** = kontrol makinesi (Ansible burada çalışır). **Sunucu** = sertleştirilecek Ubuntu 26.04.

Mevcut durum (ilk test VM, 2026-10-09): Lynis hardening index **58 → 77**, uyarı yok.

---

## 0. Büyük resim

```
Mac (bu repo + Ansible)  --SSH-->  Sunucu(lar)
   audit.yml  : tarar (Lynis), değiştirmez
   harden.yml : sertleştirir (rollerle)
```

Sunucuda elle bir şey kurmazsın. Her şey Mac'ten Ansible ile yapılır.
Sunucuda sadece **hazırlık** (bölüm 2) gerekir.

---

## 1. Mac: tek seferlik kurulum

Bu Mac'te zaten yapıldı. Başka bir bilgisayarda yapacaksan:

```bash
git clone https://github.com/syhgorath/linux-hardening.git
cd linux-hardening
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements.txt   # paketler hash ile doğrulanır; Python >= 3.12
cp inventory/hosts.example.yml inventory/hosts.yml   # sonra düzenle (bölüm 3)
```

Her yeni terminalde, çalışmadan önce:

```bash
cd ~/Developer/hardening/linux-hardening
source .venv/bin/activate
```

Not: `inventory/hosts.yml` ve `scans/` bilerek git'te yok (IP ve tarama çıktıları sızmasın).

---

## 2. Sunucu: hazırlık (her yeni sunucuda bir kez)

Sunucuda yapılacaklar:

1. Ubuntu 26.04 kur, bir kullanıcı oluştur (örn. `kullanici`).
2. Güncelle:
   ```bash
   sudo apt update && sudo apt full-upgrade -y
   ```
3. Mac'ten SSH anahtarını kopyala (**Mac'te** çalıştır):
   ```bash
   ssh-copy-id kullanici@SUNUCU_IP
   ssh kullanici@SUNUCU_IP        # parolasız girdiğini doğrula
   ```
4. Ansible'ın sudo kullanabilmesi için **ikisinden birini** seç:
   - **Test VM (pratik):** sunucuda
     ```bash
     echo 'KULLANICI ALL=(ALL) NOPASSWD:ALL' | sudo tee /etc/sudoers.d/90-ansible-test && sudo chmod 440 /etc/sudoers.d/90-ansible-test && sudo visudo -c
     ```
   - **Üretim (önerilen):** parolasız sudo verme; Ansible'ı `--ask-become-pass` ile çalıştır (bölüm 4).
5. **Proxmox'ta snapshot al** (örn. `oncesi-hardening`). Bu senin geri dönüş noktan.

---

## 3. Mac: sunucuyu envantere ekle

`inventory/hosts.yml` dosyasını düzenle:

```yaml
all:
  children:
    hardening:               # (eski 'ubuntu' grubu da kabul edilir)
      hosts:
        test-vm-01:
          ansible_host: 192.168.1.50
          ansible_user: kullanici
        yeni-sunucu:                 # <- yeni satır
          ansible_host: 192.168.1.51
          ansible_user: kullanici
```

**Değişkenler nerede?** Varsayılanlar rollerin içindedir (`roles/hardening_*/defaults/main.yml`) ve her çalıştırmada
geçerlidir; `inventory/group_vars/all.yml` yalnızca **örnek geçersiz kılma** dosyasıdır (içi yorumlu). Değiştirmek için:

| Yöntem | Ne zaman |
|---|---|
| `inventory/group_vars/all.yml` veya `inventory/host_vars/<sunucu>.yml` | Varsayılan `inventory/hosts.yml` ile çalışırken (kalıcı) |
| `-e '{"hardening_ssh_allow_from": ["192.168.1.0/24"]}'` | Tek seferlik, her durumda çalışır |
| `-e @degiskenler.yml` | **Başka bir inventory (`-i /tmp/...`) ile** çalışırken; `group_vars` yalnızca inventory'nin yanındaysa yüklenir |

Ağ ayarlarını kontrol et (varsayılanı rol `defaults/`'ında, örnek `inventory/group_vars/all.yml`'de):

| Değişken | Anlamı | Dikkat |
|---|---|---|
| `hardening_ssh_allow_from` | SSH'a izin verilen ağlar (firewall) | **ZORUNLU, varsayılan boş.** Boşsa veya Ansible'ın bağlandığı IP burada değilse playbook durur. NAT/jump host varsa sunucunun *gördüğü* adresi yaz. **Sunucuya bağlanabileceğin TÜM ağları yaz (VPN + LAN + ...):** ufw yalnızca bunlardan SSH'a izin verir; yalnızca VPN yazarsan LAN'dan SSH kesilir (ping/ARP çalışır, ssh zaman aşar) ve geri alma güvenlik ağı bunu yakalamaz. Örn. `-e '{"hardening_ssh_allow_from": ["192.168.1.0/24"]}'` |
| `hardening_fail2ban_ignoreip` | Asla banlanmayacak adresler (varsayılan `127.0.0.1/8 ::1`) | Ansible'ın bağlandığı kontrol makinesinin **sunucunun gördüğü adresi** otomatik eklenir; tüm yönetim ağını muaf tutmak istersen açıkça yaz (önerilmez). Dinamik IP'den çalıştırırsan dosya her çalıştırmada değişir ve fail2ban yeniden başlar |
| `hardening_ssh_disable_password` | SSH parola girişini kapat | Anahtar yoksa rol zaten durur |
| `hardening_ssh_kbdinteractive` | 2FA/TOTP için `keyboard-interactive` (varsayılan `false`) | `true` ise `AuthenticationMethods publickey,keyboard-interactive` yazılır. PAM 2FA'sı **sizin kurmanız gerekir**; yanlışsa erişim kesilir. Bağlantı doğrulaması yalnızca banner'ı sınar |
| `hardening_ssh_allow_tcp_forwarding` | `no` \| `local` \| `remote` \| `yes` (varsayılan `"no"`) | ProxyJump için jump host'ta en az `local`. YAML'da `no`'yu tırnaklayın (tırnaksız bool olur ve doğrulama durdurur) |
| `hardening_ufw_extra_allow` | Ek açılacak portlar, örn. `["443/tcp"]` | Web sunucusu vb. için |

Bir sunucuya özel ayar: `inventory/host_vars/yeni-sunucu.yml` oluşturup oraya yaz.

---

## 4. Mac: çalıştırma sırası

```bash
source .venv/bin/activate

# 4.1 Önce ölç (hiçbir şeyi değiştirmez, sadece lynis kurar)
ansible-playbook playbooks/audit.yml

# 4.2 Ne değişecek, önce gör (kuru çalıştırma)
ansible-playbook playbooks/harden.yml --check --diff

# 4.3 Uygula
ansible-playbook playbooks/harden.yml

# 4.4 Tekrar ölç ve karşılaştır
ansible-playbook playbooks/audit.yml
```

Seçenekler:

- Tek sunucu: `--limit yeni-sunucu`
- Parolalı sudo: `--ask-become-pass`
- Sadece bazı roller: `--tags base,auth,kernel,auditd,fail2ban,aide,ufw,ssh`
- İlk bağlantıda host key sorusu çıkarsa önce bir kez elle `ssh kullanici@IP` ile bağlanıp `yes` de.

Bitince ikinci kez `harden.yml` çalıştır; `changed=0` çıkmalı (idempotent). Çıkmıyorsa bir sorun var.

Önemli: AIDE'nin ilk veritabanı birkaç dakika sürer, takıldı sanma.

---

## 5. Sonuç nerede, skor nasıl okunur

Tarama çıktıları Mac'te, **kullanıcı klasöründe**: `~/.local/share/linux-hardening/scans/<sunucu>/<tarih>/` (`XDG_DATA_HOME` varsa onun altında). Hassas veri olduğu için paket klasörüne yazılmaz; konumu `hardening_scan_dir` ile değiştirebilirsin. (0.2.0 ve öncesinde varsayılan repodaki `scans/` idi; eski çıktılar orada kalır.)

```bash
# En son skor (hardening_index) ve uyarılar
R=$(ls -d ~/.local/share/linux-hardening/scans/test-vm-01/*/ | tail -1)
grep -E '^hardening_index|^warning\[\]' $R/lynis-report.dat
grep '^suggestion\[\]' $R/lynis-report.dat | cut -d'|' -f1,2
```

Aynısını sunucuda elle de görebilirsin (aynı sonucu verir, 77 bunun doğrulaması):

```bash
sudo lynis audit system
```

Her taramanın klasöründe ayrıca makine-okunur bir **`summary.json`** üretilir:

```json
{ "date": "2026-10-10T11:12:21Z", "hardening_index": 77, "host": "test-vm-01",
  "suggestions": 25, "tests_performed": 264, "warnings": 0 }
```

| Alan | Kaynak (`lynis-report.dat`) |
|---|---|
| `host` | envanterdeki ana makine adı |
| `date` | özetin üretildiği an (UTC, ISO 8601) |
| `hardening_index` | `hardening_index=` satırı |
| `tests_performed` | `tests_executed=` satırındaki `\|` ile ayrılmış test sayısı |
| `warnings` / `suggestions` | `warning[]=` / `suggestion[]=` satır sayısı |

Rapordan okunamayan alan `null` olur (0 değil). Dosyada yalnızca sayılar ve ana makine adı vardır.
Çıktı konumunu `hardening_scan_dir` ile değiştirebilirsin (varsayılan kullanıcı klasörü, yukarıya bak); `<host>` ve `<tarih>`
dizinleri 0700, dosyalar 0600 yazılır (varsayılan konumda uygulama dizini ve `scans/` de 0700; verdiğin özel yolun kendi izinlerine dokunulmaz). `audit.yml` her çalışmada yeni bir tarih klasörü ürettiği için
**idempotent değildir** (bu beklenen); `--check` modunda tarama yapılmaz ve rapor/özet üretilmez.

Skor tek başına hedef değil. Önemli olan **uyarı sayısı (0)** ve bilerek yapılmayanların `docs/decisions.md`'de kayıtlı olması.

---

## 6. Ne uygulanıyor (özet)

| Rol (`roles/`) | Yaptığı |
|---|---|
| `hardening_base` | Otomatik güvenlik güncellemesi (reboot yok), USB depolama kapalı, banner, postfix yerine `dma` |
| `hardening_auth` | Parola yaşı, umask 027, pwquality (min 14), hashing rounds |
| `hardening_kernel` | sysctl ağ/kernel ayarları, dccp/sctp/rds/tipc kapalı |
| `hardening_auditd` | auditd + temel kurallar |
| `hardening_fail2ban` | SSH jail |
| `hardening_aide` | Dosya bütünlüğü veritabanı |
| `hardening_time` | Salt okunur zaman raporu (chrony durumu, kaynaklar, saat kayması); `harden` çıktısında `ZAMAN:` / `UYARI (zaman):`. Hiçbir şeyi değiştirmez |
| `hardening_ufw` | Gelen trafik varsayılan engelli, SSH sadece yönetim ağından |
| `hardening_ssh` | Root yok, parola yok, MaxAuthTries 3, forwarding kapalı |

Bilerek yapılmayanlar ve nedenleri: `docs/decisions.md`.

---

## 7. Sorun giderme

Sertleştirmenin **meşru kullanımları bozabileceği** yerler (Docker, mail sunucusu, SSH yönlendirme, ufw vb.) ve kaçış yolları: [docs/known-issues.md](docs/known-issues.md).

| Durum | Ne yap |
|---|---|
| Sunucuya SSH ile giremiyorum (firewall/SSH sonrası) | **Proxmox konsolundan** gir: `sudo ufw disable` veya `/etc/ssh/sshd_config.d/00-hardening.conf` dosyasını düzelt. Olmazsa snapshot'a dön |
| `Permission denied (publickey)` | `ssh-copy-id` yapılmamış ya da yanlış kullanıcı (`ansible_user`) |
| `sudo: a password is required` | NOPASSWD ayarı yok → `--ask-become-pass` kullan ya da bölüm 2.4 |
| Proxmox snapshot'ına döndükten sonra `apt`/TLS hataları ya da tuhaf zaman damgaları | VM saati geride kalmış olabilir (snapshot saati). `timedatectl` ile bakın (**dikkat:** "synchronized: yes" yanıltıcı olabilir, tarihi `date -u` ile karşılaştırın). `sudo chronyc makestep` saati düzeltir, **ama chrony'nin kaynakları henüz seçilmemişse (`chronyc sources` çıktısında `^?`) sessizce hiçbir şey yapmaz**; o zaman `sudo systemctl restart chrony` kullanın (başlangıçtaki `makestep 1 3` büyük adımı birkaç saniyede yapar). İkisi de denendi (test VM'i, ~8 günlük kayma) |
| Host key hatası | Önce elle `ssh kullanici@IP` ile bağlanıp kabul et |
| `ansible: command not found` | `source .venv/bin/activate` yapılmamış |
| `hardening_ssh_allow_from boş veya tanımsız` / `kaynak adres ... içinde değil` | Yönetim ağını `hardening_ssh_allow_from`'a yaz (bölüm 3). Bu kontrol seni kilitlenmeden korur, aşmaya çalışma |
| `Ansible root olarak bağlanıyor` | `ansible_user` olarak sudo yetkili normal kullanıcı ver; root ile SSH sertleştirmesi bağlantıyı keser |
| `Yeni SSH bağlantısı doğrulanamadı; GERİ ALINDI` | Kural: sshd drop-in silindi, sshd yenilendi, ufw kapatıldı. Erişimi doğrulayıp nedeni bul (anahtar ssh-agent'ta mı? ağ?) ve tekrar çalıştır |
| Beklenmedik değişiklik oldu | Proxmox snapshot'a dön, `--check --diff` ile farkı incele |
| Bir kontrolü kapatmak istiyorum | İlgili değişkeni `group_vars`/`host_vars` içinde değiştir veya `--tags` ile rolü atla; kararı `docs/decisions.md`'ye yaz |

---

## 7a. Erişim kaybı korumaları (otomatik)

`harden.yml` firewall/SSH değiştirmeden önce ve sonra şunları yapar (tam çalıştırmada ve `--tags ufw` / `--tags ssh` ile çalışırken; OS/sürüm preflight'ı ise **her** `--tags` çalıştırmasında da yapılır):

**Önce (durdurur, `--check`'te de çalışır):**
- `hardening_ssh_allow_from` boş/tanımsız/geçersizse durur.
- Sunucunun gördüğü bağlantı kaynağı (`SSH_CONNECTION`) bu ağlarda değilse durur.
- `root` olarak bağlanılıyorsa durur.
- Parola girişini kapatmadan önce giriş kullanıcısının *gerçek* home dizininde `authorized_keys` var mı bakar.

**Sonra (`--check`'te atlanır):** kontrol makinesinden yeni ve bağımsız bir `ssh` bağlantısı (BatchMode) açar.
Başarılıysa geri alma güvenlik ağı **disarm** edilir. Başarısızsa sunucu **değişiklikten önceki duruma döner**
(`hardening_rollback`: sshd drop-in ve ufw kuralları/aktif-pasif durumu yedekten geri yüklenir, **silinmez**) ve
playbook hata ile durur.

**Geri alma güvenlik ağı (`hardening_rollback`):** ufw/ssh değişmeden hemen önce sunucuda önceki durum yedeklenir ve bir
systemd zamanlayıcısı kurulur (`hardening_rollback_timeout`, varsayılan 300 sn). Doğrulama başarılıysa disarm edilir.
**Bağlantı tamamen kaybolursa** (Mac kitlenir, eski oturum kopar) sunucu süre dolunca **kendini** önceki duruma döndürür.
`hardening_rollback_enabled: false` ile kapatılabilir (önerilmez; açık uyarı verir). systemd yoksa ufw/ssh'a dokunulmaz.

Sınırlar (bilerek açık yazıyoruz):
- **Geri alınmayanlar:** paketler, sysctl, auditd, fail2ban, AIDE ve diğer roller. Sadece SSH drop-in ve ufw geri alınır.
- Bağlantı doğrulanamazsa geri alma anında yapılır; **bağlantı tamamen kaybolursa** sunucu `hardening_rollback_timeout` sn sonra kendini geri alır. O süre boyunca erişim yoktur. Sunucu bu sırada **yeniden başlarsa** zamanlayıcı `armed` iken yeniden etkinleşir ve açılıştan N sn sonra geri alır. Yine de son çare Proxmox konsolu/snapshot'tır.
- **Gereksiz geri alma olabilir:** kontrol makineniz süre dolmadan dönmezse ve değişiklik iyiyse sunucu yine de geri alır (*erişim kaybı yerine gereksiz geri alma* bilinçli seçim). Süre içinde dönerseniz `hardening-rollback status/disarm` ile bakılır.
- Doğrulama `ssh` komutunu kontrol makinesinde çalıştırır: anahtar `ssh-agent`'ta (veya `ansible_ssh_private_key_file`) olmalıdır, passphrase sorulamaz. Agent'ta anahtar yoksa doğrulama başarısız olur ve gereksiz yere geri alınır.
- Agent'ta 3'ten fazla anahtar varsa ve `ansible_ssh_private_key_file` verilmediyse, `MaxAuthTries 3` yüzünden "Too many authentication failures" ile yanlış negatif olabilir.
- `authorized_keys` kontrolü varsayılan konuma bakar (özel `AuthorizedKeysFile` ayarını bilmez) ve sadece dosyanın dolu olduğunu doğrular, bağlandığın anahtarın içinde olduğunu değil.
- `ufw` komutları `--check` modunda çalışmaz; önizleme firewall değişikliğini göstermez.
- `--check` modunda servis başlatma (auditd, fail2ban) ve `restart fail2ban` handler'ı **atlanır**; temiz bir sunucuda paketler henüz kurulu olmadığı için bunlar simüle edilemez. Önizleme servis durumunu göstermez.
- **SSH portu değiştirilmez/desteklenmez.** ufw kuralı sshd'nin *gerçekten dinlediği* porttan (`ss`) yazılır; `hardening_ssh_port` kaldırıldı. sshd bulunamazsa ufw'ye dokunulmaz ve playbook durur.

---

## 7a-2. Geri alma güvenlik ağını yönetmek

Kontrol makineniz bir koşu sırasında kitlenirse ya da bağlantı kopup geri dönerseniz, sunucudaki zamanlayıcının durumuna
bakıp "değişiklik iyi" diyebilirsiniz. Bu komutlar preflight/erişim korumalarını çalıştırmaz (kontrol kaybından sonra da çalışmalı).

```bash
ansible-playbook playbooks/rollback.yml                  # status (varsayılan, salt-okunur)
ansible-playbook playbooks/rollback.yml --tags disarm    # "değişiklik iyi": geri almayı iptal et
ansible-playbook playbooks/rollback.yml --tags now       # hemen önceki duruma dön (armed ise)
```

| Durum | Ne görürsünüz | Ne yapmalı |
|---|---|---|
| `armed=yes`, `timer=active` (kalan süre görünür) | Geri alma bekliyor | Erişim iyiyse `--tags disarm`; sorun varsa bekleyin ya da `--tags now` |
| `armed=no`, `timer=inactive` | Bekleyen geri alma yok | Süre dolmuş ve geri alınmış olabilir; `harden.yml`'i yeniden çalıştırın |

`disarm` ve `now` **`never`** etiketlidir: `--tags` ile açıkça istenmedikçe çalışmaz. Sunucuda kayıt:
`journalctl -t hardening-rollback`.

---

## 7b. Üretim sunucuları

Test VM'de parolasız sudo kullandık; **üretimde kullanma.** Onun yerine:

```bash
ansible-playbook playbooks/harden.yml --ask-become-pass
```

- Sudo parolasını çalıştırma başında **bir kez** sorar; sadece o çalıştırma boyunca bellekte durur, diske/repoya/loga yazılmaz.
- Verdiğin tek parola `--limit`'teki **tüm** sunuculara denenir. Parolalar farklıysa sunucuları ayrı ayrı çalıştır (`--limit sunucu1`) ya da `ansible-vault` kullan.
- Sunucu sayısı artarsa uzun vadede: sadece anahtarla girilen, kısıtlı sudo'lu ayrı bir `ansible` servis hesabı.
- Kalıcı `NOPASSWD` sudo bir güvenlik bulgusudur; sadece test VM'de kalsın.

Üretimde kontrol listesi (sırayla):

1. Proxmox snapshot / yedek al.
2. Tek sunucuyla başla: `--limit sunucu1`.
3. Önce `--check --diff`, çıktıyı oku.
4. `hardening_ssh_allow_from` (zorunlu) **o sunucuya göre doğru mu?** (fail2ban `ignoreip` kontrol makinesi adresini zaten otomatik ekler.) Yanlışsa firewall seni dışarıda bırakır (en riskli ayar).
5. Sunucuda çalışan servis varsa (web, veritabanı...) portlarını `hardening_ufw_extra_allow` ile aç; yoksa firewall onları kapatır.
6. Bakım penceresinde uygula. Otomatik reboot yoktur ama paket/servis değişiklikleri kısa kesinti yapabilir.
7. Kademeli git: ilk gün `--tags base,auth,kernel`, sonra `auditd,fail2ban,aide`, en son `ufw,ssh`.
8. Sonunda `audit.yml` ile tekrar ölç, sorun yoksa sıradaki sunucuya geç.

## 8. Bakım

- Değişiklik yaptıysan: `git add -A && git commit -m "..." && git push`
- Ayda bir: `audit.yml` çalıştır, skoru ve uyarıları karşılaştır.
- Bekleyen iş: CIS Ubuntu 26.04 Benchmark'ı için hazır Ansible rolü (`UBUNTU26-CIS`) ve OpenSCAP 26.04 içeriği çıkınca bizim rollerle karşılaştır (`docs/decisions.md` "BEKLEYEN").
- Test VM'deki `/etc/sudoers.d/90-ansible-test` (parolasız sudo) sadece test içindir; üretimde kullanma.
