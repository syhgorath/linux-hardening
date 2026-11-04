# Ubuntu: aday ek seçenekler

**Durum:** ADAY LİSTESİ, kod yok. Genel kurallar: [README](README.md). İşaret: `[ ]` karar bekliyor, `[x]` yap, `[-]` yapma, `[?]` konuşalım.

Ortam: Ubuntu 26.04 VM (sshpocket test VM'i). Debian'a da büyük ölçüde uyar.

## A. Sabit değerleri değişkene çevir (varsayılan aynı)

Bugün kodda sabit yazılı, kullanıcı değiştiremiyor. Varsayılanlar bugünkü değerdir; yani **hiçbir sunucuda davranış değişmez**. En güvenli ve en çok "komple özelleştirilebilir" kazandıran kategori.

| # | Aday değişken | Bugünkü sabit | Not |
|---|---|---|---|
| [ ] U-A1 | `hardening_ssh_max_auth_tries` | 3 | |
| [ ] U-A2 | `hardening_ssh_login_grace_time` | 60 | |
| [ ] U-A3 | `hardening_ssh_client_alive_interval`, `_count_max` | 300 / 2 | sshpocket oturum kopmalarını etkileyebilir; değer aralığı doğrulanır |
| [ ] U-A4 | `hardening_ssh_max_startups` | `10:30:60` | |
| [ ] U-A5 | `hardening_ssh_log_level` | `VERBOSE` | |
| [ ] U-A6 | `hardening_ssh_x11_forwarding`, `_agent_forwarding` | `no` / `no` | |
| [ ] U-A7 | `hardening_ssh_banner_path` | `/etc/issue.net` | |
| [ ] U-A8 | `hardening_ssh_macs` / `_ciphers` / `_kex` (boş = bugünkü liste ya da sunucu varsayılanı) | MACs sabit listesi var, cipher/kex yazılmıyor | Eski istemci uyumsuzluğu riski; `sshd -t` doğrulaması ve geri alma ağı içinde |
| [ ] U-A9 | `hardening_sudo_timestamp_timeout`, `hardening_sudo_use_pty` | 15 / true | |
| [ ] U-A10 | Tek tek sysctl: `hardening_sysctl_rp_filter`, `_log_martians`, `_ptrace_scope`, `_kptr_restrict`, `_dmesg_restrict`, `_suid_dumpable`, `_randomize_va_space` | şablonda sabit | Alternatif: tek `hardening_sysctl_overrides` sözlüğü (aşağıdaki soru) |
| [ ] U-A11 | `hardening_fail2ban_findtime`, `_banaction`, `_sshd_port` | şablonda sabit/varsayılan | `maxretry`, `bantime`, `ignoreip` zaten değişken |
| [ ] U-A12 | `hardening_ufw_default_incoming`, `_default_outgoing`, `_logging` | sabit | outgoing zaten `ufw_outgoing_deny` ile bool |
| [ ] U-A13 | `hardening_aide_check_time` (zamanlayıcı saati) | sabit | |
| [ ] U-A14 | `hardening_encrypt_method` | yazılmıyor (dağıtım varsayılanı) | Boş = dokunma |

**Açık soru (menü şişmesi):** 128 değişkene ~30 daha eklemek sshpocket menüsünü büyütür. İki yol: (1) her sabit için ayrı değişken (menüde görünür, gruplanır); (2) ortak "gelişmiş geçersiz kılma" sözlükleri (`hardening_sysctl_overrides`, `hardening_sshd_extra_options`) ve yalnız en önemli ~10 değer için ayrı değişken. Öneri: karma. Sözlük girdileri şemada doğrulanamayacağı için `sshd -t` ve sysctl anahtar adı denetimi gerekir.

## B. Yeni pasif seçenekler

| # | Aday | Ne yapar | Risk / koşul |
|---|---|---|---|
| [?] U-B1 | **GRUB parolası** (`hardening_grub_password_hash`, `_user`) | `grub-mkpasswd-pbkdf2` hash'i ile süper kullanıcı | **BULGU (2026-11-05, Ubuntu 26.04 test VM'inde salt okunur bakıldı):** `/etc/grub.d` altında `--unrestricted` ya da `GRUB_USERS` desteği YOK; `10_linux` menü girdilerini düz `CLASS="--class gnu-linux --class gnu --class os"` ile üretiyor. GRUB belgelerine göre `superusers` ayarlanınca `--unrestricted` olmayan girdiler yalnızca süper kullanıcıya açılır: yani NORMAL açılış da konsolda parola ister ve uzaktan yönetilen sunucu kendi kendine açılmaz (1.4.1 kararının nedeni buydu; `update-grub` ile DENENMEDİ). `--unrestricted` eklemek için `10_linux`'u (conffile) değiştirmek ya da `grub.cfg`'yi sonradan yamamak gerekir; ikisi de paket güncellemesinde bozulabilir. **Güvenli bir pasif uygulama bulunamadı, önerim: yapma ya da yalnızca "açılışta konsol parolası İSTENİR" uyarısıyla, BIOS+konsol erişimli VM'de denendikten sonra ekle.** Test VM'i BIOS (EFI değil). Geri alma ağı önyükleyiciyi KAPSAMAZ |
| [ ] U-B2 | **Kurum NTP sunucuları** (`hardening_chrony_servers`) | chrony kaynaklarını yazar (zaman bölümündeki "yetkili sunucu" kararının opt-in karşılığı) | Yanlış sunucu = saat kayar. Boş varsayılan |
| [ ] U-B3 | **Uzak günlük gönderimi** (`hardening_journal_remote_url`) | journald günlüğünü uzak alıcıya yollar | Alıcı sunucu gerekir (ikinci VM); DENENMEDİ |
| [ ] U-B4 | **APT kaynaklarını https'e çevir** (`hardening_apt_https_sources`) | Kaynak adreslerini https yapar | Vekil/kurum ağında kırar; paketler zaten imzalı. Uyarılı |
| [ ] U-B5 | **IP yönlendirmeyi kapat** (`hardening_ip_forward_off`) | `ip_forward=0` | Docker/LXD/konteyner/yönlendirici varsa kırar; preflight bunları algılayıp durmalı |
| [ ] U-B6 | **cron.allow / at.allow oluştur** (`hardening_cron_allow_users`) | Dosya yoksa listedeki kullanıcılarla oluşturur | Boş liste cron'u kapatırdı; liste zorunlu, boşsa yazılmaz |
| [ ] U-B7 | **unattended-upgrades ayrıntıları** (`hardening_unattended_auto_reboot`, `_reboot_time`, `_origins`) | Otomatik yeniden başlatma ve kaynaklar | Beklenmedik yeniden başlatma; uyarılı |
| [ ] U-B8 | **systemd servis sandbox drop-in'leri** (yönettiğimiz servisler için) | `ProtectClock`, `ProtectHostname`, `KeyringMode`, `RestrictNamespaces`, ... | Fazla sıkı ayar servisi kırar; **önce U-C1 ölçümü**, servis başına VM'de denenir |
| [ ] U-B9 | **/etc/profile.d umask** (`hardening_profile_umask`) | `login.defs` dışında kabuk dosyalarına da umask yazar | Web sunucusu içerik okuması etkilenir |
| [ ] U-B10 | **Ctrl+Alt+Del'i devre dışı bırak** (`hardening_disable_ctrl_alt_del`) | `ctrl-alt-del.target` birimini maskeler (sysctl `kernel.ctrl-alt-del` yalnızca tek başına yetmez: asıl karar systemd hedefindedir) | Sanal/fiziksel konsoldan Ctrl+Alt+Del ile yeniden başlatma çalışmaz; Proxmox konsolundan "Ctrl+Alt+Del gönder" işe yaramaz. Düşük risk, varsayılan pasif. DENENMEDİ |
| [ ] U-B11 | **auditd gürültülü olay dışlaması** (`hardening_auditd_exclude_msgtypes`, örn. `CWD`) | `-a exclude,always -F msgtype=...` kuralı kural setinin EN BAŞINA | İlk eşleşen kural kazanır, sıra önemli; denetim izini azaltır. Varsayılan boş. `auditd_cis_l2` ile birlikte düşünülmeli |

