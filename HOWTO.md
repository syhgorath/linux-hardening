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
.venv/bin/pip install -r requirements.txt
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
    ubuntu:
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
| `hardening_ssh_allow_from` | SSH'a izin verilen ağlar (firewall) | **ZORUNLU, varsayılan boş.** Boşsa veya Ansible'ın bağlandığı IP burada değilse playbook durur. NAT/jump host varsa sunucunun *gördüğü* adresi yaz. Örn. `-e '{"hardening_ssh_allow_from": ["192.168.1.0/24"]}'` |
| `hardening_fail2ban_ignoreip` | Asla banlanmayacak ağlar | Aynı ağı yaz |
| `hardening_ssh_disable_password` | SSH parola girişini kapat | Anahtar yoksa rol zaten durur |
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

Tarama çıktıları Mac'te: `scans/<sunucu>/<tarih>/`

```bash
# En son skor (hardening_index) ve uyarılar
R=$(ls -d scans/test-vm-01/*/ | tail -1)
grep -E '^hardening_index|^warning\[\]' $R/lynis-report.dat
grep '^suggestion\[\]' $R/lynis-report.dat | cut -d'|' -f1,2
```

Aynısını sunucuda elle de görebilirsin (aynı sonucu verir, 77 bunun doğrulaması):

```bash
sudo lynis audit system
```

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
| `hardening_ufw` | Gelen trafik varsayılan engelli, SSH sadece yönetim ağından |
| `hardening_ssh` | Root yok, parola yok, MaxAuthTries 3, forwarding kapalı |

Bilerek yapılmayanlar ve nedenleri: `docs/decisions.md`.

---

## 7. Sorun giderme

| Durum | Ne yap |
|---|---|
| Sunucuya SSH ile giremiyorum (firewall/SSH sonrası) | **Proxmox konsolundan** gir: `sudo ufw disable` veya `/etc/ssh/sshd_config.d/00-hardening.conf` dosyasını düzelt. Olmazsa snapshot'a dön |
| `Permission denied (publickey)` | `ssh-copy-id` yapılmamış ya da yanlış kullanıcı (`ansible_user`) |
| `sudo: a password is required` | NOPASSWD ayarı yok → `--ask-become-pass` kullan ya da bölüm 2.4 |
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
Başarısızsa **hâlâ açık olan eski oturum** üzerinden: `/etc/ssh/sshd_config.d/00-hardening.conf` silinir,
sshd yeniden yüklenir, ufw kapatılır ve playbook hata ile durur.

Sınırlar (bilerek açık yazıyoruz):
- **Geri alınmayanlar:** paketler, sysctl, auditd, fail2ban, AIDE ve diğer roller. Sadece SSH drop-in ve ufw geri alınır.
- Geri alma, eski SSH oturumunun hâlâ canlı olmasına dayanır. Eski bağlantı da koparsa kurtarma **yapılamaz**; Proxmox konsolu/snapshot gerekir.
- Doğrulama `ssh` komutunu kontrol makinesinde çalıştırır: anahtar `ssh-agent`'ta (veya `ansible_ssh_private_key_file`) olmalıdır, passphrase sorulamaz. Agent'ta anahtar yoksa doğrulama başarısız olur ve gereksiz yere geri alınır.
- Agent'ta 3'ten fazla anahtar varsa ve `ansible_ssh_private_key_file` verilmediyse, `MaxAuthTries 3` yüzünden "Too many authentication failures" ile yanlış negatif olabilir.
- `authorized_keys` kontrolü varsayılan konuma bakar (özel `AuthorizedKeysFile` ayarını bilmez) ve sadece dosyanın dolu olduğunu doğrular, bağlandığın anahtarın içinde olduğunu değil.
- `ufw` komutları `--check` modunda çalışmaz; önizleme firewall değişikliğini göstermez.
- **SSH portu değiştirilmez/desteklenmez.** ufw kuralı sshd'nin *gerçekten dinlediği* porttan (`ss`) yazılır; `hardening_ssh_port` kaldırıldı. sshd bulunamazsa ufw'ye dokunulmaz ve playbook durur.

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
4. `hardening_ssh_allow_from` (zorunlu) ve `hardening_fail2ban_ignoreip` **o sunucuya göre doğru mu?** Yanlışsa firewall seni dışarıda bırakır (en riskli ayar).
5. Sunucuda çalışan servis varsa (web, veritabanı...) portlarını `hardening_ufw_extra_allow` ile aç; yoksa firewall onları kapatır.
6. Bakım penceresinde uygula. Otomatik reboot yoktur ama paket/servis değişiklikleri kısa kesinti yapabilir.
7. Kademeli git: ilk gün `--tags base,auth,kernel`, sonra `auditd,fail2ban,aide`, en son `ufw,ssh`.
8. Sonunda `audit.yml` ile tekrar ölç, sorun yoksa sıradaki sunucuya geç.

## 8. Bakım

- Değişiklik yaptıysan: `git add -A && git commit -m "..." && git push`
- Ayda bir: `audit.yml` çalıştır, skoru ve uyarıları karşılaştır.
- Bekleyen iş: CIS Ubuntu 26.04 Benchmark'ı için hazır Ansible rolü (`UBUNTU26-CIS`) ve OpenSCAP 26.04 içeriği çıkınca bizim rollerle karşılaştır (`docs/decisions.md` "BEKLEYEN").
- Test VM'deki `/etc/sudoers.d/90-ansible-test` (parolasız sudo) sadece test içindir; üretimde kullanma.
