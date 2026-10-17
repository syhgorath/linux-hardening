# CIS Ubuntu Linux 26.04 LTS Benchmark eşlemesi (taslak)

Bu belge, projenin yaptıklarını **CIS Ubuntu Linux 26.04 LTS Benchmark v1.0.0** (08-26-2026) madde numaralarıyla eşler. Amaç iddia değil **boşlukları görmek**: proje tam CIS uyumu iddia etmez (bkz. [README](../README.md#ne-yapmaz-kapsam-sınırları)).

> **Telif:** CIS Benchmark metni bu depoda barındırılmaz ve aktarılmaz. Burada yalnızca madde **numaraları** ve kendi sözlerimizle kısa açıklamalar var. PDF'i [CIS'ten](https://www.cisecurity.org/cis-benchmarks) indirin; madde numarasından karşılık bulabilirsiniz.

## Nasıl okunur

- **Kapsam:** yalnızca **Level 1 - Server** profili ve **274 madde**. (Level 2 - Server ayrıca 76 madde; bu belgede ayrıca işlenmedi.) Sayılar PDF'ten betikle çıkarıldı, tek tek elle sayılmadı.

- ✅ **Karşılıyor:** ayar kodda var ve değeri benchmark'ın beklediğiyle **elle karşılaştırıldı** (sysctl, SSH, pwquality değerleri PDF'in beklediği değerlerle).
- 🟡 **Kısmen:** ilgili ayar var ama maddenin tamamını kapsamıyor (neden satırda yazılı).
- ⏸️ **Bilerek yok:** belgeli karar.
- ❌ **Yok:** kodda karşılığı yok. Sunucuda dağıtım varsayılanı zaten uygun olabilir; **denetlemiyor ve garanti etmiyoruz**.

- **Ölçülmedi:** CIS-CAT, OpenSCAP veya benzeri bir araçla tarama yapılmadı; bu tablo **koddan okuyarak** çıkarıldı. Kodda ayar olması, çalışan sunucuda uygulandığının kanıtı değildir (kanıtlar için [verification-log.md](verification-log.md)).

## Özet

| Bölüm | Konu | Level 1 madde | ✅ | 🟡 | ⏸️ | ❌ |
|---|---|---:|---:|---:|---:|---:|
| 1.1 | Dosya sistemi (modüller, bölümler, bağlama seçenekleri) | 29 | 1 |  |  | 28 |
| 1.2 | Paket yönetimi (APT depoları, güncellemeler) | 15 |  | 1 |  | 14 |
| 1.3 | AppArmor | 3 |  |  |  | 3 |
| 1.4 | Önyükleyici | 2 |  |  |  | 2 |
| 1.5 | Süreç sertleştirme (sysctl, core dump) | 11 | 6 |  |  | 5 |
| 1.6 | Oturum açma uyarı metinleri | 12 | 6 |  |  | 6 |
| 1.7 | GNOME oturum yöneticisi (masaüstü) | 6 |  |  |  | 6 |
| 2.1 | Sunucu servisleri | 22 |  | 1 |  | 21 |
| 2.2 | İstemci paketleri | 6 |  |  |  | 6 |
| 2.3 | Zaman senkronizasyonu | 6 |  |  |  | 6 |
| 2.4 | Zamanlanmış işler (cron, at) | 10 |  |  |  | 10 |
| 3.1 | Ağ aygıtları (IPv6, kablosuz, bluetooth) | 3 |  |  |  | 3 |
| 3.2 | Ağ çekirdek modülleri | 7 | 4 |  |  | 3 |
| 3.3 | Ağ çekirdek parametreleri | 27 | 17 |  | 5 | 5 |
| 4.1 | Güvenlik duvarı (ufw) | 4 | 3 |  |  | 1 |
| 5.1 | SSH sunucusu | 24 | 8 | 1 |  | 15 |
| 5.2 | Yetki yükseltme (sudo, su) | 6 |  |  |  | 6 |
| 5.3 | PAM (parola kalitesi, kilitleme, geçmiş) | 25 | 4 | 3 |  | 18 |
| 5.4 | Kullanıcı hesapları ve ortamı | 15 |  | 4 |  | 11 |
| 6.1 | Günlük kaydı (journald, rsyslog, logrotate) | 15 |  |  |  | 15 |
| 6.3 | Bütünlük denetimi (AIDE) | 2 | 1 |  |  | 1 |
| 7.1 | Sistem dosyası izinleri | 13 |  |  |  | 13 |
| 7.2 | Yerel kullanıcı ve grup ayarları | 11 |  |  |  | 11 |
| | **Toplam** | **274** | **50** | **10** | **5** | **209** |

Yani Level 1 Server maddelerinin yaklaşık %18'i ✅, %22'i en azından kısmen karşılanıyor. Bu, **uyumluluk yüzdesi değildir**: ölçülmedi, maddeler eşit ağırlıkta değil.

## Karşılananlar (✅)

| Madde | Ne | Nerede |
|---|---|---|
| 1.1.1.10 | usb-storage modülü kapalı | `roles/hardening_base/tasks/main.yml` |
| 1.5.1 | fs.protected_hardlinks = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 1.5.3 | kernel.yama.ptrace_scope = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 1.5.4 | fs.suid_dumpable = 0 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 1.5.5 | kernel.dmesg_restrict = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 1.5.8 | kernel.kptr_restrict = 2 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 1.5.9 | kernel.randomize_va_space = 2 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 1.6.2 | /etc/issue ve /etc/issue.net: işletim sistemi bilgisi içermeyen uyarı metni | `roles/hardening_base/tasks/main.yml` |
| 1.6.3 | /etc/issue ve /etc/issue.net: işletim sistemi bilgisi içermeyen uyarı metni | `roles/hardening_base/tasks/main.yml` |
| 1.6.5 | sshd Banner /etc/issue.net | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 1.6.7 | banner dosyaları root:root 0644 | `roles/hardening_base/tasks/main.yml` |
| 1.6.8 | banner dosyaları root:root 0644 | `roles/hardening_base/tasks/main.yml` |
| 1.6.10 | banner dosyaları root:root 0644 | `roles/hardening_base/tasks/main.yml` |
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
| 3.3.1.12 | rp_filter = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.13 | rp_filter = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.14 | accept_source_route = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.15 | accept_source_route = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.16 | log_martians = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.17 | log_martians = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.1.18 | tcp_syncookies = 1 | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.2.3 | accept_redirects = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.2.4 | accept_redirects = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.2.5 | accept_source_route = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 3.3.2.6 | accept_source_route = 0 (IPv4 ve IPv6) | `roles/hardening_kernel/templates/sysctl.conf.j2` |
| 4.1.1 | ufw kurulur | `roles/hardening_ufw/tasks/main.yml` |
| 4.1.2 | ufw etkinleştirilir | `roles/hardening_ufw/tasks/main.yml` |
| 4.1.3 | gelen varsayılan: deny | `roles/hardening_ufw/tasks/main.yml` |
| 5.1.6 | Banner /etc/issue.net | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.8 | ClientAliveInterval 300, ClientAliveCountMax 2 (ikisi de sıfırdan büyük) | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.15 | LoginGraceTime 60 | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.16 | LogLevel VERBOSE | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.18 | MaxAuthTries 3 (en çok 4 isteniyor) | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.19 | MaxSessions 4 (en çok 10 isteniyor) | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.21 | PermitEmptyPasswords no | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.1.22 | PermitRootLogin no | `roles/hardening_ssh/templates/sshd-hardening.conf.j2` |
| 5.3.3.2.2 | minlen 14 | `roles/hardening_auth/templates/pwquality.conf.j2` |
| 5.3.3.2.3 | minclass 3 | `roles/hardening_auth/templates/pwquality.conf.j2` |
| 5.3.3.2.4 | maxrepeat 3 | `roles/hardening_auth/templates/pwquality.conf.j2` |
| 5.3.3.2.6 | dictcheck 1 | `roles/hardening_auth/templates/pwquality.conf.j2` |
| 6.3.1 | AIDE kurulur, veritabanı üretilir | `roles/hardening_aide/tasks/main.yml` |

## Kısmen karşılananlar (🟡)

| Madde | Durum |
|---|---|
| 1.2.2.1 | Güvenlik güncellemeleri otomatik (unattended-upgrades); 'tüm güncellemeler kurulu' denetlenmez |
| 2.1.22 | postfix/courier kaldırılır, dinlemeyen `dma` kurulur; belirli bir MTA'nın yalnız-yerel ayarı denetlenmez |
| 5.1.9 | X11, ajan ve TCP yönlendirme kapalı; `DisableForwarding yes` yazılmıyor |
| 5.3.1.3 | libpam-pwquality kurulur; 'son sürüm' denetlenmez |
| 5.3.2.3 | paket kurulur ve pwquality.conf yazılır; pam-configs'te etkin olduğu doğrulanmadı |
| 5.3.3.2.7 | `enforcing = 1` yazılır; pam-configs'te `enforcing=0` kalmadığı denetlenmez |
| 5.4.1.1 | `PASS_MAX_DAYS 365` login.defs'te; yalnız yeni hesapları etkiler, mevcut kullanıcılara dokunulmaz |
| 5.4.1.3 | `PASS_WARN_AGE 7` login.defs'te; yalnız yeni hesaplar |
| 5.4.1.4 | `SHA_CRYPT_*_ROUNDS` yazılır; `ENCRYPT_METHOD` yazılmaz (dağıtım varsayılanına bırakıldı) |
| 5.4.3.3 | `UMASK 027` login.defs'te; /etc/profile.d ve bashrc dosyalarına dokunulmaz |

## Bilerek yapılmayanlar (⏸️)

| Madde | Neden |
|---|---|
| 3.3.1.1 | ip_forward'a bilerek dokunulmaz (LXD/konteyner/yönlendirici kullanımı) |
| 3.3.1.2 | ip_forward'a bilerek dokunulmaz |
| 3.3.1.3 | ip_forward'a bilerek dokunulmaz |
| 3.3.2.1 | ip_forward'a bilerek dokunulmaz |
| 3.3.2.2 | ip_forward'a bilerek dokunulmaz |

## Yok (❌), konuya göre

Her satır, o bölümde ✅/🟡/⏸️ **olmayan** Level 1 maddeleridir (numaralar yalnız konu gruplamak içindir).

| Bölüm | Konu | Madde numaraları |
|---|---|---|
| 1.1 | Dosya sistemi (modüller, bölümler, bağlama seçenekleri) | 1.1.1.1, 1.1.1.2, 1.1.1.3, 1.1.1.4, 1.1.1.5, 1.1.1.9, 1.1.1.11, 1.1.2.1.1, 1.1.2.1.2, 1.1.2.1.3, 1.1.2.1.4, 1.1.2.2.1, 1.1.2.2.2, 1.1.2.2.3, 1.1.2.2.4, 1.1.2.3.2, 1.1.2.3.3, 1.1.2.4.2, 1.1.2.4.3, 1.1.2.5.2, 1.1.2.5.3, 1.1.2.5.4, 1.1.2.6.2, 1.1.2.6.3, 1.1.2.6.4, 1.1.2.7.2, 1.1.2.7.3, 1.1.2.7.4 |
| 1.2 | Paket yönetimi (APT depoları, güncellemeler) | 1.2.1.1, 1.2.1.3, 1.2.1.4, 1.2.1.5, 1.2.1.6, 1.2.1.7, 1.2.1.8, 1.2.1.9, 1.2.1.10, 1.2.1.11, 1.2.1.12, 1.2.1.13, 1.2.1.14, 1.2.1.15 |
| 1.3 | AppArmor | 1.3.1.1, 1.3.1.2, 1.3.1.4 |
| 1.4 | Önyükleyici | 1.4.1, 1.4.2 |
| 1.5 | Süreç sertleştirme (sysctl, core dump) | 1.5.6, 1.5.7, 1.5.10, 1.5.11, 1.5.12 |
| 1.6 | Oturum açma uyarı metinleri | 1.6.1, 1.6.4, 1.6.6, 1.6.9, 1.6.11, 1.6.12 |
| 1.7 | GNOME oturum yöneticisi (masaüstü) | 1.7.1, 1.7.2, 1.7.3, 1.7.4, 1.7.5, 1.7.6 |
| 2.1 | Sunucu servisleri | 2.1.1, 2.1.2, 2.1.3, 2.1.4, 2.1.5, 2.1.6, 2.1.7, 2.1.8, 2.1.9, 2.1.10, 2.1.11, 2.1.12, 2.1.13, 2.1.14, 2.1.15, 2.1.16, 2.1.17, 2.1.18, 2.1.19, 2.1.20, 2.1.23 |
| 2.2 | İstemci paketleri | 2.2.1, 2.2.2, 2.2.3, 2.2.4, 2.2.5, 2.2.6 |
| 2.3 | Zaman senkronizasyonu | 2.3.1.1, 2.3.2.1, 2.3.2.2, 2.3.3.1, 2.3.3.2, 2.3.3.3 |
| 2.4 | Zamanlanmış işler (cron, at) | 2.4.1.1, 2.4.1.2, 2.4.1.3, 2.4.1.4, 2.4.1.5, 2.4.1.6, 2.4.1.7, 2.4.1.8, 2.4.1.9, 2.4.2.1 |
| 3.1 | Ağ aygıtları (IPv6, kablosuz, bluetooth) | 3.1.1, 3.1.2, 3.1.3 |
| 3.2 | Ağ çekirdek modülleri | 3.2.1, 3.2.2, 3.2.7 |
| 3.3 | Ağ çekirdek parametreleri | 3.3.1.10, 3.3.1.11, 3.3.1.19, 3.3.2.7, 3.3.2.8 |
| 4.1 | Güvenlik duvarı (ufw) | 4.1.5 |
| 5.1 | SSH sunucusu | 5.1.1, 5.1.2, 5.1.3, 5.1.4, 5.1.5, 5.1.7, 5.1.10, 5.1.11, 5.1.12, 5.1.13, 5.1.14, 5.1.17, 5.1.20, 5.1.23, 5.1.24 |
| 5.2 | Yetki yükseltme (sudo, su) | 5.2.1, 5.2.2, 5.2.3, 5.2.5, 5.2.6, 5.2.7 |
| 5.3 | PAM (parola kalitesi, kilitleme, geçmiş) | 5.3.1.1, 5.3.1.2, 5.3.1.4, 5.3.2.1, 5.3.2.2, 5.3.2.4, 5.3.3.1.1, 5.3.3.1.2, 5.3.3.2.1, 5.3.3.2.5, 5.3.3.2.8, 5.3.3.3.1, 5.3.3.3.2, 5.3.3.3.3, 5.3.3.4.1, 5.3.3.4.2, 5.3.3.4.3, 5.3.3.4.4 |
| 5.4 | Kullanıcı hesapları ve ortamı | 5.4.1.5, 5.4.1.6, 5.4.2.1, 5.4.2.2, 5.4.2.3, 5.4.2.4, 5.4.2.5, 5.4.2.6, 5.4.2.7, 5.4.2.8, 5.4.3.2 |
| 6.1 | Günlük kaydı (journald, rsyslog, logrotate) | 6.1.1.1.1, 6.1.1.1.2, 6.1.1.1.3, 6.1.1.1.4, 6.1.1.1.5, 6.1.1.1.6, 6.1.1.1.7, 6.1.2.1, 6.1.2.2, 6.1.2.3, 6.1.2.4, 6.1.2.5, 6.1.2.6, 6.1.2.7, 6.1.3.1 |
| 6.3 | Bütünlük denetimi (AIDE) | 6.3.2 |
| 7.1 | Sistem dosyası izinleri | 7.1.1, 7.1.2, 7.1.3, 7.1.4, 7.1.5, 7.1.6, 7.1.7, 7.1.8, 7.1.9, 7.1.10, 7.1.11, 7.1.12, 7.1.13 |
| 7.2 | Yerel kullanıcı ve grup ayarları | 7.2.1, 7.2.2, 7.2.3, 7.2.4, 7.2.5, 7.2.6, 7.2.7, 7.2.8, 7.2.9, 7.2.10, 7.2.11 |

## Level 1 dışında yaptıklarımız

Projenin CIS Level 1 Server'da **karşılığı olmayan** (ya da daha ileri giden) işleri:

- **auditd** (13 kural satırı): benchmark'ta denetim bölümü (6.2) **tamamen Level 2 Server**'dır (54 madde). Bizdeki küçük kural seti bu bölümün yalnız bir kısmına benzer; madde madde eşlenmedi.
- **fail2ban** (`sshd` jail): benchmark'ta yok. Not: 5.3.2.2 / 5.3.3.1.x `pam_faillock` ister; fail2ban bunun **yerine geçmez** (farklı mekanizma).
- **SSH `PasswordAuthentication no` + anahtar zorunluluğu, `ufw allow_from` ağ kısıtı, geri alma güvenlik ağı:** benchmark'ın maddesi değil, bu projenin erişim-kaybı korumaları.

## Sonraki adım için notlar

- En kolay kazançlar (düşük risk, kodda küçük): `ufw default deny routed` (4.1.5), kalan `sysctl` satırları (3.3.1.10, 3.3.1.11, 3.3.1.19, 3.3.2.7, 3.3.2.8), kullanılmayan dosya sistemi/ağ modülleri (1.1.1.x, 3.2.1, 3.2.2), SSH'ta açıkça yazılmayan seçenekler (5.1.10–5.1.14, 5.1.17, 5.1.20, 5.1.23, 5.1.24; sunucunun varsayılanları `sshd -T` ile doğrulanmadı).
- Davranışı değiştirenler önce tartışılmalı: bölüm/bağlama seçenekleri (1.1.2.x), `pam_faillock` (kilitlenme riski), sudo ayarları, ssh şifre/kex listeleri (eski istemcileri bozabilir).
- Madde numarası etiket yapılacaksa (ör. `--tags cis-3.3.1.4`), mevcut `ufw`/`ssh` koruma etiketleriyle karışmaması için ayrı ad alanı gerekir.

<!-- Üretim notu: madde listesi PDF'ten betikle çıkarıldı; durumlar koddan elle işlendi. -->