## C. Salt okunur rapor / ölçüm

| # | Aday | Ne yapar |
|---|---|---|
| [ ] U-C1 | **`systemd-analyze security` raporu** (`hardening_report`'a ek) | Servis sandbox puanlarını listeler (hangileri UNSAFE/EXPOSED). Davranış değiştirmez; sandbox işinden (U-B8) önce ölçüm verir |
| [ ] U-C2 | **CVE raporu (OVAL)** | Canonical'ın CVE tanımlarıyla açık CVE listesi. Hardening'den çok güncelleme izleme; öncelik düşük |
| [ ] U-C3 | **`hardening_rollback_timeout` alt sınırı** | Çok düşük timeout (arm→disarm penceresi ~30 sn) preflight'ta uyarı/hata. (Aday B/C değil, koruma; küçük) |
| [ ] U-C4 | **auditd durum raporu** | `auditctl -s`: `enabled`, `backlog_limit`, `lost`, `backlog`. `lost > 0` ise UYARI (olaylar kayboluyor; `hardening_auditd_backlog_limit` büyütülmeli), değilse NOT. Salt okunur; `-e 2` kilidi açıkken de okunur |
| [ ] U-C5 | **Kayma (drift) raporu** | `harden.yml --check` sonucunda `changed` olan görevlerin sayısı = ayarların amaçlanan durumdan sapması. Zaten `preview` eylemi bunu gösteriyor; periyodik/özet hâli aday |

## D. Tarama aracı

| # | Aday | Not |
|---|---|---|
| [ ] U-D1 | OpenSCAP'ı **salt okunur tarayıcı eylemi** olarak ekle; bulguları `bulgular.tsv` ile değişkene eşle | Ubuntu 26.04 için CIS içeriği bulunmuyor (bkz. README); içerik gelene kadar bekler |
| [ ] U-D2 | Mevcut `bulgular.tsv` eşlemesini genişlet: yeni değişkenler eklendikçe Lynis bulgularını onlara bağla | Seçenekler çoğaldıkça doğal sonuç |

## Bilerek aday olmayanlar

- **IPv6'yı kapatmak**, **PAM paketlerinin en güncel olması**, **`systemd-timesyncd`**, **rsyslog**: mevcut belgeli kararlar (`docs/cis-esleme.md`, ⏸️ bölümü).
- OpenSCAP'ın kendi **düzeltme (remediation)** betikleri: ayarlarımızla çakışır.
