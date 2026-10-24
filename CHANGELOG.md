# Değişiklik günlüğü

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) biçimini ve
[Anlamsal Sürümleme](https://semver.org/lang/tr/) kullanır.

## [Yayımlanmamış]

### Eklendi
- **Erişim/ağ seçenekleri** (Lynis SSH-7408, HRDN-7222; CIS 4.1.4 Level 2, 1.3): `hardening_ssh_max_sessions` (1-10, varsayılan **4** = davranış değişmez; Lynis 2 ister), `hardening_ufw_outgoing_deny` (varsayılan **KAPALI**, `warn_if`; giden trafik DROP + `hardening_ufw_outgoing_allow` izin listesi: 53, 123/udp, 80/tcp, 443/tcp; izin kuralları varsayılan değişmeden ÖNCE eklenir), `hardening_restrict_compilers` (varsayılan **KAPALI**, `warn_if`; `as`, `cc`, `c++`, `gcc`, `g++`, `clang`, `clang++` için `o-rwx`, sembolik bağlar çözülür), yeni rol `hardening_apparmor` + `hardening_apparmor_enforce` (varsayılan **KAPALI**, `warn_if`; complain kipindeki profiller `aa-enforce`, korumasız süreçler UYARI; AppArmor çekirdekte etkin değilse NOT). Kapatınca derleyici izinleri, AppArmor kipi ve `ALLOW OUT` kuralları geri alınmaz. `test_erisim_ag_secenekleri.py` (gerçek Ansible; mutasyon doğrulaması)

### Eklendi
- **auditd/AIDE Level 2 seçenekleri**, hepsi varsayılan **KAPALI**: `hardening_auditd_conf_cis` (`auditd.conf`: `max_log_file`, `keep_logs`, `space_left_action=email`, `admin_space_left_action=single`; `warn_if`), `hardening_auditd_disk_full_halt` (disk dolunca/hata verince `halt`; `warn_if`), `hardening_auditd_backlog_limit` (GRUB'a `audit_backlog_limit=N`, önerilen 8192; yeniden başlatmada etkili), `hardening_auditd_immutable` (`-e 2`; `warn_if`; kilitliyken kural yüklemesi atlanır ve UYARILIR), `hardening_aide_audit_tools` (audit araçları için AIDE sha512 + öznitelik kuralı, CIS 6.3.3). Kapatınca `auditd.conf` değerleri ve GRUB satırı geri ALINMAZ. `test_auditd_secenekleri.py` (gerçek Ansible, geçici dosyalar; mutasyon doğrulaması). Colima Ubuntu 26.04'te açma/kapama koşuldu (konteynerde çekirdek denetimi yok: `Load audit rules` her koşuda `changed` görünür, VM'de değil)

### Düzeltildi
- **`log_martians=1` (CIS 3.3.1) ufw etkinken gerçekte 0'dı** (gerçek Ubuntu VM'inde Lynis KRNL-6000 ile görüldü; eşleme belgesi ✅ diyordu): ufw, `/etc/ufw/sysctl.conf` dosyasını başlarken uygular ve orada `log_martians=0` yazar, `sysctl.d`'deki `1` ezilirdi. `hardening_ufw_log_martians` (varsayılan **AÇIK**) ufw'nin dosyasını `1` yapar ve canlı değeri düzeltir. Colima Ubuntu 26.04'te hata yeniden üretildi (değer 0) ve düzeltildi (1); ikinci koşu `changed=0`, `ufw reload` sonrası değer 1 kalır. `test_ufw_log_martians.py`

### Eklendi
- `hardening_kernel_extra_sysctl` (varsayılan açık) artık `kernel.unprivileged_bpf_disabled=1` de yazar (Lynis KRNL-6000; Ubuntu varsayılanı 2 ayrıcalıksız eBPF'yi zaten kapatır, 1 root'un yeniden açmasını da engeller)
- `hardening_kernel_modules_disabled` (varsayılan **KAPALI**, `warn_if: true`): `kernel.modules_disabled=1`. Yeniden başlatmaya kadar GERİ ALINAMAZ; sonrasında hiçbir çekirdek modülü yüklenemez (Docker overlay/br_netfilter, USB, ağ/ses sürücüleri). Lynis KRNL-6000 gerçek VM ölçümünde yalnızca 4 anahtar farklıydı (`modules_disabled`, `unprivileged_bpf_disabled`, iki `log_martians`)

### Eklendi
- **Lynis puanı için paket seçenekleri** (Lynis'in test mantığı konteynerde okundu; `docs/deneme-matrisi.md` bu seçeneklerin sshpocket deneme notlarını tutar). Varsayılan **AÇIK**, her biri kendi değişkeniyle kapanır: `hardening_debsums` + `hardening_debsums_cron_check` (`weekly`; PKGS-7370: kurulum 0/2 → 1/1, zamanlama 1/3 → 3/3), `hardening_apt_show_versions` (PKGS-7394), `hardening_process_accounting` (`acct`, ACCT-9622), `hardening_fail2ban_jail_local` (boş `jail.local`, DEB-0880; var olan dosyaya dokunulmaz). `haveged`/`rng-tools` EKLENMEDİ: Lynis'in rastgele sayı testleri (CRYP-8005, HW RNG) puan vermiyor, yalnızca ekrana yazıyor
- `hardening_apt_upgrade` (varsayılan **KAPALI**, `warn_if: true`): her koşuda `apt-get upgrade` (`dist-upgrade` değil). Lynis PKGS-7392 bekleyen güvenlik güncellemesi için 25 puan kaybettirir, en ağır kalem; servisler yeniden başlayabilir, yeni çekirdek yeniden başlatma ister (sunucu yeniden BAŞLATILMAZ, UYARI verilir)
- `hardening_report`: Level 2 salt okunur raporlar: sudoers'ta `NOPASSWD` (5.2.4, UYARI), `/etc/shells`'te `nologin` (5.4.3, NOT), ayrı bölümler `/home` `/var` `/var/tmp` `/var/log` `/var/log/audit` (1.1.2.x.1, NOT)

## [0.7.1] - 2026-10-24

v0.7.0'dan sonra, sshpocket 3.6.9 gerçek VM turunun bulguları. **Önemli:** `pve_firewall_preview` v0.7.0'da `hardening_pve_apply=true` iken güvenlik duvarını yazıyordu; bu sürümde düzeltildi. Kırıcı değişiklik yok.

### Düzeltildi
- `playbooks/rollback.yml --tags disarm`: geri alma ağı armed DEĞİLKEN de `changed=1` dönüyordu (gerçek VM turunda görüldü, kozmetik). Betik armed değilken artık "armed degil: yapilacak bir sey yok" der (temizlik yine yapılır), eylem yalnızca "disarmed" çıktısında değişiklik sayar. Birim testleri: `test_rollback_script.sh` (6), `test_rollback_playbook.sh` (gerçek Ansible `changed=` sayımı)
- **`pve_firewall_preview` önizleme değil gerçekten YAZIYORDU** (gerçek Proxmox VE 9 VM'inde sshpocket 3.6.9 turunda görüldü): sunucu değişkenlerinde `hardening_platform=proxmox-host` ve `hardening_pve_apply=true` (ana `apply` için zaten gerekli) iken eylem `playbooks/pve-firewall.yml`'i çalıştırdığı için `cluster.fw` yazılıyor, `pve-firewall restart` çalışıyordu. Eylem artık yeni `playbooks/pve-firewall-onizleme.yml --check` komutunu çalıştırır: yazma kapısı (`hardening_pve_fw_write`) `hardening_pve_fw_preview_only` ile DAİMA kapalıdır (değişken `component.yml`'de yok, formdan açılamaz); `hardening_pve_apply` ve `hardening_pve_fw_confirm` ne olursa olsun yazılmaz, geri alma ağı arm edilmez. Gerçek yazma yalnızca `pve_firewall_apply` ile. Gerçek Ansible koşusuyla denen birim testleri: `test_pve_firewall_tasks.py`

### Eklendi
- `hardening_sudo`: sudoers yapılandırmasının tamamı `visudo -c` ile SALT OKUNUR denetlenir, sorun varsa UYARI verir (kullanıcının dosyalarına dokunmaz, koşuyu durdurmaz). Ubuntu 26.04'ün sudo-rs'i `/etc/sudoers.d` içindeki bozuk bir dosyada hata basıp çalışmaya devam eder (rc=0); mevcut `become` denemesi bunu yakalamıyordu. sudo-rs 0.2.13 ve klasik sudo 1.9.17'de bozuk dosyada `visudo -c` çıkış kodu 1 verir (disposable konteynerde ölçüldü)

### Belgeler
- `docs/known-issues.md`: sertleştirmeden sonra yeni kullanıcıya parola verirken geçerli kurallar (14 karakter, 3 sınıf, 3 art arda aynı karakter, sözlük kelimesi yok); `/etc/sudoers.d` 0750 olunca root olmayan kullanıcının dizini listeleyememesi (beklenen)

## [0.7.0] - 2026-10-23

v0.6.0'dan sonra: **Proxmox güvenlik duvarı için iki sshpocket eylemi** (eylem sayısı 6 → 8), **CIS Level 1 Server'da "kodda karşılığı yok" madde kalmadı** ve opt-in **auditd Level 2**. Kırıcı değişiklik yok: yeni seçeneklerin hepsi varsayılan KAPALI ya da salt okunur.
**Denenmeyenler (değişmedi):** gerçek Raspberry Pi donanımı, VM/CT'li ve kümeli Proxmox, `auditd` Debian'da, sshpocket arayüzünde gerçek form.

### Eklendi
- **Son 3 CIS Level 1 maddesi (1.6.4, 5.3.3.4.2, 5.3.3.4.4): artık Level 1 Server'da "kodda karşılığı yok" madde kalmadı.** `hardening_report` MOTD'daki işletim sistemi bilgisini (1.6.4), `pam_unix` `remember=` (5.3.3.4.2) ve `use_authtok` eksikliğini (5.3.3.4.4) UYARI olarak bildirir (hiçbir şeyi değiştirmez); yeni `hardening_motd_disable_scripts` (varsayılan BOŞ, `/etc/update-motd.d` betiklerinin çalıştırma iznini kaldırır, sembolik bağlar atlanır). Ubuntu VM'inde 5.3.3.4.2 ve 5.3.3.4.4'ün varsayılan olarak sağlandığı ölçüldü (verification-log 54)
- **`hardening_auditd_cis_l2`** (varsayılan **KAPALI**, `warn_if: true`): CIS Level 2 denetim kuralları (6.2.3.x) `/etc/audit/rules.d/61-hardening-cis-l2.rules` dosyasına (yalnızca var olan yollar için; 32 bit kuralları yalnızca x86_64'te; üretici `files/audit_l2_rules.py`, birim testli) ve audit günlük/yapılandırma/araç dosyası izinleri (6.2.4.x, yalnızca izin kaldırır). Günlük hacmi artar, disk dolabilir. `-e 2` (6.2.3.35) ve disk dolunca durdurma (6.2.2.x) bilerek YOK. Gerçek Ubuntu VM'inde 76 kural yüklendi, `augenrules --check` "No change", kapatınca geri alındı (verification-log 53)
- **Proxmox güvenlik duvarı için iki sshpocket eylemi** (eylem sayısı 6 → 8): `pve_firewall_preview` (`playbooks/pve-firewall.yml`, salt okunur) ve `pve_firewall_apply` (`playbooks/pve-firewall-uygula.yml`, `type-server-name`, önizlemeyi şart koşar). Uygulama eylemi yazma onayını kendisi taşır (`hardening_pve_fw_confirm`, component.yml'de yok): formdan `hardening_pve_apply=false` gelse bile yazar. Eylem her sunucuda görünür; Proxmox olmayan hostta hiçbir şey yapmadan durur. Tutarlılık betiği iki eylem için de "tüm bağlantı ağlarını yaz (VPN + LAN)" uyarısını zorunlu kılar. İç içe Proxmox 9.2'de denendi (verification-log 52)

## [0.6.0] - 2026-10-22

v0.5.0'dan sonra: **Debian 13**, **Proxmox VE** (tek düğüm: pve-firewall ve tam sertleştirme), **Raspberry Pi** platformu ve CIS Level 1 Server'ın kalan maddelerinin büyük kısmı. `component.yml` `vars` listesi 48'den 80'e çıktı (+32; 15'i rollerde zaten olup menüde eksik olanlardı). Ayrıntılar aşağıdaki "Düzeltildi", "Eklendi" ve "Belgeler" bölümlerinde; doğrulama kayıtları verification-log 39-51.
**Dikkat (Ubuntu/Debian'da varsayılan AÇIK, yeni davranışlar):** (1) `hardening_base` artık `cron` paketini kurar (AIDE onu zaten bağımlılık olarak getiriyordu; değişiklik yalnızca minimal imajda görünür, `cron` izinleri ilk koşuda sıkılaşır); (2) `/etc/apt/auth.conf.d/*.conf` ve `pam_motd` dosyasının izinleri sıkılaşır (yalnızca izin kaldırır); (3) yeni SALT OKUNUR `hardening_report` (IPv6 durumu, dinleyen servisler, nokta dizinleri, `nullok`/boş parola): hiçbir şeyi değiştirmez. Yeni pwquality/journald/sshd erişim seçenekleri ve `hardening_pve_apply`, `hardening_rpi_strict` **varsayılan KAPALI**.
**Platformlar:** Proxmox VE hostu `hardening_platform=proxmox-host` + `hardening_pve_apply=true` ile (TEK düğüm; MTA değişimi, `ufw`, `libpam-tmpdir`, `noexec` ve `usb-storage` engeli çalışmaz; `rp_filter` gevşek), güvenlik duvarı `playbooks/pve-firewall.yml` ile. Raspberry Pi: `hardening_platform=raspberry-pi` (yalnızca `usb-storage` engeli gevşer). Platform atlatması yok (`hardening_allow_unsupported` etkisiz).
**Denenmeyenler:** gerçek Raspberry Pi donanımı, VM/CT'li ve kümeli Proxmox, `auditd` Debian'da, sshpocket arayüzünde gerçek form.

### Düzeltildi
- `hardening_base` artık `cron` paketini `hardening_files`'tan önce kurar: minimal imajda (cron yok) AIDE onu sonradan getirdiği için cron dosya/dizin izinleri (CIS bölüm 2.4) ilk koşuda sıkılaşmıyor, ikinci koşuda sıkılaşıyordu. Cron zaten kuruluysa değişiklik yok. Temiz Ubuntu 26.04 konteynerinde ilk koşuda sıkılaştığı doğrulandı

### Eklendi
- **sshpocket menüsüne 15 eksik ayar eklendi** (`component.yml` `vars`; rollerde zaten vardı, yalnızca düz Ansible'dan verilebiliyordu): SSH (`hardening_ssh_disable_password`, `hardening_ssh_kbdinteractive` `warn_if: true`, `hardening_ssh_allow_tcp_forwarding`), fail2ban (`hardening_fail2ban_maxretry`, `_bantime`, `_ignoreip`), parola/hesap (`hardening_pass_max_days`, `_min_days`, `_warn_age`, `hardening_umask`, `hardening_pwquality_minlen`), ufw sunucuya özel kural (`hardening_ufw_extra_allow_host`), `hardening_auditd_docker_rules`, `hardening_sudo_logfile`. Varsayılanlar rol varsayılanlarıyla aynı, davranış değişmez. `docs/component-vars.md` artık `component.yml`'deki HER değişkeni içerir (14 eksik satır tamamlandı) ve `scripts/check-consistency.py` bunu denetler
- **CIS kalan Level 1 maddelerinden bir kısmı** (docs/cis-esleme.md): dosya izinleri `/etc/apt/auth.conf.d/*.conf` (1.2.1.6) ve `pam_motd` dosyası (1.6.9) her zaman sıkılaşır; **salt okunur sistem raporu** `hardening_report` (varsayılan açık, `--tags report`): IPv6 durumu (3.1.1), dinleyen servisler (2.1.23, `hardening_approved_listeners`), kullanıcı nokta dizinleri (7.2.11), `nullok`/boş parolalı hesaplar (5.3.3.4.1); **varsayılan KAPALI** seçenekler: `hardening_pwquality_difok`, `hardening_pwquality_maxsequence`, `hardening_pwquality_enforce_for_root` (5.3.3.2.1, .5, .8), `hardening_journald_rotation` + `_system_max_use`, `_runtime_max_use`, `_max_file_sec` (6.1.1.1.5, `warn_if: true`), `hardening_ssh_allow_users`, `hardening_ssh_allow_groups` (5.1.5; bağlanan kullanıcı listede değilse rol durur). Önyükleyici parolası (1.4.1) ve 10 madde bilerek yapılmayanlara taşındı (gerekçeleri belgede)
- **Proxmox VE'de tam `harden.yml` gerçek koşusu** (TEK düğüm): preflight'ın "yalnızca önizleme" reddi kaldırıldı, yerine `hardening_pve_apply=true` kapısı geldi (`playbooks/pve-firewall.yml` ile aynı değişken; önizleme serbest; `hardening_allow_unsupported` atlatamaz). `libpam-tmpdir` Proxmox'ta (gevşek) kurulmaz. İç içe Proxmox 9.2'de tam koşu `failed=0`, ikinci koşu `changed=0`; `pve-*` servisleri ve web arayüzü (8006) çalışmaya devam etti, `postfix`/`pve-manager`/`proxmox-ve` korundu. VM/CT'li host, küme ve fail2ban ban davranışı DENENMEDİ (docs/verification-log.md madde 49)
- **Raspberry Pi platformu** (`hardening_platform=raspberry-pi`, `hardening_rpi_strict` varsayılan kapalı + `warn_if: true`, `hardening_rpi_markers`): Pi'de YALNIZCA `usb-storage` engeli gevşer (Pi USB'den açılabilir); `raspberry-pi` platformu yalnızca gerçek Pi'de kabul edilir (`hardening_allow_unsupported` atlatamaz); Pi algılanıp platform `generic` ise rol durmaz, NOT düşer. Raspberry Pi OS = `debian-13` profili. arm64 Debian konteynerinde Pi işaretleriyle denendi, **Pi donanımında DENENMEDİ**. Tasarım: docs/design/raspberry-pi.md
- **Debian 13 CIS eşlemesi ve Proxmox notları** (`docs/cis-esleme-debian.md`): Debian 13 v1.1.0 ile Ubuntu 26.04 v1.0.0 benchmark'larının içindekiler listeleri betikle karşılaştırıldı, 341 madde numara/başlık/profil olarak birebir aynı çıktı; Ubuntu eşlemesi Debian için de geçerli (Debian'da ölçülmedi). Proxmox'ta farklı ele alınan Level 1 - Server maddeleri tablolandı. Kod değişikliği yok
- **Proxmox VE güvenlik duvarı** (`playbooks/pve-firewall.yml`, rol `hardening_pve_firewall`, harden.yml'e BAĞLI DEĞİL; **TEK düğüm**): datacenter `cluster.fw`'yi `hardening_ssh_allow_from` ağlarından (`management` IP kümesi) yazar: gelen `DROP`, SSH + 8006 + ping yalnızca yönetim ağlarından. Önce `enable: 0` yazılır, `pve-firewall compile` ile doğrulanır, sonra `enable: 1`. Küme, boş/geçersiz `allow_from`, kontrol makinesini kapsamayan `allow_from` ve kullanıcının kendi `cluster.fw` dosyası (bu rolün işareti yok) durumlarında HİÇBİR ŞEY yazılmaz. `hardening_pve_apply` (varsayılan KAPALI, `warn_if: true`) kapalıyken yalnızca ÖNİZLEME; `hardening_pve_firewall_extra_ports` (varsayılan boş: rpcbind 111 kapanır; Proxmox yönetim ağlarına 8006/VNC/SPICE/22/taşıma portlarını kendisi açar). `local_network` alias'ı `allow_from`'dan tanımlanır (Proxmox yoksa düğümün yerel ağını `management` kümesine kendisi ekler). Gerçek koşu zamanlı geri alma ağı ile: `hardening-rollback` artık `cluster.fw`'yi de yedekler/geri yazar (yoksa siler) ve `pve-firewall restart` (olmazsa `stop`) çalıştırır; `hardening_verify_access` yeni SSH'a ek olarak 8006'ya TCP bağlantısı dener (`hardening_verify_access_tcp_ports`). Birim testleri + iç içe Proxmox 9.2'de GERÇEK koşu (erişim kaybı senaryosunda zamanlayıcı kendiliğinden geri aldı; verification-log 43)
- `hardening_ssh_permit_root_login` (`no` varsayılan | `prohibit-password`): Proxmox KÜMESİ için (`/etc/pve/corosync.conf` var iken `no` ile preflight DURUR). Parola ile kök girişi hiçbir ayarla açılmaz. `kernel`: Proxmox'ta (`hardening_pve_strict=false`) `rp_filter` gevşek (2), Proxmox'un varsayılanı. Golden testler (`sshd-hardening.rootkey.conf`, `sysctl.pve.conf`), küme koruması `test_proxmox_guard.py`'de. Kümeli host ve VM ağı üzerinde gerçek koşu DENENMEDİ.
- **`hardening_platform`** (`generic` | `proxmox-host`, varsayılan `generic`), **`hardening_pve_strict`** (varsayılan kapalı, `warn_if: true`) ve **`hardening_aide_pve_excludes`**: Proxmox VE platform bağlantısı (aşama 3), YALNIZCA `--check` önizlemesi. Proxmox hostu `generic` ile ASLA sertleştirilmez; `proxmox-host` yalnızca gerçek Proxmox'ta ve yalnızca `--check`'te kabul edilir, gerçek koşu REDDEDİLİR; `hardening_allow_unsupported` hiçbirini atlatmaz. Proxmox'ta MTA değişimi (postfix → dma) ve `ufw` hiç çalışmaz; `/tmp`+`/dev/shm` `noexec` ve `usb-storage` engeli `hardening_pve_strict=true` olmadıkça uygulanmaz; AIDE `/etc/pve`, VM deposu ve küme veritabanını taramaz (denenmedi). İç içe Proxmox 9.2'de `--check` `failed=0` (verification-log 42). `test_proxmox_guard.py` yeniden yazıldı, `test_platform_wiring.py`.
- **Proxmox VE durum raporu** (`playbooks/pve-report.yml`, rol `hardening_pve_report`, harden.yml'e BAĞLI DEĞİL, SALT OKUNUR): sürüm, küme, `pve-firewall` durumu, servisler, dinleyiciler, SSH, postfix/MTA bağımlılığı, VM/CT sayısı, abonelik; uyarı ve not üretir. Hedef Proxmox değilse durur. Gerçek bulgu: `postfix`'i kaldırmak `pve-manager` ve `proxmox-ve`'yi kaldırır. İç içe Proxmox 9.2'de denendi (verification-log 41). `test_pve_report.py`, `test_pve_report_tasks.py`. Proxmox hostu hâlâ SERTLEŞTİRİLMEZ.
- **Debian 13 (trixie) desteği** (`debian-13` profili, `hardening_supported_os`): `vars/debian-13.yml`; sürüm anahtarı Debian'da ANA sürüm (`ansible_facts['distribution_version']` `13.7` döndürür); `--check` için `python3-apt` yoksa anlaşılır mesajla durur; `ufw` kurulu değilken `--check` düşmez. Colima'da systemd'li Debian 13 konteynerinde `--check` `failed=0`, gerçek koşu `failed=0`, **ikinci koşu `changed=0`** (`auditd` konteynerde çalışmadığı için atlandı; verification-log 39). **Gerçek Debian VM'inde, `auditd` ve Raspberry Pi OS ile DENENMEDİ.** Proxmox hostu hâlâ bilerek reddedilir. `test_debian_support.py`.

### Belgeler
- Proxmox VE 9.2 SALT OKUNUR keşfi (iç içe VM, verification-log 40, `docs/design/proxmox-host.md`): `sudo` kurulu değil (önkoşul), `pve-firewall` etkin, tek düğüm, apt kaynakları temiz. Koruma gerçek Proxmox'ta doğrulandı: Debian 13 profiliyle de rol durur, `hardening_allow_unsupported` atlatmaz. Açık soru 1 (kısmen), 2 ve 7 cevaplandı.
- `docs/verification-log.md` madde 38: v0.5.0 (`main` `5d9e024`) gerçek VM'de SIFIRDAN tam kurulum: `--check` `failed=0`, 1. koşu `ok=143 changed=43 failed=0`, **2. koşu `changed=0`**, `noexec` etkin, `faillock` kapalı, Lynis 75 (bekleyen güvenlik güncellemeleri yüzünden 1 uyarı). v0.5.0 notundaki "sıfırdan tam kurulum yapılmadı" cümlesi bununla kapandı.

## [0.5.0] - 2026-10-21

v0.4.0'dan sonra: `/tmp` ve `/dev/shm` için `noexec` (varsayılan **açık**), hesap kilitleme (`pam_faillock`) ve parola geçmişi (`pam_pwhistory`) seçenekleri (varsayılan **kapalı**), geri alma güvenlik ağının PAM'i kapsaması,
Proxmox VE host koruması, isteğe bağlı saat düzeltme ve çok sayıda gerçek VM doğrulaması (verification-log 29-37). `component.yml` `vars` listesi 38'den 48'e çıktı (+10) (`sshpocket_api` değişmedi).
**Dikkat (varsayılan AÇIK ve sunucuyu etkileyen TEK davranış değişikliği):** `hardening_tmp_noexec` ve `hardening_shm_noexec`: `/tmp` ve `/dev/shm`'ye `nodev,nosuid,noexec`; bu dizinlerden doğrudan çalıştırma kapanır
(`./betik` reddedilir, `sh betik` çalışır). `/tmp`'ten ikili çalıştıran uygulamalar (Java/Node işleri, dışarıdan program çağıran PHP paketleri) bozulabilir; sorun olursa ilgili sunucuda `false` yapın (yazılmış yapılandırma geri alınmaz, elle silinir).
Ansible, `apt`, nginx+php-fpm ve composer ile gerçek VM'de denendi, yeniden başlatma sonrası kalıcı. Yalnızca ayrı ve `tmpfs` olan dizin yönetilir; `fstab`'taki mevcut `/dev/shm` satırı ezilmez.
**Her zaman açık korumalar:** Proxmox VE host'unda (`/etc/pve`) rol, `hardening_allow_unsupported` ile bile DURUR; geri alma betiği artık PAM dosyalarını da yedekler.
**Varsayılan KAPALI yeni seçenekler:** `hardening_pam_faillock` (+ `_deny`, `_unlock_time`, `_fail_interval`, `_even_deny_root`; geri alma ağı ARMED olmadan rol çalışmaz), `hardening_pam_pwhistory_remember` (+ `_enforce_for_root`), `hardening_time_makestep`.
**Önemli bulgu (bu pakette değil, Ubuntu 26.04'te):** sudo-rs ile Ansible'ın parolalı `become`'ı (`--ask-become-pass`) doğru parolayla bile `Timeout waiting for privilege escalation prompt` verir; çözüm `-e ansible_become_exe=/usr/bin/sudo.ws` (HOWTO bölüm 4).
**Doğrulama notu:** her madde gerçek VM'de TEK TEK denendi. Bu sürüm adayının TÜM varsayılanlarıyla sıfırdan kurulumu ve ikinci koşusu ayrıca YAPILMADI (v0.4.0 için sshpocket üzerinden yapıldı: madde 29; `main` üstünde tam `harden` + `changed=0` madde 32'de, `noexec` öncesi).
**Denenmeyenler:** Raspberry Pi, gerçek bir Proxmox host'u, `even_deny_root`, faillock'ta `su`/konsol girişi, faillock `rescue` yolunun gerçek tetiklenmesi, PDF üreten dış programlar, Java/Node ve Docker ile `noexec`.

### Eklendi
- `hardening_pam_faillock` (varsayılan **kapalı**, `warn_if: true`) ve `hardening_pam_faillock_deny` (5), `_unlock_time` (900), `_fail_interval` (900), `_even_deny_root` (kapalı, `warn_if: true`): hesap kilitleme (`pam_faillock`; CIS 5.3.2.2, 5.3.3.1.1, 5.3.3.1.2 ve 5.3.2.4 ❌ → 🟡). İki `pam-auth-update` profili (`preauth`+`account` pam_unix'ten önce, `authfail` sonra). Rol yalnızca geri alma güvenlik ağı ARMED iken çalışır (kapalıysa/armed değilse DURUR), yığın sırası assert ile doğrulanır, hata olursa rescue geri alır; `harden.yml`'de `hardening_rollback`'in `pam` etiketiyle arm penceresinin içinde. Sudo/su/konsol kilitlenir, SSH anahtarı etkilenmez; klasik sudo ve Ansible yanlış parolada koşu başına 2 kayıt bırakır. `test_pam_faillock.py`. Gerçek VM'de denendi (verification-log 37).
- `hardening-rollback` betiği PAM'i de kapsar: arm anında `/etc/pam.d/common-*`, `/var/lib/pam/*`, `hardening-faillock` profili ve `faillock.conf` yedeklenir; restore bunları OLDUĞU GİBİ geri yazar (`pam-auth-update` çalıştırmaz), sonradan eklenen faillock profilini siler, `/run/faillock` kilit sayaçlarını temizler ve PAM'i ssh/ufw'den ÖNCE geri alır. Gerçek VM'de bilerek bozuk `common-auth` zamanlayıcıyla kendiliğinden düzeldi (verification-log 36). `faillock` rolü için önkoşul; henüz hiçbir rol PAM'i arm penceresinde değiştirmiyor.
- `hardening_pam_pwhistory_remember` (varsayılan **0 = kapalı**) ve `hardening_pam_pwhistory_enforce_for_root` (varsayılan kapalı): parola geçmişi (`pam_pwhistory`; CIS 5.3.3.3.1, 5.3.3.3.2, 5.3.3.3.3 ❌ → 🟡). `pam-auth-update` profili (`pwquality` > `pwhistory` > `unix` sırası, assert + rescue ile doğrulanır) ve `pwhistory.conf`. Yalnızca parola DEĞİŞTİRMEYİ etkiler, girişe dokunmaz. Ölçüm: `remember=N` mevcut + önceki N-1 parolayı engeller; root'un `chpasswd`'si `enforce_for_root` kapalıyken engellenmez. `test_pwhistory.py`. Gerçek VM'de denendi (verification-log 35).
- `hardening_tmp_noexec` ve `hardening_shm_noexec` (varsayılan **açık**, `warn_if: false`): `/tmp` ve `/dev/shm`'ye `nodev,nosuid,noexec` uygulanır (CIS 1.1.2.1.4 ve 1.1.2.2.4 🟡 → ✅). `/tmp`: `tmp.mount` drop-in'i + anında remount; `/dev/shm`: `/etc/fstab` satırı + remount. Yalnızca ayrı ve tmpfs olan dizin yönetilir; fstab'da `/dev/shm` satırı varsa üstüne yazılmaz. **Davranışı değiştirir:** `/tmp`'ten doğrudan çalıştırma kapanır (`sh betik` çalışır); sorun olursa `false` yapın (yazılmış yapılandırma elle silinir). Ansible etkilenmez. Karar mantığı `tmp_plan.py`. `test_tmp_plan.py`, `test_tmp_noexec_tasks.py`. Gerçek VM'de PHP/nginx/composer ile denendi (verification-log 33).
- Tam `harden` + idempotens, gerçek VM (verification-log 32): üçüncü koşu `ok=126 changed=0`; uygulama sonrası Lynis 80 (öncesi 62). İkinci koşu tek seferlik ssh bağlantı kopmasıyla yarım kaldı, sebep belirlenmedi.
- `hardening_time_makestep` gerçek VM'de denendi (verification-log 31): saat 3 gün geri alınınca `restart` yolu saati düzeltti, saat doğruyken ikinci koşu `changed=0`. `makestep` dalı (kaynak seçiliyken büyük kayma) VM'de üretilemediği için yalnız birim testlidir.
- `hardening_preflight`: Proxmox VE hostu koruması. `/etc/pve` ya da `/usr/bin/pveversion` varsa rol en başta DURUR; `hardening_allow_unsupported=true` bunu ATLATMAZ, `--check`'te de çalışır ve Proxmox için ayrı bir bayrak yoktur. Proxmox üstündeki Ubuntu VM'leri etkilenmez. Proxmox hostunu sertleştirme hâlâ yok (`docs/design/proxmox-host.md`). Bildirim sshpocket tarafından geldi. `test_proxmox_guard.py`.
- `hardening_time_makestep` (varsayılan **kapalı**, `warn_if: true`): zaman raporu büyük bir saat kayması bulursa düzeltir (`chronyc makestep`; kaynak seçilmemişse `systemctl restart chrony`, çünkü o durumda `makestep` etkisiz). Saati sıçratır, `--check`'te çalışmaz. `time_report.py` çıktısına `fix` alanı eklendi (`makestep` | `restart` | boş; betik hiçbir şey çalıştırmaz). Fikir sshpocket tarafından geldi. Gerçek (saati kaymış) VM'de denenmedi.

### Belgeler
- Platform kararı (`docs/design/proxmox-host.md` soru 5 CEVAPLANDI): platform bir **paket değişkeni** olur, preflight gerçek platformu doğrular, sshpocket yalnızca iletir. `docs/SUPPORT.md`: Proxmox hostu bilerek reddedilir, Ubuntu Server'ın Raspberry Pi üzerinde çalışması **denenmedi**.
- **Önemli bulgu (gerçek VM):** Ubuntu 26.04'ün sudo-rs'i ile Ansible'ın parolalı `become`'ı (`--ask-become-pass`) doğru parolayla bile `Timeout (12s) waiting for privilege escalation prompt` verir; çözüm `-e ansible_become_exe=/usr/bin/sudo.ws`. `HOWTO.md` (bölüm 2, 4, sorun giderme), `docs/known-issues.md`, verification-log madde 34. `docs/design/pam-faillock.md`'ye faillock öncesi taban çizgisi ölçümü eklendi.
- `examples/yedek-pull.md`: çeken (pull) yedek örneği, kısıtlı `rrsync -ro` anahtarıyla (sunucu başına kullanıcı, `authorized_keys` kısıtı, `hardening_ssh_allow_from`, `--link-dest`). **ÖRNEKTİR ve denenmedi** (yedek sunucusu yok); yalnız `rrsync`'in Ubuntu 26.04'te bulunduğu doğrulandı.
- `examples/README.md`: "Ayarlarım nerede? Güncellemede ne olur?" bölümü (kod / kendi ayarlarınız / sunucu ayrımı, ayarları klasörün dışında tutma, bir ayarı hepsinde açıp bir grupta kapatma, yeni sürüme geçiş adımları).
- `docs/verification-log.md` madde 29: v0.4.0'ın sshpocket üzerinden TAZE kurulumda doğrulanması (`ok=131 changed=38 failed=0`, `warn_if` onayı çıkmadı). v0.4.0 sürüm notundaki "tam kurulum yapılmadı" cümlesi bununla kapandı; apply sonrası audit ve ikinci koşu hâlâ yapılmadı.
- `component.yml` önizleme uyarısı: `--check`'te `dma` kurulmadığı için apt simülasyonu AIDE'nin posta bağımlılığı olarak `postfix`'i "yeni paket" gösterebilir; gerçek uygulamada `dma` önce kurulur ve `postfix` gelmez.

## [0.4.0] - 2026-10-19

v0.3.0'dan sonra: Lynis önce/sonra ölçümünden çıkan küçük maddeler, üç salt okunur rapor (root ortamı, `/tmp` ve `/dev/shm`, AIDE zamanlayıcı denetimi), `su` kısıtı, Docker `daemon.json` seçenekleri,
Grup 3 tasarım notu ve CI'da yakalanan düzeltmeler. `component.yml` `vars` listesine 11 değişken eklendi (27'den 38'e) (`sshpocket_api` değişmedi).
**Dikkat edilecekler (varsayılan AÇIK ve sunucuyu etkileyenler; kaçış yolu `docs/known-issues.md` ve README "Dikkat" tablosunda):**
(1) `kernel`: `fs.protected_fifos=2`, `kernel.sysrq=0` (VM konsolundan SysRq acil yeniden başlatma kullanılamaz), `net.core.bpf_jit_harden=2` (`hardening_kernel_extra_sysctl`);
(2) `auth`: `libpam-tmpdir` (`$TMPDIR` artık `/tmp` değil, `hardening_pam_tmpdir`); (3) `base`: `apt-listchanges` (`hardening_apt_listchanges`; yükseltmeyi bloklamaz);
(4) `files`: `/etc/sudoers.d` `0750`; (5) `ansible.cfg`: `ServerAliveInterval` (ölü bağlantıda koşu ~45 sn sonra UNREACHABLE olur).
**Salt okunur, varsayılan açık raporlar (hiçbir şeyi değiştirmez):** `hardening_root_env_report`, `hardening_tmp_report`; `hardening_aide_scheduled_check` paketin zaten açık kurduğu zamanlayıcıyı açık tutar.
**Varsayılan KAPALI yeni seçenekler:** `hardening_su_restrict` (+ `hardening_su_group`), `hardening_docker_no_new_privileges`, `hardening_docker_userland_proxy_off`, `hardening_docker_icc_off`.
**Doğrulama notu:** her madde gerçek VM ya da mini labda TEK TEK denendi (verification-log 21-28); bu sürümün TÜM yeni varsayılanlarıyla sıfırdan tam kurulumu ve ikinci koşusu v0.3.0 sonrası ayrıca yapılmadı.

### Eklendi
- `hardening_tmp_report` (varsayılan **açık**, SALT OKUNUR, `warn_if` yok): `/tmp` ve `/dev/shm` bağlama seçenekleri raporu (CIS 1.1.2). `noexec` yoksa yalnızca NOT düşer (Ubuntu varsayılanı budur), `nodev`/`nosuid` yoksa, dizin ayrı bağlama değilse ya da Ansible `remote_tmp` `/tmp` altındaysa UYARIR. Hiçbir şeyi değiştirmez; `noexec` AÇMA seçeneği bilerek eklenmedi (paket betikleri ve Ansible etkilenebilir, `docs/design/grup3-tmp-su-root.md`). `hardening_files_enabled`'dan bağımsız. `test_tmp_report.py`, `test_tmp_tasks.py`.
- `hardening_root_env_report` (varsayılan **açık**, SALT OKUNUR, `warn_if` yok): root ortamı raporu (CIS 5.4.2.5 `PATH` bütünlüğü, 5.4.2.6 `umask`). Hiçbir şeyi değiştirmez, `--check`'te de çalışır. `PATH`'te boş girdi, `.`, olmayan/yazılabilir/root'a ait olmayan dizin ve 027'den gevşek `umask` uyarılır. Karar mantığı `roles/hardening_auth/files/root_env_report.py`. `test_root_env_report.py`, `test_root_env_tasks.py`. Mini labda bilerek bozulmuş root ortamı yakalandı (verification-log 27).
- `hardening_aide_scheduled_check` (varsayılan **açık**, `warn_if` yok): `dailyaidecheck.timer` açık ve başlatılmış tutulur (CIS 6.3.2 ❌ → ✅). Paket zaten açık kurduğu için normalde değişiklik yapmaz. AIDE'nin işi değişmedi. `test_aide_timer.py`. Gerçek VM'de bulgular `docs/known-issues.md`'de (e-posta teslim edilmiyor, veritabanı kendiliğinden güncellenmiyor, kontrol ~8,5 dk ve ~2,4 GB bellek tepesi).
- `hardening_su_restrict` (varsayılan **kapalı**, `warn_if: true`) ve `hardening_su_group` (varsayılan `sugroup`): `su` yalnızca grup üyelerine açılır (CIS 5.2.7). Grup yoksa BOŞ oluşturulur, yani `root` dışında kimse `su` yapamaz; `sudo`, ssh, konsol etkilenmez. `/etc/pam.d/su`'ya `pam_rootok` satırından hemen sonra `pam_wheel.so use_uid group=...` eklenir. `test_su_restrict.py`. Grup 3 tasarım notu: `docs/design/grup3-tmp-su-root.md`.
- Grup 3 için tasarım notu: `docs/design/grup3-tmp-su-root.md` (kod yok): `/tmp`/`/dev/shm` `noexec`, `su` kısıtı, root `PATH`/`umask`; test VM'inden ölçümler, riskler, önerilen sıra ve 5 açık soru.
- `hardening_docker`: üç tek tek açılan `daemon.json` seçeneği, hepsi varsayılan **kapalı**, `warn_if: true`: `hardening_docker_no_new_privileges` (CIS Docker 2.15), `hardening_docker_userland_proxy_off` (2.17), `hardening_docker_icc_off` (2.2). Yalnızca `hardening_docker_daemon_manage=true` iken etkilidir. sshpocket sözlük (dict) tipi bilmediği için `hardening_docker_daemon_settings` yerine bu bool'lar kullanılır. Gerçek Docker'la doğrulandı (verification-log 25); **önemli:** `icc=false`, `live-restore` açıkken yalnızca Docker yeniden başlatmakla mevcut `docker0` köprüsüne işlemez, konteynerler durdurulmalıdır.
- `hardening_apt_listchanges` (varsayılan **açık**, `warn_if` yok): `apt-listchanges` kurulur (Lynis DEB-0811) ve `/etc/apt/listchanges.conf` yükseltmeyi ASLA bloklamayacak şekilde yazılır (`frontend=text`, `confirm=false`, e-posta yok). `apt-listbugs` Ubuntu 26.04 depolarında olmadığı için eklenmedi (DEB-0810 uygulanamaz); rkhunter/malware tarayıcı bilinçli eklenmedi (`docs/known-issues.md`). `test_apt_listchanges.py`.
- `hardening_files`: `/etc/sudoers.d` dizini `0750` (grup yazma ve diğer erişim kaldırılır; yalnızca sıkılaşır). Lynis AUTH-9252 `0755`'i "possibly unsafe" sayıp ekranda kırmızı WARNING gösteriyordu (hem sertleştirme öncesi hem sonrası taramada). Ubuntu 26.04'ün sudo-rs'i dizini `0755` bırakıyor; klasik sudo'nun Debian varsayılanı `0750`'dir. `sudo` kök olarak okuduğu için işlev etkilenmez.
- Lynis önce/sonra ölçümünden (58 → 73, verification-log 21) çıkan küçük ve güvenli maddeler: `hardening_kernel_extra_sysctl` (varsayılan **açık**: `fs.protected_fifos=2`, `kernel.sysrq=0`, `net.core.bpf_jit_harden=2`) ve `hardening_pam_tmpdir` (varsayılan **açık**: `libpam-tmpdir`, oturum başına özel `$TMPDIR`). İkisi de `component.yml` `vars`'ta, `warn_if` yok. `test_lynis_small.py`. Lynis FINT-4402'nin (AIDE özetleri) yanlış pozitif olduğu `docs/known-issues.md`'de açıklandı; yapılandırma daraltılmadı.

### Değişti
- `component.yml`: `hardening_disable_apport` ve `hardening_disable_update_notifier_motd` değişkenlerinden `warn_if` kaldırıldı (#74). Varsayılanları zaten `true` olduğu için sshpocket kullanıcı hiçbir şeyi değiştirmediği hâlde her `apply`'da "riskli değer" onayı istiyordu. `scripts/check-consistency.py` artık `warn_if` varsayılana eşitse hata verir (sürüm 0.3.0'da ikisi de bu hataya sahipti).
- `ansible.cfg`: `[ssh_connection] ssh_extra_args = -o ServerAliveInterval=15 -o ServerAliveCountMax=3`. Ölü bir TCP bağlantısında (ağ değişti, Mac uyudu) `ansible-playbook` artık ~45 sn yanıt gelmezse görevi UNREACHABLE yapar. Ansible'ın varsayılan `ssh_args`'ı (ControlMaster/ControlPersist) ezilmez. `test_ansible_cfg.py`. Mini labda sessiz paket düşürmeyle ölçüldü: ayar yokken 153 sn, varken 58 sn.

## [0.3.0] - 2026-10-18

CIS Ubuntu 26.04 Level 1 Server eşlemesi, üç yeni rol (`hardening_files`, `hardening_sudo`, `hardening_docker`), salt okunur zaman raporu, çoklu sunucu örnekleri ve çok sayıda gerçek VM / Docker
mini lab doğrulaması. **Dikkat edilecekler (varsayılan olarak AÇIK ve davranışı değiştirenler; hepsinin kaçış yolu `docs/known-issues.md` ve README "Dikkat" tablosunda):**
(1) `kernel`: yeni sysctl satırları (`secure_redirects=0`, `route_localnet=0`) ve modül yasakları (`cramfs`, `freevxfs`, `hfs`, `hfsplus`, `jffs2`, `firewire-core`, `atm`, `can`);
(2) `ufw`: yönlendirilen trafik için `deny` (`hardening_ufw_routed_deny`); (3) `ssh`: `DisableForwarding`, zayıf `MACs` çıkarma, `MaxStartups 10:30:60`, drop-in `0600`;
(4) `base`: `apport` ve `update-notifier-motd` kapatma, `journald` kalıcı depolama; (5) `sudo`: `use_pty` ve `timestamp_timeout=15` (sudo-rs algılanır); (6) `files`: dosya izinleri (yalnızca sıkılaşır);
(7) `auditd`: `clock_adjtime` kuralı ve (Docker kuruluysa) Docker izleme kuralları. **Varsayılan KAPALI yeni seçenekler:** core dump, `telnet`/`ftp` kaldırma, `TMOUT`, `INACTIVE`, günlük dosyası izinleri, IPv6 RA,
`audit=1`, servis yeniden başlatma, Docker rolü. `component.yml` `vars` listesine bu sürümde 22 değişken eklendi (5'ten 27'ye) (`sshpocket_api` değişmedi). Tam CIS uyumu iddiası yoktur: eşleme `docs/cis-esleme.md` içindedir
ve CIS-CAT ile ölçülmedi.

### Eklendi
- `hardening_docker` (yeni rol, etiket `docker`, **varsayılan KAPALI**, Docker kurulu değilse atlanır; `docs/design/docker-sunucusu.md` ilk dilim): `hardening_docker_enabled` ile **salt okunur rapor** (docker grubu üyeleri, `0.0.0.0`'a yayınlanan ve izinli listede olmayan konteyner portları, TLS'siz TCP API, `iptables:false`/`experimental`/`insecure-registries`/`tcp://` gibi `daemon.json` ayarları); `hardening_docker_daemon_manage` ile `daemon.json` **birleştirme** (`live-restore`, günlük boyutu sınırı; mevcut anahtarlar korunur, değişmeden önce yedek, geçersiz JSON'a dokunulmaz); `daemon.json` değişince önce `reload` (SIGHUP: `live-restore` konteynerler durmadan açılır; gerçek Docker'da doğrulandı), tam yeniden başlatma yalnız `hardening_docker_restart=true` ile. Karar betikleri birim testli (`test_docker_scripts.py`, `test_docker_tasks.py`).
  `hardening_files`: Docker dosyaları (`docker.service`/`docker.socket`, `/etc/docker`, `daemon.json`, `/run/docker.sock` `root:docker`, containerd soketi) için izinler (yalnız var olanlara). `hardening_auditd`: Docker kuruluysa var olan Docker yolları için izleme kuralı (`/var/lib/docker` hariç; `hardening_auditd_docker_rules`, varsayılan açık).
- `docs/design/docker-sunucusu.md`: Docker çalıştıran sunucu için tasarım notu (kod yok). CIS Docker Benchmark v1.9.0 bölüm 1-3 eşleme tablosu, `daemon.json` birleştirme mekanizması, ufw/Docker riski seçenekleri, önerilen değişkenler, test planı ve açık sorular.
- `examples/` (3 sunucu: web / Docker / Redis+günlük+yedek): `inventory.example.yml`, `group_vars/{all,web,docker,infra}.yml`, sshpocket için `sshpocket/<sunucu>.yml` ve katmanları/liste tuzağını anlatan `examples/README.md`; HOWTO 7c. `test_examples.py`: gerçek `ansible-inventory` birleşimi ile sshpocket dosyaları aynı kalır.
- `hardening_disable_usb_storage` (varsayılan `true`, yani bugünkü davranış): `false` iken `usb-storage` kural dosyası silinir, USB diske yedek alınabilir. `component.yml` `vars`'ta.
- CIS "grup 2" (davranışı değiştirenler, **hepsi varsayılan KAPALI**, her biri kendi değişkeniyle; `test_cis_group2.py`, `test_files_role.py`):
  - `hardening_disable_coredump` (`limits.d` ve `systemd-coredump`), `hardening_remove_legacy_clients` (`telnet`/`ftp` istemcileri ve `ubuntu-standard` metapaketi; `apt remove`, purge ve autoremove YOK; metapaket olmadan apt bir istemciyi kaldırınca öbürünü kuruyor, gerçek VM'de görüldü), `hardening_shell_timeout_seconds` (`TMOUT`, 0..900), `hardening_password_inactive_days` (`useradd -D -f`; yalnız yeni hesaplar, mevcutlar uyarıyla listelenir, 0..365), `hardening_log_file_permissions` (`/var/log` dosyalarında `g-wx,o-rwx`; wtmp/btmp/lastlog/faillog ve journal hariç).
  - Tamsayı değişkenler `abc` gibi değerleri sessizce "kapalı" saymaz; reddedilir.
  - `/var/log` taraması taşınabilir `find` kullanır (`-perm /mode` GNU'ya özgüdür).
  - README "Dikkat" bölümü güncellendi. Kalan (tasarım gerekir): `/tmp` ve `/dev/shm` `noexec`, `su` kısıtı, kullanıcı dot dizinleri.
- `hardening_ufw`: **`hardening_ufw_extra_allow` artık sshpocket'e açık** (`component.yml` `vars`, `list[string]`). Kaynak kısıtlı kurallar da yazılabilir (`from 192.0.2.5 to any port 6379 proto tcp`). **Geçersiz girdi** (typo, ek komut, yanlış biçim) roller çalışmadan, daha preflight'ta reddedilir (AIDE'nin dakikalarca sürmesinden sonra değil). `hardening_ufw_extra_allow_host` (yeni): sunucuya özel kurallar, grup listesiyle **birleşir**; Ansible liste değişkenlerini birleştirmez, ezer, bu yüzden `host_vars`'a `hardening_ufw_extra_allow` yazmak grubunkini sessizce siliyordu. Eski-kural (prune) koruması da birleşik listeyi görür.
- CIS "grup 1" parçaları (sessiz ve güvenli; her biri kendi değişkeniyle kapanır, hepsi `test_cis_group1.py` / `test_files_role.py` ile sınandı):
  - `hardening_base`: `hardening_disable_apport` (CIS 1.5.7; `/etc/default/apport` `enabled=0`, servis durdurulup maskelenir) ve `hardening_disable_update_notifier_motd` (CIS 1.6.12). Olmayan birime dokunulmaz. Varsayılan **açık**; çökme raporları toplanmaz.
  - `hardening_base`: `hardening_suid_report` (CIS 7.1.13): SUID/SGID dosyalarının **salt okunur** özeti (`find / -xdev`, en çok 120 sn). Hiçbir şeyi değiştirmez.
  - `hardening_files`: APT dizinleri (`auth.conf.d`, `sources.list.d`) 0755 ya da daha kısıtlı; `sources.list.d` içindeki dosyalar ve `.gpg` anahtarları 0644 ya da daha kısıtlı (yalnız fazla izin kaldırılır).
- `hardening_base`: journald için `/etc/systemd/journald.conf.d/60-hardening.conf` (`Storage=persistent`, `Compress=yes`; CIS 6.1.1.1.6/7). `Storage=auto` yalnızca `/var/log/journal` varsa kalıcıdır (bazı bulut imajlarında yoktur). Günlükler diske yazılır; saklama süresi/boyut ayarlarına dokunulmaz. Değişince `systemd-journald` yeniden başlatılır.
- `docs/cis-esleme.md`: yeni **⚪ "Varsayılan uygun"** durumu. Test VM'inde (2026-10-18) CIS denetim metinlerinin yaklaşığı salt okunur çalıştırıldı; 100 Level 1 madde Ubuntu varsayılanıyla karşılanıyor (kodumuz yapmıyor, garanti değil). VM'de uygun çıkmayanlar listelendi (`telnet`/`ftp` istemcisi kurulu, `apport` etkin, `/tmp` `noexec` yok, `sysstat` günlükleri okunabilir vb.).
- `hardening_files` (yeni rol, etiket `files`): CIS dosya izinleri: `/etc/passwd`, `group`, `shadow`, `gshadow` (+ `-` yedekleri), `shells`, `opasswd`; `sshd_config`, `sshd_config.d` ve içindeki `.conf` dosyaları, ana bilgisayar anahtarları; cron dosyaları/dizinleri; `/etc/motd`; `/boot/grub/grub.cfg`. **Yalnızca fazla izni kaldırır** (sembolik modlar: 0600 olan dosya 0644 olmaz), olmayan dosyayı oluşturmaz (`cron.allow`/`at.allow` dahil: boş `cron.allow` crontab kullanımını kapatırdı), sembolik bağı izlemez. `hardening_files_enabled=false` ile kapanır. `hardening_ssh` artık drop-in'i `0600` yazar. Geri alma güvenlik ağı kapsamında değil.
- `hardening_sudo` (yeni rol, etiket `sudo`, en sonda): `/etc/sudoers.d/60-hardening` ile `use_pty` ve `timestamp_timeout=15` (CIS 5.2.2, 5.2.6); klasik sudo'da ayrıca `logfile=/var/log/sudo.log`. **Ubuntu 26.04'ün varsayılanı sudo-rs'tir ve `logfile` desteklemez** (gerçek VM'de görüldü: "unknown setting: 'logfile'"); rol `visudo --version` ile algılar, sudo-rs'te `logfile` yazmaz (olaylar journald'e gider). `visudo -cf` ile doğrulanır, yazıldıktan hemen sonra `become` denenir (başarısızsa dosya silinir ve play durur); `!authenticate` bulunursa yalnızca uyarır. `hardening_sudo_enabled=false` ile kapanır. Geri alma kapsamında değil.
- `hardening_ssh`: açık yazılan CIS 5.1.x seçenekleri: `DisableForwarding yes` (yalnız `hardening_ssh_allow_tcp_forwarding=no` iken), `GSSAPIAuthentication no`, `HostbasedAuthentication no`, `IgnoreRhosts yes`, `PermitUserEnvironment no`, `UsePAM yes`, `MaxStartups 10:30:60` ve `MACs` için zayıf listenin çıkarılması. Çoğu varsayılan zaten uygundu (test VM'inde `sshd -T`); açık yazmak denetlenebilirlik içindir. **Davranışı değiştirenler:** `MaxStartups` (Ubuntu varsayılanı `10:30:100`), `MACs` (umac-64/umac-128-etm kapanır), `DisableForwarding` (StreamLocal da kapanır). Bkz. `docs/known-issues.md`.
- CIS 26.04 eşlemesinden çıkan "kolay kazançlar" (`docs/cis-esleme.md`), **hepsi `test_cis_quickwins.py` ile sınandı**:
  - `hardening_kernel`: `secure_redirects=0` (CIS 3.3.1.10/11), `route_localnet=0` (3.3.1.19); modül yasağı `cramfs`, `freevxfs`, `hfs`, `hfsplus`, `jffs2`, `firewire-core` (1.1.1.x) ve `atm`, `can` (3.2.1/3.2.2). `hardening_kernel_disable_ipv6_ra` (varsayılan `false`): `accept_ra=0` (3.3.2.7/8), IPv6'sını RA'dan alan sunucuyu kesebileceği için kapalı.
  - `hardening_ufw`: `ufw default deny routed` (4.1.5), `hardening_ufw_routed_deny` (varsayılan `true`) ile kapatılabilir.
  - `hardening_auditd`: `clock_adjtime` kuralı yalnız kullanıcı oturumundan gelirse (`auid>=1000`, chronyd gürültüsü yok); `hardening_auditd_restart_services` (varsayılan `[]`, `ssh`/`sshd` reddedilir) ve `hardening_auditd_grub_audit` (varsayılan `false`, `audit=1`, yeniden başlatma gerekir, geri alma kapsamında değil).
  Varsayılan davranış değişiklikleri: yeni sysctl satırları, yeni modül yasakları ve `routed deny` **varsayılan açıktır**; bkz. `docs/known-issues.md`.
- `hardening_time` (yeni rol, etiket `time`): **salt okunur** zaman raporu. chrony çalışıyor mu, kaynaklar ulaşılabilir ve seçili mi, saat kaynaklara göre ne kadar kayık? `harden` çıktısında `ZAMAN:` ya da `UYARI (zaman):` verir.
  Snapshot dönüşünde `timedatectl` "synchronized: yes" derken saatin günlerce kayık olduğu görüldü; rapor bunu kaynakların ölçtüğü ofsetten yakalar. Saati ya da yapılandırmayı **değiştirmez**, `--check`'te de çalışır.
  Değişkenler: `hardening_time_report` (varsayılan `true`), `hardening_time_max_offset_seconds` (varsayılan `5`). Testler: `test_time_report.py`, `test_time_tasks.py`.
- README (TR/EN): **"Ne yapmaz (kapsam sınırları)"** bölümü: alan bazlı tablo; "bilerek" (belgeli karar) ile "henüz yapılmadı" ayrımı. Madde numaralı eşleme sonradan `docs/cis-esleme.md` olarak eklendi.

### Düzeltildi
- `hardening_time`: kaynaklar seçilmemişken (`*` yok; `~` çok değişken, `?` seçilemez) chrony'nin ölçtüğü ofset artık "kesin kayma" diye yazılmaz. Gerçek VM'de snapshot dönüşünde saat ~8 gün geride iken kaynaklar `~` idi ve ofset yalnızca ~9,2 sn görünüyordu; rapor "~9.2 sn kayık" diyordu. Şimdi "bu değere güvenilmez" der ve **sunucu saatini kontrol makinesinin saatiyle de karşılaştırır** (`date +%s`, en az 30 sn eşik; kontrol makinesinin saati de yanlış olabilir, mesaj bunu söyler). Saat dilimi hatası (`now(utc=true).timestamp()` 3 saat kaydırıyordu) gerçek VM'de yakalandı ve testi eklendi.

## [0.2.2] - 2026-10-17

Denetim ve firewall tarafında iki davranış iyileştirmesi ve belge ağırlıklı bir sürüm. Varsayılan davranışlar korunur: yeni özellik opt-in
(`hardening_ufw_prune_ssh`, varsayılan `false`), yeni çıktılar yalnızca uyarıdır. Dikkat edilecekler: (1) `hardening_auditd` kuralları artık
auditd başlar başlamaz yükler (eskiden play sonunda); (2) `harden` çıktısında iki yeni uyarı görünebilir (ufw'de `allow_from`'da olmayan SSH kuralı,
auditd'den önce başlamış süreçler); (3) `component.yml` `vars` listesine bir bool değişken eklendi (`sshpocket_api` değişmedi).

### Eklendi
- `hardening_ufw`: `hardening_ssh_allow_from`'dan çıkarılan ağın SSH kuralı artık **fark ediliyor**. Eskiden rol yalnızca kural ekliyordu; çıkarılan ağın kuralı firewall'da kalıyor, sunucu değişkende yazandan daha açık oluyordu. Varsayılan davranış yalnızca **uyarır**; `hardening_ufw_prune_ssh: true` ile siler (yalnızca bu rolün yazdığı biçimdeki SSH kuralları; kontrol makinesinin adresini kapsayanlara, `extra_allow`'dakilere dokunmaz; `allow_from` boşsa ya da adres bilinmiyorsa silmez; silmeden sonra eksik kural varsa `ufw enable`'dan önce durur). Karar mantığı `roles/hardening_ufw/files/stale_ssh_rules.py`. Testler: `test_ufw_stale_rules.py`, `test_ufw_prune_tasks.py`.
- `hardening_auditd`: `harden` sırasında **salt okunur** bir uyarı: auditd'den ÖNCE başlamış ve yeniden başlatılmamış programları listeler (denetlenmezler; örn. `sshd`, `cron`, `rsyslogd`). Davranışı değiştirmez, `--check`'te de çalışır; auditd kurulu değilse sessizdir. Test: `test_auditd_unaudited.py`.
- `docs/known-issues.md`: sertleştirmenin meşru kullanımları bozabileceği yerler (ufw+Docker, SSH yönlendirme, mail sunucusu kaldırma, umask vb.) ve her biri için kaçış değişkeni ya da "anahtar yok" notu. Birçok satır Docker LAB'ında denendi; denenemeyenler ⚠️ olarak işaretli.
- auditd kapsamı için tasarım notu: `docs/design/auditd-kapsam.md` (kod yok). Test VM'inde ölçülen üç bulgu: kurallar play sonunda yükleniyor, auditd'den önce başlayan süreçler denetlenmiyor, `time-change` kuralı chrony'yi (`clock_adjtime`) kapsamıyor.
- Zaman senkronizasyonu rolü için tasarım notu: `docs/design/zaman-ntp.md` (kod yok; seçenekler, değişkenler, riskler, açık sorular).
- Proxmox VE hostu için **işlevsiz iskelet** ve tasarım notu: `docs/design/proxmox-host.md`, boş roller `hardening_pve_firewall` ve
  `hardening_pve_access`, `hardening_preflight/tasks/platform.yml`. `harden.yml` bunlara bağlı değil; yanlışlıkla çağrılırsa durur.
  Davranış değişmez.

### Düzeltildi
- `hardening_auditd`: denetim kuralları artık auditd başladıktan **hemen sonra** yükleniyor (handler yerine görev; `auditctl -l` ile kural yoksa da yeniden yüklenir). Eskiden kurallar play sonunda yükleniyordu; test VM'inde auditd başlangıcından 652 sn sonra, yani `fail2ban`/`aide`/`ufw`/`ssh` değişiklikleri izlenmiyordu. Davranış tek yönlü iyileşir. Test: `test_auditd_rules_order.py`.

## [0.2.1] - 2026-10-17

sshpocket ile gerçek çalıştırmalarda çıkan sorunların düzeltildiği ve ansible-core 2.24'e hazırlanan sürüm. Davranış değişikliği: doğrudan
`ansible-playbook` ile çalıştıranlar için `hardening_scan_dir` varsayılan konumu artık kullanıcı klasörüdür (#37, aşağıda); sshpocket üzerinden
çalıştıranlar etkilenmez.

### Düzeltildi
- Playbook'lar (`harden`, `audit`, `rollback`) artık yalnızca envanterde **var olan** `hardening` / `ubuntu` gruplarını hedefler (#35): sshpocket'in
  ürettiği yalnız-`hardening` envanterinde her çalıştırmada çıkan `Could not match supplied host pattern, ignoring: ubuntu` uyarısı kalktı.
  Eski `ubuntu` grubu hâlâ kabul edilir (davranış değişmez); hiçbiri yoksa `hardening` için tek uyarı verilir.
- ansible-core 2.24 hazırlığı (#36): fact'ler artık `ansible_facts['distribution']`, `ansible_facts['distribution_version']` ve
  `ansible_facts['getent_passwd']` ile okunur (`hardening_preflight` OS denetimi, `hardening_ssh` anahtar kontrolü).
  2.24'te üst düzey `ansible_distribution` / `getent_passwd` tanımsız olacağından bu erişim kaybı korumaları kırılırdı.
  `ansible.cfg` artık `inject_facts_as_vars = False` ayarlar (2.21'deki `DEPRECATION WARNING` kalkar); testler de bunu zorlar.

### Değişti
- **Davranış değişikliği** (#37): `hardening_scan_dir` verilmezse `audit.yml` çıktıyı artık paketin `scans/` klasörüne değil **kullanıcı klasörüne**
  yazar: `$XDG_DATA_HOME/linux-hardening/scans`, yoksa `~/.local/share/linux-hardening/scans` (uygulama dizini ve `scans/` 0700; `<host>`/`<tarih>` 0700,
  dosyalar 0600). Gerekçe: rapor hassas veri içerir, paket klasörü USB/paylaşımlı olabilir. sshpocket üzerinden çalıştırınca değişen bir şey yok
  (sshpocket değeri zaten kendi kullanıcı klasörüne yönlendirir). Doğrudan `ansible-playbook` kullananlar: eski çıktılar repodaki `scans/` içinde
  kalır; eski konumu istiyorsan `-e hardening_scan_dir=$PWD/scans` ver. HOME/XDG tanımsız ve değer verilmemişse playbook durur.
- `hardening_ssh_allow_from` için görünür uyarı (#39): sunucuya bağlanabileceğin **tüm** ağları yaz (VPN + LAN + ...); ufw yalnızca bu ağlardan
  SSH'a izin verir, yalnızca VPN yazılırsa LAN'dan SSH kesilir ve geri alma güvenlik ağı bunu yakalamaz. README (TR/EN), HOWTO,
  `docs/component-vars.md` ve `component.yml` (`preview`/`apply` `warnings`, değişken açıklaması); `check-consistency.py` uyarının yerinde olduğunu denetler.
- `component.yml` / `component.json` `invoke.append` yalnızca `--ask-become-pass` içerir (#38). `-i` ve `--limit` çıkarıldı: sshpocket
  çalıştırıcısı `-i`, `--limit` ve `-e @dosya`'yı kendisi ekler (paket standardı §14 madde 7) ve `invoke.append` içindekileri zaten atlıyordu,
  yani davranış değişmez. `scripts/check-consistency.py` bu bayrakları `cmd` ve `invoke.append` içinde yasaklar.

## [0.2.0] - 2026-10-16

sshpocket paket standardı v1 ile uyumlu sürüm: pakette artık makine-okunur `component.json` var. Davranış
değişikliği yalnızca `hardening-rollback status` çıktısı ve `component.yml` biçimi (alanlar eklemeli, ad listesi
biçimi `vars` için hâlâ okunur).

### Eklendi
- **sshpocket paket standardı v1 uyumu (#30):** `component.json` (`component.yml`'den `scripts/make-component-json.py` ile türetilir,
  imzalı pakete girer), `runner: ansible`, `name`/`description`, eylem başına `confirm` (`apply`, `rollback_disarm`,
  `rollback_now` için `type-server-name`) ve `warnings`. `invoke` yer tutucuları sshpocket doğrulayıcısının biçimine
  (`<inventory>`, `<server>`) getirildi; `-e @<değişken dosyası>` kaldırıldı (runner: ansible için sshpocket verir).
  `release.sh` paketteki `component.json`'u (id/version) denetler.
- `rollback_status` makine-okunur sonuç satırı: `SSHPOCKET_RESULT linux-hardening.rollback_status installed=… armed=… timer=… remaining_seconds=… timeout_seconds=…`
  (Ansible çıktı biçiminden bağımsız; betik kurulu değilken de aynı anahtarlar). `component.yml` `outputs` ile bildirir (#28).

### Değişti
- `hardening-rollback status` artık serbest biçimli `list-timers` satırı yerine tek sonuç satırı yazar; `armed` dosyası bitiş zamanını (epoch) taşır.
- `scripts/release.sh`: PyYAML yoksa çözümü söyler; repodaki `.venv`'i kendiliğinden kullanır, `LH_PYTHON` ile başka Python seçilebilir.

## [0.1.0] - 2026-10-10

İlk sürüm: Ubuntu 26.04 LTS için Ansible tabanlı sertleştirme ve makine-okunur bileşen sözleşmesi.

### Eklendi
- Roller: `hardening_base`, `hardening_auth`, `hardening_kernel`, `hardening_auditd`, `hardening_fail2ban`,
  `hardening_aide`, `hardening_ufw`, `hardening_ssh`; ön kontrol `hardening_preflight`.
- `playbooks/audit.yml` (Lynis taraması, `summary.json`), `playbooks/harden.yml`.
- Erişim kaybı korumaları: `hardening_ssh_allow_from` zorunlu, kaynak IP ve root kontrolü, uygulama sonrası
  bağlantı doğrulaması.
- **Hedef taraflı geri alma güvenlik ağı** (`hardening_rollback`): ufw/ssh'tan önce önceki durum yedeklenir ve
  kalıcı bir systemd zamanlayıcısı kurulur; doğrulama başarılıysa disarm, başarısızsa ya da kontrol kaybolursa
  (kontrol makinesi ölür, sunucu yeniden başlar) sunucu **kendini önceki duruma döndürür** (silmez, geri yükler).
  `playbooks/rollback.yml` (`status`, `--tags disarm`, `--tags now`). Tasarım: `docs/design/rollback-timer.md`.
- `component.yml` (sshpocket sözleşmesi; `rollback_status/disarm/now` eylemleri dahil), `VERSION`, hash'li
  `requirements.txt`, `docs/RELEASING.md`, `scripts/release.sh`.
- CI (7 kontrol), 16 test dosyası, Dependabot, `SECURITY.md`, katkı rehberi ve şablonlar, `README.en.md`.

### Değişti
- `hardening_*` varsayılanları rol `defaults/` dosyalarına taşındı.
- `hosts: "hardening:ubuntu"` (genel grup).
- fail2ban `ignoreip` varsayılanı `127.0.0.1/8 ::1` + yalnızca kontrol makinesi adresi.

### Kaldırıldı
- `hardening_ssh_port` (port değiştirme desteklenmiyor; ufw kuralı gerçekten dinlenen porttan yazılır).

[Yayımlanmamış]: https://github.com/syhgorath/linux-hardening/compare/v0.7.1...HEAD
[0.7.1]: https://github.com/syhgorath/linux-hardening/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/syhgorath/linux-hardening/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/syhgorath/linux-hardening/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/syhgorath/linux-hardening/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/syhgorath/linux-hardening/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/syhgorath/linux-hardening/compare/v0.2.2...v0.3.0
[0.2.2]: https://github.com/syhgorath/linux-hardening/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/syhgorath/linux-hardening/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/syhgorath/linux-hardening/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/syhgorath/linux-hardening/releases/tag/v0.1.0
