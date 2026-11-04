# Ubuntu: aday ek seçenekler

**Durum:** ADAY LİSTESİ, kod yok. Genel kurallar: [README](README.md). İşaret: `[ ]` karar bekliyor, `[x]` yap, `[-]` yapma, `[?]` konuşalım.

Ortam: Ubuntu 26.04 VM (sshpocket test VM'i). Debian'a da büyük ölçüde uyar.

## A. Sabit değerleri değişkene çevir (varsayılan aynı)

Bugün kodda sabit yazılı, kullanıcı değiştiremiyor. Varsayılanlar bugünkü değerdir; yani **hiçbir sunucuda davranış değişmez**. En güvenli ve en çok "komple özelleştirilebilir" kazandıran kategori.

| # | Aday değişken | Bugünkü sabit | Not |
|---|---|---|---|
| [x] U-A1 (YAPILDI) | `hardening_ssh_max_auth_tries` | 3 | |
| [x] U-A2 (YAPILDI) | `hardening_ssh_login_grace_time` | 60 | |
| [x] U-A3 (YAPILDI) | `hardening_ssh_client_alive_interval`, `_count_max` | 300 / 2 | sshpocket oturum kopmalarını etkileyebilir; değer aralığı doğrulanır |
| [x] U-A4 (YAPILDI) | `hardening_ssh_max_startups` | `10:30:60` | |
| [x] U-A5 (YAPILDI) | `hardening_ssh_log_level` | `VERBOSE` | |
| [x] U-A6 (YAPILDI) | `hardening_ssh_x11_forwarding`, `_agent_forwarding` | `no` / `no` | |
| [ ] U-A7 | `hardening_ssh_banner_path` | `/etc/issue.net` | |
| [ ] U-A8 | `hardening_ssh_macs` / `_ciphers` / `_kex` (boş = bugünkü liste ya da sunucu varsayılanı) | MACs sabit listesi var, cipher/kex yazılmıyor | Eski istemci uyumsuzluğu riski; `sshd -t` doğrulaması ve geri alma ağı içinde |
| [x] U-A9 (YAPILDI) | `hardening_sudo_timestamp_timeout`, `hardening_sudo_use_pty` | 15 / true | |
| [ ] U-A10 | Tek tek sysctl: `hardening_sysctl_rp_filter`, `_log_martians`, `_ptrace_scope`, `_kptr_restrict`, `_dmesg_restrict`, `_suid_dumpable`, `_randomize_va_space` | şablonda sabit | Alternatif: tek `hardening_sysctl_overrides` sözlüğü (aşağıdaki soru) |
| [ ] U-A11 | `hardening_fail2ban_findtime`, `_banaction`, `_sshd_port` | şablonda sabit/varsayılan | `maxretry`, `bantime`, `ignoreip` zaten değişken |
| [ ] U-A12 | `hardening_ufw_default_incoming`, `_default_outgoing`, `_logging` | sabit | outgoing zaten `ufw_outgoing_deny` ile bool |
| [ ] U-A13 | `hardening_aide_check_time` (zamanlayıcı saati) | sabit | |
| [ ] U-A14 | `hardening_encrypt_method` | yazılmıyor (dağıtım varsayılanı) | Boş = dokunma |

**Açık soru (menü şişmesi):** 128 değişkene ~30 daha eklemek sshpocket menüsünü büyütür. İki yol: (1) her sabit için ayrı değişken (menüde görünür, gruplanır); (2) ortak "gelişmiş geçersiz kılma" sözlükleri (`hardening_sysctl_overrides`, `hardening_sshd_extra_options`) ve yalnız en önemli ~10 değer için ayrı değişken. Öneri: karma. Sözlük girdileri şemada doğrulanamayacağı için `sshd -t` ve sysctl anahtar adı denetimi gerekir.

## B. Yeni pasif seçenekler

| # | Aday | Ne yapar | Risk / koşul |
|---|---|---|---|
| [ ] U-B1 | **GRUB parolası** (`hardening_grub_password_hash`, `_user`) | `grub-mkpasswd-pbkdf2` hash'i ile süper kullanıcı; normal açılış girdileri kilitsiz (`--unrestricted`), yalnız menü düzenleme/komut satırı korunur | **Varsayılan pasif**, kullanıcı açar. Geri alma ağı önyükleyiciyi KAPSAMAZ; yanlış yazım önyüklemeyi bozabilir, konsolla ve yeniden başlatarak denenmeli. README ve known-issues'ta **DENENMEDİ**. GRUB yoksa (`/etc/default/grub` yok) atlanır. Düz parola değişkene girmez |
| [ ] U-B2 | **Kurum NTP sunucuları** (`hardening_chrony_servers`) | chrony kaynaklarını yazar (zaman bölümündeki "yetkili sunucu" kararının opt-in karşılığı) | Yanlış sunucu = saat kayar. Boş varsayılan |
| [ ] U-B3 | **Uzak günlük gönderimi** (`hardening_journal_remote_url`) | journald günlüğünü uzak alıcıya yollar | Alıcı sunucu gerekir (ikinci VM); DENENMEDİ |
| [ ] U-B4 | **APT kaynaklarını https'e çevir** (`hardening_apt_https_sources`) | Kaynak adreslerini https yapar | Vekil/kurum ağında kırar; paketler zaten imzalı. Uyarılı |
| [ ] U-B5 | **IP yönlendirmeyi kapat** (`hardening_ip_forward_off`) | `ip_forward=0` | Docker/LXD/konteyner/yönlendirici varsa kırar; preflight bunları algılayıp durmalı |
| [ ] U-B6 | **cron.allow / at.allow oluştur** (`hardening_cron_allow_users`) | Dosya yoksa listedeki kullanıcılarla oluşturur | Boş liste cron'u kapatırdı; liste zorunlu, boşsa yazılmaz |
| [ ] U-B7 | **unattended-upgrades ayrıntıları** (`hardening_unattended_auto_reboot`, `_reboot_time`, `_origins`) | Otomatik yeniden başlatma ve kaynaklar | Beklenmedik yeniden başlatma; uyarılı |
| [ ] U-B8 | **systemd servis sandbox drop-in'leri** (yönettiğimiz servisler için) | `ProtectClock`, `ProtectHostname`, `KeyringMode`, `RestrictNamespaces`, ... | Fazla sıkı ayar servisi kırar; **önce U-C1 ölçümü**, servis başına VM'de denenir |
| [ ] U-B9 | **/etc/profile.d umask** (`hardening_profile_umask`) | `login.defs` dışında kabuk dosyalarına da umask yazar | Web sunucusu içerik okuması etkilenir |

## C. Salt okunur rapor / ölçüm

| # | Aday | Ne yapar |
|---|---|---|
| [ ] U-C1 | **`systemd-analyze security` raporu** (`hardening_report`'a ek) | Servis sandbox puanlarını listeler (hangileri UNSAFE/EXPOSED). Davranış değiştirmez; sandbox işinden (U-B8) önce ölçüm verir |
| [ ] U-C2 | **CVE raporu (OVAL)** | Canonical'ın CVE tanımlarıyla açık CVE listesi. Hardening'den çok güncelleme izleme; öncelik düşük |
| [ ] U-C3 | **`hardening_rollback_timeout` alt sınırı** | Çok düşük timeout (arm→disarm penceresi ~30 sn) preflight'ta uyarı/hata. (Aday B/C değil, koruma; küçük) |

## D. Tarama aracı

| # | Aday | Not |
|---|---|---|
| [ ] U-D1 | OpenSCAP'ı **salt okunur tarayıcı eylemi** olarak ekle; bulguları `bulgular.tsv` ile değişkene eşle | Ubuntu 26.04 için CIS içeriği bulunmuyor (bkz. README); içerik gelene kadar bekler |
| [ ] U-D2 | Mevcut `bulgular.tsv` eşlemesini genişlet: yeni değişkenler eklendikçe Lynis bulgularını onlara bağla | Seçenekler çoğaldıkça doğal sonuç |

## Bilerek aday olmayanlar

- **IPv6'yı kapatmak**, **PAM paketlerinin en güncel olması**, **`systemd-timesyncd`**, **rsyslog**: mevcut belgeli kararlar (`docs/cis-esleme.md`, ⏸️ bölümü).
- OpenSCAP'ın kendi **düzeltme (remediation)** betikleri: ayarlarımızla çakışır.
