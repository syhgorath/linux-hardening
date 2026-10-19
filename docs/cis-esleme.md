# CIS Ubuntu Linux 26.04 LTS Benchmark eşlemesi (taslak)

Bu belge, projenin yaptıklarını **CIS Ubuntu Linux 26.04 LTS Benchmark v1.0.0** (08-26-2026) madde numaralarıyla eşler. Amaç iddia değil **boşlukları görmek**: proje tam CIS uyumu iddia etmez (bkz. [README](../README.md#ne-yapmaz-kapsam-sınırları)).

> **Telif:** CIS Benchmark metni bu depoda barındırılmaz ve aktarılmaz. Burada yalnızca madde **numaraları** ve kendi sözlerimizle kısa açıklamalar var. PDF'i [CIS'ten](https://www.cisecurity.org/cis-benchmarks) indirin; madde numarasından karşılık bulabilirsiniz.

## Nasıl okunur

- **Kapsam:** yalnızca **Level 1 - Server** profili ve **274 madde**. (Level 2 - Server ayrıca 76 madde; bu belgede ayrıca işlenmedi.) Sayılar PDF'ten betikle çıkarıldı, tek tek elle sayılmadı.

- ✅ **Karşılıyor:** ayar kodda var ve değeri benchmark'ın beklediğiyle **elle karşılaştırıldı** (sysctl, SSH, pwquality değerleri PDF'in beklediği değerlerle).
- 🟡 **Kısmen:** ilgili ayar var ama maddenin tamamını kapsamıyor (neden satırda yazılı).
- ⏸️ **Bilerek yok:** belgeli karar.
- ⚪ **Varsayılan uygun:** kodumuz bir şey yapmıyor ama **test VM'inde** Ubuntu varsayılanı maddeyi karşılıyor (aşağıda ölçüm yöntemi). Başka sunucuda böyle olmayabilir; garanti değil.
- ❌ **Yok:** kodda karşılığı yok. Sunucuda dağıtım varsayılanı zaten uygun olabilir; **denetlemiyor ve garanti etmiyoruz**.

- **Ölçülmedi:** CIS-CAT, OpenSCAP veya benzeri bir araçla tarama yapılmadı; bu tablo **koddan okuyarak** çıkarıldı. Kodda ayar olması, çalışan sunucuda uygulandığının kanıtı değildir (kanıtlar için [verification-log.md](verification-log.md)).

## Özet

| Bölüm | Konu | Level 1 madde | ✅ | 🟡 | ⏸️ | ⚪ | ❌ |
|---|---|---:|---:|---:|---:|---:|---:|
| 1.1 | Dosya sistemi (modüller, bölümler, bağlama seçenekleri) | 29 | 7 |  |  | 19 | 3 |
| 1.2 | Paket yönetimi (APT depoları, güncellemeler) | 15 | 4 | 1 |  | 8 | 2 |
| 1.3 | AppArmor | 3 |  |  |  | 3 |  |
| 1.4 | Önyükleyici | 2 |  | 1 |  |  | 1 |
| 1.5 | Süreç sertleştirme (sysctl, core dump) | 11 | 7 | 3 |  | 1 |  |
| 1.6 | Oturum açma uyarı metinleri | 12 | 8 |  |  | 2 | 2 |
| 1.7 | GNOME oturum yöneticisi (masaüstü) | 6 |  |  |  | 6 |  |
| 2.1 | Sunucu servisleri | 22 |  | 1 |  | 20 | 1 |
| 2.2 | İstemci paketleri | 6 |  | 2 |  | 4 |  |
| 2.3 | Zaman senkronizasyonu | 6 |  |  |  | 3 | 3 |
| 2.4 | Zamanlanmış işler (cron, at) | 10 | 7 | 2 |  | 1 |  |
| 3.1 | Ağ aygıtları (IPv6, kablosuz, bluetooth) | 3 |  |  |  | 2 | 1 |
| 3.2 | Ağ çekirdek modülleri | 7 | 6 |  |  |  | 1 |
| 3.3 | Ağ çekirdek parametreleri | 27 | 20 | 2 | 5 |  |  |
| 4.1 | Güvenlik duvarı (ufw) | 4 | 4 |  |  |  |  |
| 5.1 | SSH sunucusu | 24 | 20 | 3 |  |  | 1 |
| 5.2 | Yetki yükseltme (sudo, su) | 6 | 2 | 3 |  | 1 |  |
| 5.3 | PAM (parola kalitesi, kilitleme, geçmiş) | 25 | 4 | 3 |  | 2 | 16 |
| 5.4 | Kullanıcı hesapları ve ortamı | 15 |  | 6 |  | 7 | 2 |
| 6.1 | Günlük kaydı (journald, rsyslog, logrotate) | 15 | 2 | 1 |  | 9 | 3 |
| 6.3 | Bütünlük denetimi (AIDE) | 2 | 2 |  |  |  |  |
| 7.1 | Sistem dosyası izinleri | 13 | 10 | 1 |  | 2 |  |
| 7.2 | Yerel kullanıcı ve grup ayarları | 11 |  |  |  | 10 | 1 |
| | **Toplam** | **274** | **103** | **29** | **5** | **100** | **37** |

Yani Level 1 Server maddelerinin yaklaşık %38'i ✅, %48'i en azından kısmen karşılanıyor. Bu, **uyumluluk yüzdesi değildir**: ölçülmedi, maddeler eşit ağırlıkta değil.

## Karşılananlar (✅)

| Madde | Ne | Nerede |
|---|---|---|
| 1.1.1.1 | cramfs, freevxfs, hfs, hfsplus, jffs2, firewire-core modülleri kapalı (zaten yüklüyse kaldırılmaz) | `roles/hardening_kernel/tasks/main.yml` |
| 1.1.1.2 | cramfs, freevxfs, hfs, hfsplus, jffs2, firewire-core modülleri kapalı (zaten yüklüyse kaldırılmaz) | `roles/hardening_kernel/tasks/main.yml` |
| 1.1.1.3 | cramfs, freevxfs, hfs, hfsplus, jffs2, firewire-core modülleri kapalı (zaten yüklüyse kaldırılmaz) | `roles/hardening_kernel/tasks/main.yml` |
| 1.1.1.4 | cramfs, freevxfs, hfs, hfsplus, jffs2, firewire-core modülleri kapalı (zaten yüklüyse kaldırılmaz) | `roles/hardening_kernel/tasks/main.yml` |
| 1.1.1.5 | cramfs, freevxfs, hfs, hfsplus, jffs2, firewire-core modülleri kapalı (zaten yüklüyse kaldırılmaz) | `roles/hardening_kernel/tasks/main.yml` |
| 1.1.1.9 | cramfs, freevxfs, hfs, hfsplus, jffs2, firewire-core modülleri kapalı (zaten yüklüyse kaldırılmaz) | `roles/hardening_kernel/tasks/main.yml` |
| 1.1.1.10 | usb-storage modülü kapalı | `roles/hardening_base/tasks/main.yml` |
| 1.2.1.3 | APT anahtarları (.gpg), auth.conf.d / sources.list.d dizinleri ve kaynak dosyaları: yalnızca fazla izin kaldırılır | `roles/hardening_files/tasks/main.yml` |
| 1.2.1.5 | APT anahtarları (.gpg), auth.conf.d / sources.list.d dizinleri ve kaynak dosyaları: yalnızca fazla izin kaldırılır | `roles/hardening_files/tasks/main.yml` |
| 1.2.1.8 | APT anahtarları (.gpg), auth.conf.d / sources.list.d dizinleri ve kaynak dosyaları: yalnızca fazla izin kaldırılır | `roles/hardening_files/tasks/main.yml` |
| 1.2.1.9 | APT anahtarları (.gpg), auth.conf.d / sources.list.d dizinleri ve kaynak dosyaları: yalnızca fazla izin kaldırılır | `roles/hardening_files/tasks/main.yml` |
| 1.5.1 | fs.protected_hardlinks = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 1.5.3 | kernel.yama.ptrace_scope = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 1.5.4 | fs.suid_dumpable = 0 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 1.5.5 | kernel.dmesg_restrict = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 1.5.7 | apport kapatılır (enabled=0, servis durdurulup maskelenir) | `roles/hardening_base/tasks/main.yml` |
| 1.5.8 | kernel.kptr_restrict = 2 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 1.5.9 | kernel.randomize_va_space = 2 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 1.6.2 | /etc/issue ve /etc/issue.net: işletim sistemi bilgisi içermeyen uyarı metni | `roles/hardening_base/tasks/main.yml` |
| 1.6.3 | /etc/issue ve /etc/issue.net: işletim sistemi bilgisi içermeyen uyarı metni | `roles/hardening_base/tasks/main.yml` |
| 1.6.5 | sshd Banner /etc/issue.net | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 1.6.6 | /etc/motd izin/sahibi (dosya varsa) | `roles/hardening_files/defaults/main.yml` |
| 1.6.7 | banner dosyaları root:root 0644 | `roles/hardening_base/tasks/main.yml` |
| 1.6.8 | banner dosyaları root:root 0644 | `roles/hardening_base/tasks/main.yml` |
| 1.6.10 | banner dosyaları root:root 0644 | `roles/hardening_base/tasks/main.yml` |
| 1.6.12 | update-notifier-motd zamanlayıcısı maskelenir | `roles/hardening_base/tasks/main.yml` |
| 2.4.1.2 | crontab ve cron dizinleri og-rwx root:root (cron kurulu değilse atlanır) | `roles/hardening_files/defaults/main.yml` |
| 2.4.1.3 | crontab ve cron dizinleri og-rwx root:root (cron kurulu değilse atlanır) | `roles/hardening_files/defaults/main.yml` |
| 2.4.1.4 | crontab ve cron dizinleri og-rwx root:root (cron kurulu değilse atlanır) | `roles/hardening_files/defaults/main.yml` |
| 2.4.1.5 | crontab ve cron dizinleri og-rwx root:root (cron kurulu değilse atlanır) | `roles/hardening_files/defaults/main.yml` |
| 2.4.1.6 | crontab ve cron dizinleri og-rwx root:root (cron kurulu değilse atlanır) | `roles/hardening_files/defaults/main.yml` |
| 2.4.1.7 | crontab ve cron dizinleri og-rwx root:root (cron kurulu değilse atlanır) | `roles/hardening_files/defaults/main.yml` |
| 2.4.1.8 | crontab ve cron dizinleri og-rwx root:root (cron kurulu değilse atlanır) | `roles/hardening_files/defaults/main.yml` |
| 3.2.1 | atm ve can modülleri kapalı (zaten yüklüyse kaldırılmaz) | `roles/hardening_kernel/tasks/main.yml` |
| 3.2.2 | atm ve can modülleri kapalı (zaten yüklüyse kaldırılmaz) | `roles/hardening_kernel/tasks/main.yml` |
| 3.2.3 | dccp, rds, sctp, tipc modülleri kapalı | `roles/hardening_kernel/tasks/main.yml` |
| 3.2.4 | dccp, rds, sctp, tipc modülleri kapalı | `roles/hardening_kernel/tasks/main.yml` |
| 3.2.5 | dccp, rds, sctp, tipc modülleri kapalı | `roles/hardening_kernel/tasks/main.yml` |
| 3.2.6 | dccp, rds, sctp, tipc modülleri kapalı | `roles/hardening_kernel/tasks/main.yml` |
| 3.3.1.4 | send_redirects = 0 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.5 | send_redirects = 0 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.6 | icmp_ignore_bogus_error_responses = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.7 | icmp_echo_ignore_broadcasts = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.8 | accept_redirects = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.9 | accept_redirects = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.10 | secure_redirects = 0 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.11 | secure_redirects = 0 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.12 | rp_filter = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.13 | rp_filter = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.14 | accept_source_route = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.15 | accept_source_route = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.16 | log_martians = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.17 | log_martians = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.18 | tcp_syncookies = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.19 | route_localnet = 0 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.2.3 | accept_redirects = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.2.4 | accept_redirects = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.2.5 | accept_source_route = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.2.6 | accept_source_route = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 4.1.1 | ufw kurulur | `roles/hardening_ufw/tasks/main.yml` |
| 4.1.2 | ufw etkinleştirilir | `roles/hardening_ufw/tasks/main.yml` |
| 4.1.3 | gelen varsayılan: deny | `roles/hardening_ufw/tasks/main.yml` |
| 4.1.5 | routed varsayılanı: deny (hardening_ufw_routed_deny, varsayılan true) | `roles/hardening_ufw/tasks/main.yml` |
| 5.1.1 | sshd_config(.d), drop-in .conf dosyaları ve ana bilgisayar anahtarlarının izin/sahibi (yalnızca fazla izni kaldırır) | `roles/hardening_files/tasks/main.yml` |
| 5.1.2 | sshd_config(.d), drop-in .conf dosyaları ve ana bilgisayar anahtarlarının izin/sahibi (yalnızca fazla izni kaldırır) | `roles/hardening_files/tasks/main.yml` |
| 5.1.3 | sshd_config(.d), drop-in .conf dosyaları ve ana bilgisayar anahtarlarının izin/sahibi (yalnızca fazla izni kaldırır) | `roles/hardening_files/tasks/main.yml` |
| 5.1.4 | sshd_config(.d), drop-in .conf dosyaları ve ana bilgisayar anahtarlarının izin/sahibi (yalnızca fazla izni kaldırır) | `roles/hardening_files/tasks/main.yml` |
| 5.1.6 | Banner /etc/issue.net | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.8 | ClientAliveInterval 300, ClientAliveCountMax 2 (ikisi de sıfırdan büyük) | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.9 | DisableForwarding yes (yalnızca AllowTcpForwarding=no iken; değişkenle local/remote seçilirse yazılmaz) | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.10 | GSSAPIAuthentication no | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.11 | HostbasedAuthentication no | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.12 | IgnoreRhosts yes | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.15 | LoginGraceTime 60 | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.16 | LogLevel VERBOSE | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.17 | MACs: zayıf listesi çıkarılır (umac-64, umac-64-etm, umac-128-etm, sha1-96, md5, ripemd160) | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.18 | MaxAuthTries 3 (en çok 4 isteniyor) | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.19 | MaxSessions 4 (en çok 10 isteniyor) | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.20 | MaxStartups 10:30:60 | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.21 | PermitEmptyPasswords no | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.22 | PermitRootLogin no | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.23 | PermitUserEnvironment no | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.24 | UsePAM yes | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.2.2 | sudoers.d/60-hardening: use_pty, timestamp_timeout=15 (visudo ile doğrulanır) | `roles/hardening_sudo/tasks/main.yml` |
| 5.2.6 | sudoers.d/60-hardening: use_pty, timestamp_timeout=15 (visudo ile doğrulanır) | `roles/hardening_sudo/tasks/main.yml` |
| 5.3.3.2.2 | minlen 14 | `roles/hardening_auth/templates/pwquality.conf.j2` |
| 5.3.3.2.3 | minclass 3 | `roles/hardening_auth/templates/pwquality.conf.j2` |
| 5.3.3.2.4 | maxrepeat 3 | `roles/hardening_auth/templates/pwquality.conf.j2` |
| 5.3.3.2.6 | dictcheck 1 | `roles/hardening_auth/templates/pwquality.conf.j2` |
| 6.1.1.1.6 | journald drop-in: Storage=persistent, Compress=yes | `roles/hardening_base/tasks/main.yml` |
| 6.1.1.1.7 | journald drop-in: Storage=persistent, Compress=yes | `roles/hardening_base/tasks/main.yml` |
| 6.3.1 | AIDE kurulur, veritabanı üretilir | `roles/hardening_aide/tasks/main.yml` |
| 6.3.2 | Günlük AIDE kontrol zamanlayıcısı (`dailyaidecheck.timer`) açık ve başlatılmış | `roles/hardening_aide/tasks/main.yml` |
| 7.1.1 | passwd/group/shadow/gshadow (+ yedekleri), shells, opasswd izinleri (var olanlar; yalnızca fazla izni kaldırır) | `roles/hardening_files/defaults/main.yml` |
| 7.1.2 | passwd/group/shadow/gshadow (+ yedekleri), shells, opasswd izinleri (var olanlar; yalnızca fazla izni kaldırır) | `roles/hardening_files/defaults/main.yml` |
| 7.1.3 | passwd/group/shadow/gshadow (+ yedekleri), shells, opasswd izinleri (var olanlar; yalnızca fazla izni kaldırır) | `roles/hardening_files/defaults/main.yml` |
| 7.1.4 | passwd/group/shadow/gshadow (+ yedekleri), shells, opasswd izinleri (var olanlar; yalnızca fazla izni kaldırır) | `roles/hardening_files/defaults/main.yml` |
| 7.1.5 | passwd/group/shadow/gshadow (+ yedekleri), shells, opasswd izinleri (var olanlar; yalnızca fazla izni kaldırır) | `roles/hardening_files/defaults/main.yml` |
| 7.1.6 | passwd/group/shadow/gshadow (+ yedekleri), shells, opasswd izinleri (var olanlar; yalnızca fazla izni kaldırır) | `roles/hardening_files/defaults/main.yml` |
| 7.1.7 | passwd/group/shadow/gshadow (+ yedekleri), shells, opasswd izinleri (var olanlar; yalnızca fazla izni kaldırır) | `roles/hardening_files/defaults/main.yml` |
| 7.1.8 | passwd/group/shadow/gshadow (+ yedekleri), shells, opasswd izinleri (var olanlar; yalnızca fazla izni kaldırır) | `roles/hardening_files/defaults/main.yml` |
| 7.1.9 | passwd/group/shadow/gshadow (+ yedekleri), shells, opasswd izinleri (var olanlar; yalnızca fazla izni kaldırır) | `roles/hardening_files/defaults/main.yml` |
| 7.1.10 | passwd/group/shadow/gshadow (+ yedekleri), shells, opasswd izinleri (var olanlar; yalnızca fazla izni kaldırır) | `roles/hardening_files/defaults/main.yml` |

## Kısmen karşılananlar (🟡)

| Madde | Durum |
|---|---|
| 1.2.2.1 | Güvenlik güncellemeleri otomatik (unattended-upgrades); 'tüm güncellemeler kurulu' denetlenmez |
| 1.4.2 | grub.cfg 0600 root:root yapılır; update-grub dosyayı yeniden yazarsa 0444'e dönebilir (sonraki çalıştırmada yeniden sıkılaşır, doğrulanmadı) |
| 1.5.10 | kod var (hardening_disable_coredump) ama varsayılan KAPALI; çökme dökümünü kapatır |
| 1.5.11 | kod var (hardening_disable_coredump) ama varsayılan KAPALI; çökme dökümünü kapatır |
| 1.5.12 | kod var (hardening_disable_coredump) ama varsayılan KAPALI; çökme dökümünü kapatır |
| 2.1.22 | postfix/courier kaldırılır, dinlemeyen `dma` kurulur; belirli bir MTA'nın yalnız-yerel ayarı denetlenmez |
| 2.2.4 | kod var (hardening_remove_legacy_clients) ama varsayılan KAPALI; telnet/ftp istemcilerini kaldırır |
| 2.2.6 | kod var (hardening_remove_legacy_clients) ama varsayılan KAPALI; telnet/ftp istemcilerini kaldırır |
| 2.4.1.9 | cron.allow/at.allow izinleri yalnızca dosya VARSA sıkılaştırılır; OLUŞTURULMAZ (boş cron.allow crontab kullanımını kapatırdı) |
| 2.4.2.1 | cron.allow/at.allow izinleri yalnızca dosya VARSA sıkılaştırılır; OLUŞTURULMAZ (boş cron.allow crontab kullanımını kapatırdı) |
| 3.3.2.7 | `accept_ra = 0` yalnızca `hardening_kernel_disable_ipv6_ra=true` ile (varsayılan kapalı: RA ile IPv6 alan sunucu bağlantıyı kaybeder) |
| 3.3.2.8 | `accept_ra = 0` yalnızca `hardening_kernel_disable_ipv6_ra=true` ile (varsayılan kapalı: RA ile IPv6 alan sunucu bağlantıyı kaybeder) |
| 5.1.7 | kodda yazılmıyor; test VM'inde (OpenSSH 10.2) `sshd -T` varsayılanı zaten uygun (zayıf şifre/KEX yok; sntrup761x25519 ve mlkem768x25519 var). Varsayılan değişirse garanti yok |
| 5.1.13 | kodda yazılmıyor; test VM'inde (OpenSSH 10.2) `sshd -T` varsayılanı zaten uygun (zayıf şifre/KEX yok; sntrup761x25519 ve mlkem768x25519 var). Varsayılan değişirse garanti yok |
| 5.1.14 | kodda yazılmıyor; test VM'inde (OpenSSH 10.2) `sshd -T` varsayılanı zaten uygun (zayıf şifre/KEX yok; sntrup761x25519 ve mlkem768x25519 var). Varsayılan değişirse garanti yok |
| 5.2.3 | sudo-rs (26.04 varsayılanı) `logfile` desteklemez; olaylar varsayılan olarak journald'e gider (CIS yöntem A) ama kodla garanti/yapılandırma yok. Klasik sudo'da `logfile` yazılır |
| 5.2.7 | `su` kısıtı yalnızca `hardening_su_restrict=true` ile (varsayılan kapalı: kök olmayan hesapla `su` kullanan betik/insan bozulur); `pam_wheel` + varsayılan boş `sugroup` |
| 5.2.5 | sudoers'ta `!authenticate` varsa yalnızca UYARIR, değiştirmez |
| 5.3.1.3 | libpam-pwquality kurulur; 'son sürüm' denetlenmez |
| 5.3.2.3 | paket kurulur ve pwquality.conf yazılır; pam-configs'te etkin olduğu doğrulanmadı |
| 5.3.3.2.7 | `enforcing = 1` yazılır; pam-configs'te `enforcing=0` kalmadığı denetlenmez |
| 5.4.1.1 | `PASS_MAX_DAYS 365` login.defs'te; yalnız yeni hesapları etkiler, mevcut kullanıcılara dokunulmaz |
| 5.4.1.3 | `PASS_WARN_AGE 7` login.defs'te; yalnız yeni hesaplar |
| 5.4.1.4 | `SHA_CRYPT_*_ROUNDS` yazılır; `ENCRYPT_METHOD` yazılmaz (dağıtım varsayılanına bırakıldı) |
| 5.4.1.5 | kod var (hardening_password_inactive_days) ama varsayılan KAPALI ve yalnız YENİ hesaplar için |
| 5.4.3.2 | kod var (hardening_shell_timeout_seconds) ama varsayılan 0 = KAPALI |
| 5.4.3.3 | `UMASK 027` login.defs'te; /etc/profile.d ve bashrc dosyalarına dokunulmaz |
| 6.1.3.1 | kod var (hardening_log_file_permissions) ama varsayılan KAPALI; wtmp/btmp/lastlog/faillog ve journal hariç |
| 7.1.13 | SUID/SGID dosyaları listelenir (salt okunur özet, hardening_suid_report); inceleme insana kalır, değişiklik yok |

## Bilerek yapılmayanlar (⏸️)

| Madde | Neden |
|---|---|
| 3.3.1.1 | ip_forward'a bilerek dokunulmaz (LXD/konteyner/yönlendirici kullanımı) |
| 3.3.1.2 | ip_forward'a bilerek dokunulmaz |
| 3.3.1.3 | ip_forward'a bilerek dokunulmaz |
| 3.3.2.1 | ip_forward'a bilerek dokunulmaz |
| 3.3.2.2 | ip_forward'a bilerek dokunulmaz |

## Varsayılan uygun (⚪), test VM'inde ölçüldü

**Ölçüm yöntemi (CIS-CAT değil):** 2026-10-18'de test VM'inde (Ubuntu 26.04, bu projenin rolleri uygulanmış) her madde için CIS denetim metninin **yaklaşığı** salt okunur bir kabuk betiğiyle çalıştırıldı (`sysctl`, `systemctl`, `dpkg-query`, `findmnt`, `find` vb.; hiçbir şey değiştirilmedi). Betik depoda **yok**; sonuçlar yaklaşıktır, resmî uyumluluk kanıtı değildir. Bu satırlar kodumuzun bir şey yaptığı anlamına gelmez; yalnızca o makinede varsayılanın uygun çıktığını söyler.

| Bölüm | Konu | Madde numaraları |
|---|---|---|
| 1.1 | Dosya sistemi (modüller, bölümler, bağlama seçenekleri) | 1.1.2.1.1, 1.1.2.1.2, 1.1.2.1.3, 1.1.2.2.1, 1.1.2.2.2, 1.1.2.2.3, 1.1.2.3.2, 1.1.2.3.3, 1.1.2.4.2, 1.1.2.4.3, 1.1.2.5.2, 1.1.2.5.3, 1.1.2.5.4, 1.1.2.6.2, 1.1.2.6.3, 1.1.2.6.4, 1.1.2.7.2, 1.1.2.7.3, 1.1.2.7.4 |
| 1.2 | Paket yönetimi (APT depoları, güncellemeler) | 1.2.1.1, 1.2.1.4, 1.2.1.7, 1.2.1.10, 1.2.1.12, 1.2.1.13, 1.2.1.14, 1.2.1.15 |
| 1.3 | AppArmor | 1.3.1.1, 1.3.1.2, 1.3.1.4 |
| 1.5 | Süreç sertleştirme (sysctl, core dump) | 1.5.6 |
| 1.6 | Oturum açma uyarı metinleri | 1.6.1, 1.6.11 |
| 1.7 | GNOME oturum yöneticisi (masaüstü) | 1.7.1, 1.7.2, 1.7.3, 1.7.4, 1.7.5, 1.7.6 |
| 2.1 | Sunucu servisleri | 2.1.1, 2.1.2, 2.1.3, 2.1.4, 2.1.5, 2.1.6, 2.1.7, 2.1.8, 2.1.9, 2.1.10, 2.1.11, 2.1.12, 2.1.13, 2.1.14, 2.1.15, 2.1.16, 2.1.17, 2.1.18, 2.1.19, 2.1.20 |
| 2.2 | İstemci paketleri | 2.2.1, 2.2.2, 2.2.3, 2.2.5 |
| 2.3 | Zaman senkronizasyonu | 2.3.1.1, 2.3.3.2, 2.3.3.3 |
| 2.4 | Zamanlanmış işler (cron, at) | 2.4.1.1 |
| 3.1 | Ağ aygıtları (IPv6, kablosuz, bluetooth) | 3.1.2, 3.1.3 |
| 5.2 | Yetki yükseltme (sudo, su) | 5.2.1 |
| 5.3 | PAM (parola kalitesi, kilitleme, geçmiş) | 5.3.2.1, 5.3.3.4.3 |
| 5.4 | Kullanıcı hesapları ve ortamı | 5.4.1.6, 5.4.2.1, 5.4.2.2, 5.4.2.3, 5.4.2.4, 5.4.2.7, 5.4.2.8 |
| 6.1 | Günlük kaydı (journald, rsyslog, logrotate) | 6.1.1.1.1, 6.1.1.1.2, 6.1.1.1.3, 6.1.1.1.4, 6.1.2.1, 6.1.2.2, 6.1.2.3, 6.1.2.6, 6.1.2.7 |
| 7.1 | Sistem dosyası izinleri | 7.1.11, 7.1.12 |
| 7.2 | Yerel kullanıcı ve grup ayarları | 7.2.1, 7.2.2, 7.2.3, 7.2.4, 7.2.5, 7.2.6, 7.2.7, 7.2.8, 7.2.9, 7.2.10 |

**VM'de uygun ÇIKMAYAN** (bu yüzden ❌ kaldı) ve kodla çözülebilecek olanlar: `/tmp` ve `/dev/shm` için `noexec` (1.1.2.x), `apport` etkin (1.5.7), core dump sınırı ve `systemd-coredump` ayarı (1.5.10-12), `update-notifier-motd.timer` etkin (1.6.12), `telnet`, `ftp`/`tnftp` istemcileri **kurulu** (2.2.4, 2.2.6), `pam_unix` `nullok` (5.3.3.4.1), `INACTIVE` (5.4.1.5), kabuk `TMOUT` (5.4.3.2), journald `Storage`/`Compress` açıkça yazılı değil (6.1.1.1.6/7), `sysstat` günlükleri herkesçe okunabilir (6.1.3.1). Bu envanter VM'e özgüdür.


## Yok (❌), konuya göre

Her satır, o bölümde ✅/🟡/⏸️ **olmayan** Level 1 maddeleridir (numaralar yalnız konu gruplamak içindir).

| Bölüm | Konu | Madde numaraları |
|---|---|---|
| 1.1 | Dosya sistemi (modüller, bölümler, bağlama seçenekleri) | 1.1.1.11, 1.1.2.1.4, 1.1.2.2.4 |
| 1.2 | Paket yönetimi (APT depoları, güncellemeler) | 1.2.1.6, 1.2.1.11 |
| 1.4 | Önyükleyici | 1.4.1 |
| 1.6 | Oturum açma uyarı metinleri | 1.6.4, 1.6.9 |
| 2.1 | Sunucu servisleri | 2.1.23 |
| 2.3 | Zaman senkronizasyonu | 2.3.2.1, 2.3.2.2, 2.3.3.1 |
| 3.1 | Ağ aygıtları (IPv6, kablosuz, bluetooth) | 3.1.1 |
| 3.2 | Ağ çekirdek modülleri | 3.2.7 |
| 5.1 | SSH sunucusu | 5.1.5 |
| 5.3 | PAM (parola kalitesi, kilitleme, geçmiş) | 5.3.1.1, 5.3.1.2, 5.3.1.4, 5.3.2.2, 5.3.2.4, 5.3.3.1.1, 5.3.3.1.2, 5.3.3.2.1, 5.3.3.2.5, 5.3.3.2.8, 5.3.3.3.1, 5.3.3.3.2, 5.3.3.3.3, 5.3.3.4.1, 5.3.3.4.2, 5.3.3.4.4 |
| 5.4 | Kullanıcı hesapları ve ortamı | 5.4.2.5, 5.4.2.6 |
| 6.1 | Günlük kaydı (journald, rsyslog, logrotate) | 6.1.1.1.5, 6.1.2.4, 6.1.2.5 |
| 7.2 | Yerel kullanıcı ve grup ayarları | 7.2.11 |

## Level 1 dışında yaptıklarımız

Projenin CIS Level 1 Server'da **karşılığı olmayan** (ya da daha ileri giden) işleri:

- **auditd** (13 kural satırı): benchmark'ta denetim bölümü (6.2) **tamamen Level 2 Server**'dır (54 madde). Bizdeki küçük kural seti bu bölümün yalnız bir kısmına benzer; madde madde eşlenmedi.
- **fail2ban** (`sshd` jail): benchmark'ta yok. Not: 5.3.2.2 / 5.3.3.1.x `pam_faillock` ister; fail2ban bunun **yerine geçmez** (farklı mekanizma).
- **SSH `PasswordAuthentication no` + anahtar zorunluluğu, `ufw allow_from` ağ kısıtı, geri alma güvenlik ağı:** benchmark'ın maddesi değil, bu projenin erişim-kaybı korumaları.

## Sonraki adım için notlar

- Yapılan: ufw `routed` (4.1.5), sysctl/modül kolay kazançları, SSH seçenekleri (5.1.9–5.1.12, 5.1.17, 5.1.20, 5.1.23, 5.1.24), dosya izinleri (5.1.1–5.1.4, 7.1.x, cron), sudo (5.2.2, 5.2.3, 5.2.6). Kalanlar: SSH erişim kısıtı (5.1.5), `pam_faillock`/`pwhistory` (5.3.x; tasarım notu: [design/pam-faillock.md](design/pam-faillock.md)), `su` kısıtı (5.2.7), günlük kaydı (6.1.x), bölüm/bağlama seçenekleri (1.1.2.x), kullanıcı hesabı denetimleri (7.2.x).
- Davranışı değiştirenler önce tartışılmalı: bölüm/bağlama seçenekleri (1.1.2.x), `pam_faillock` (kilitlenme riski), sudo ayarları, ssh şifre/kex listeleri (eski istemcileri bozabilir).
- Madde numarası etiket yapılacaksa (ör. `--tags cis-3.3.1.4`), mevcut `ufw`/`ssh` koruma etiketleriyle karışmaması için ayrı ad alanı gerekir.

<!-- Üretim notu: madde listesi PDF'ten betikle çıkarıldı; durumlar koddan elle işlendi. -->
