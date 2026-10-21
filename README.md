# linux-hardening

🇹🇷 Türkçe · 🇬🇧 [English](README.en.md)

Ansible ile Linux sunucu sertleştirme (hardening). Rolleri tek repoda tutar; her dağıtım/sürüm için
destek açıkça listelenir, desteklenmeyen sistemde çalışmayı durdurur.

**Şu an desteklenen:** Ubuntu 26.04 LTS (hedef: CIS Level 1 Server yaklaşımı).
Başka sürüm/dağıtım ekleme yolu açık: bkz. [docs/SUPPORT.md](docs/SUPPORT.md).

> **Durum (0.x):** Ubuntu 26.04.1 LTS test VM'inde **canlı doğrulandı**: temiz sunucuda ilk kurulum, ikinci
> koşuda `changed=0`, `--check` (`failed=0`), erişim kaybı korumaları ve geri alma güvenlik ağı (doğrulama
> başarısızlığı, kontrol makinesinin ölmesi, sunucunun yeniden başlaması). Lynis hardening index 77, uyarı 0.
> **Doğrulanmayanlar:** tek bir VM/yapılandırma dışı sunucular, gerçek ağ düzeyi kesinti, Raspberry Pi/Proxmox,
> tam CIS Benchmark uyumu (bilerek "yaklaşım"). Önce test sunucusunda deneyin, snapshot alın.

## Akış
1. `playbooks/audit.yml` — baseline tarama (Lynis)
2. `playbooks/harden.yml --check --diff` — ne değişecek, önce gör
3. `playbooks/harden.yml` — uygula (önce snapshot/yedek al)
4. `playbooks/audit.yml` — tekrar tara, öncesi/sonrası karşılaştır

## Inventory grubu
Sunucuları inventory'de **`hardening`** grubuna yazın (dışarıdan üretilen inventory'ler de bunu kullanabilir).
Eski **`ubuntu`** grubu geçiş için hâlâ kabul edilir. Desteklenen sistem/sürüm kontrolü grup adıyla değil,
`hardening_preflight` ile yapılır.

> **2FA uyarısı:** `hardening_ssh_kbdinteractive: true` yazmak yalnızca bir anahtarı çevirir. Sunucuda PAM'ın
> 2FA'yı (örn. `libpam-google-authenticator`) ayrıca yapılandırılması gerekir; yanlışsa erişim kesilir. Açıkken
> sshd `AuthenticationMethods publickey,keyboard-interactive` ile (anahtar VE PAM istemi) çalışır; böylece
> `PasswordAuthentication no` iken PAM üzerinden **tek başına parola girişi** açılmaz. Bu durumda bağlantı doğrulaması
> yalnızca SSH banner'ını sınar (2FA istemi otomatik cevaplanamaz). Önce test sunucusunda deneyin.

## Başlangıç
```
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.txt   # hash'li, Python >= 3.12
cp inventory/hosts.example.yml inventory/hosts.yml   # kendi makinelerini yaz
source .venv/bin/activate
ansible-playbook playbooks/audit.yml
```

Ayrıntılı kullanım, sudo/üretim notları ve sorun giderme: **[HOWTO.md](HOWTO.md)**.
Alınan kararlar ve istisnalar: [docs/decisions.md](docs/decisions.md).
Canlı doğrulama kayıtları: [docs/verification-log.md](docs/verification-log.md). Yol haritası: [docs/ROADMAP.md](docs/ROADMAP.md).

> **`hardening_ssh_allow_from` zorunludur** (varsayılanı bilerek boş). Boşsa, geçersizse ya da Ansible'ın bağlandığı
> kaynak IP bu ağlarda değilse `harden.yml` firewall/SSH'a dokunmadan durur. Ayrıca root olarak bağlanılamaz.
> Örn: `-e '{"hardening_ssh_allow_from": ["192.168.1.0/24"]}'`
>
> **Yalnızca VPN yazma:** listeye sunucuya **bağlanabileceğin tüm ağları** yaz (VPN + LAN + ...). ufw yalnızca bu ağlardan SSH'a
> izin verir, gerisini keser; koruma ise yalnızca *şu anki* bağlantının kaynağını denetler. Yalnızca VPN yazarsan LAN'dan SSH
> zaman aşımına uğrar (ping/ARP çalışır). Geri alma güvenlik ağı bunu yakalamaz: doğrulama kontrol makinesinden, yani çalışan
> yoldan yapılır.
>
> Önce test sunucusunda deneyin, snapshot alın, `--check --diff` ile bakın.

## Birden fazla sunucu

Web, Docker, Redis gibi farklı sunucuları farklı ayarlarla sertleştirmek için çalışan örnek: [examples/](examples/README.md) (`group_vars` ve sshpocket için sunucu başına değişken dosyası). Ayrıntı: [HOWTO.md](HOWTO.md#7c-birden-fazla-sunucu-farklı-sertleştirme).

## Ne yapmaz (kapsam sınırları)

Bu proje **tam CIS Benchmark uyumu iddia etmez**: hedef "Level 1 Server *yaklaşımı*". Madde numaralı eşleme (Level 1 Server) [docs/cis-esleme.md](docs/cis-esleme.md) dosyasında (Debian 13 ve Proxmox notları: [docs/cis-esleme-debian.md](docs/cis-esleme-debian.md)); aşağıdaki tablo ise madde değil **alan** bazlıdır ve yalnızca kodda
doğrulanmış sınırları listeler. "Bilerek" yazılanlar belgeli kararlardır; diğerleri **henüz yapılmadı**, atlandığı anlamına gelmez. Eksik bir alan görürseniz issue açın.

| Alan | Durum | Not |
|---|---|---|
| SSH portunu değiştirmek | Bilerek yok | ufw kuralı sshd'nin gerçekten dinlediği porttan yazılır ([decisions.md](docs/decisions.md)) |
| Otomatik yeniden başlatma | Bilerek yok | Otomatik güvenlik güncellemesi açılır, reboot **yok** ([HOWTO.md](HOWTO.md)) |
| Kullanıcı, parola, anahtar yönetimi | Tasarım gereği yok | Kullanıcıyı siz oluşturursunuz; rol yalnızca parola girişini kapatmadan önce `authorized_keys`'in dolu olduğunu doğrular |
| Uygulama sertleştirmesi (nginx, MySQL vb.) | Kapsam dışı | Yalnızca işletim sistemi |
| Başka dağıtım/sürüm | Şimdilik yok | Yalnızca Ubuntu 26.04; Raspberry Pi/Proxmox planlı ([SUPPORT.md](docs/SUPPORT.md)) |
| Geri alma | Kısmi | sshd drop-in, ufw ve (faillock açıksa) PAM geri alınır; paketler, sysctl, auditd, fail2ban, AIDE geri alınmaz |
| Bölüm/bağlama seçenekleri (`/tmp`, `nodev`, `noexec`, `hidepid`) | Henüz yok | |
| Önyükleyici (GRUB parolası, `audit=1`) | Henüz yok | `audit=1` için tasarım notu: [auditd-kapsam.md](docs/design/auditd-kapsam.md) |
| AppArmor profilleri | Henüz yok | |
| Günlük yönetimi (rsyslog, journald, logrotate, uzak günlük) | Henüz yok | |
| `cron`/`at` kısıtları, `sudo` yapılandırması | Kısmi | Yalnızca cron dosya/dizin **izinleri** ve `sudoers.d` ayarı (`use_pty`, `logfile`, `timestamp_timeout`); `cron.allow`/`at.allow` oluşturulmaz, `su` kısıtlanmaz. `sudoers` değişimleri ayrıca auditd ile **izlenir** |
| IPv6'yı kapatmak | Henüz yok | |
| Core dump | Kısmi | Yalnızca `fs.suid_dumpable = 0`; `systemd-coredump` ayarı yok |
| Kullanılmayan servis/paket kaldırma | Kısmi | Yalnızca `postfix`/`courier-*` kaldırılır; avahi, cups vb. yok |
| Nadir dosya sistemi modülleri (`cramfs`, `udf`, `squashfs`…) | Henüz yok | Yalnızca `dccp`, `sctp`, `rds`, `tipc` ve `usb-storage` engellenir |
| SUID/SGID envanteri | Henüz yok | |
| AIDE zamanlanmış kontrol | Henüz yok | Yalnızca ilk veritabanı üretilir; zamanlama paket varsayılanıdır (doğrulanmadı) |
| Zaman senkronizasyonu | Kısmi | Yalnızca salt okunur rapor (`hardening_time`: saat kayması uyarısı); chrony yapılandırılmaz. Tasarım notu: [zaman-ntp.md](docs/design/zaman-ntp.md) |
| Denetim (auditd) kapsamı | Sınırlı | 6 kural grubu (`identity`, `scope`, `sshd`, `logins`, `time-change`, `modules`); `-e 2` yok; komut yürütme/dosya silme izlenmez; auditd'den **önce** başlamış süreçler yeniden başlatılana kadar denetlenmez |
| fail2ban | Sınırlı | Yalnızca `sshd` jail |

Bilinen çakışmalar (sertleştirmenin meşru kullanımları bozabileceği yerler): [docs/known-issues.md](docs/known-issues.md).

## Dikkat: davranışı değiştiren ayarlar

`harden` bir sunucuya uygulanınca aşağıdakiler **varsayılan olarak açıktır** ve meşru bir kullanımı bozabilir. Sunucu türüne göre `group_vars`/`host_vars` ya da `-e` ile kapatın. Tam liste ve kaçış yolları: [docs/known-issues.md](docs/known-issues.md).

| Ayar (varsayılan) | Ne bozabilir | Kapatma |
|---|---|---|
| `ufw`: gelen trafik `deny` | `hardening_ssh_allow_from` ve `hardening_ufw_extra_allow` dışındaki her şey (web, Redis, izleme) kapanır. Docker'ın yayınladığı portlar ufw'yi **atlar** | `hardening_ssh_allow_from` (tüm bağlantı ağlarını yaz), `hardening_ufw_extra_allow` |
| `hardening_ufw_routed_deny` (açık) | ufw ile yönlendirme/NAT/köprü yapan, Docker'lı sunucularda konteyner trafiği durabilir | `false` |
| `base`: `postfix`/`courier` kaldırılır, `dma` kurulur | Yerel posta sunucusu bekleyen uygulama bozulur | `--skip-tags base` (tüm rolü atlar) |
| `base`: `usb-storage` kapalı; `kernel`: `cramfs`, `hfs`, `jffs2`, `firewire-core`, `atm`, `can`, `dccp`, `sctp`, `rds`, `tipc` yüklenemez | USB diske yedek, bu dosya sistemi/protokolü kullanan uygulama çalışmaz | `--skip-tags kernel,base` |
| `kernel`: `route_localnet=0` | `localhost`'a DNAT yapan düzenler (bazı Kubernetes `NodePort`) bozulur | `--skip-tags kernel` |
| `ssh`: `DisableForwarding`, `MACs` zayıf liste, `MaxStartups 10:30:60` | Unix soket yönlendirme, çok eski istemciler, çok paralel SSH bağlantısı | `hardening_ssh_allow_tcp_forwarding=local` (yönlendirme), diğerleri için `--skip-tags ssh` |
| `hardening_kernel_extra_sysctl` (açık) | `kernel.sysrq=0`: VM konsolundan SysRq ile acil yeniden başlatma kullanılamaz; `net.core.bpf_jit_harden=2`: eBPF yoğun iş yüklerinde küçük performans bedeli | `false` |
| `hardening_tmp_noexec` (açık) | `/tmp`'e `nodev,nosuid,noexec`: bu dizinden doğrudan çalıştırma kapanır; `/tmp`'ten ikili çalıştıran uygulamalar (PHP/Java/Node işleri, bazı paket betikleri) bozulabilir. Ansible etkilenmez | `false` (yazılmış drop-in elle silinir) |
| `hardening_shm_noexec` (açık) | `/dev/shm`'ye `nodev,nosuid,noexec` (`/etc/fstab` satırı); paylaşımlı bellekten çalıştıran uygulamalar bozulabilir | `false` (yazılmış fstab satırı elle silinir) |
| `hardening_pam_tmpdir` (açık) | `libpam-tmpdir`: `$TMPDIR` artık `/tmp` değil (`/tmp/user/<uid>`); `/tmp`'i sabit varsayan betikler etkilenebilir | `false` |
| `hardening_apt_listchanges` (açık) | `apt-listchanges` kurulur; `apt` yükseltmelerinde değişiklik notları (onaysız, e-postasız) yazdırılır; çıktıyı ayrıştıran betikler fazladan metin görebilir | `false` (kurulu paket kaldırılmaz) |
| `hardening_disable_apport` (açık) | Ubuntu çökme raporları toplanmaz | `false` |
| `hardening_disable_update_notifier_motd` (açık) | Oturum açılışındaki güncelleme iletisi yenilenmez | `false` |
| `hardening_su_restrict` (kapalı) | Açılırsa `su` yalnızca `hardening_su_group` üyelerine açılır; varsayılan boş `sugroup` ile `root` dışında kimse `su` yapamaz (`sudo`, ssh etkilenmez) | `false` (yazılmış satır elle silinir) |
| `hardening_sudo_enabled` (açık) | `use_pty`: arka plana atılan `sudo` süreçleri oturum kapanınca takılabilir | `false` |
| `hardening_files_enabled` (açık) | İzinler yalnızca **sıkılaşır**; bu dosyalara başka kullanıcıyla erişen betikler bozulabilir | `false` |

**Varsayılan KAPALI, bilinçli açılacaklar:** `hardening_pam_faillock` (hesap kilitleme: `deny` yanlış parolada hesap `unlock_time` boyunca kilitlenir; sudo/su/konsol, SSH anahtarı etkilenmez; geri alma güvenlik ağı açık olmalı), `hardening_pam_pwhistory_remember` (parola geçmişi: `N > 0` ise son N parola yeniden kullanılamaz; yalnızca parola DEĞİŞTİRMEYİ etkiler, girişi değil; `enforce_for_root` kapalıyken root'un `chpasswd`'si engellenmez), `hardening_time_makestep` (büyük saat kaymasını düzeltir; saati SIÇRATIR: sertifika, cron ve günlük sırası etkilenebilir), `hardening_docker_enabled` (salt okunur Docker raporu), `hardening_docker_daemon_manage` (`daemon.json` birleştirme), `hardening_docker_no_new_privileges` / `hardening_docker_userland_proxy_off` / `hardening_docker_icc_off` (`daemon.json`'a CIS Docker 2.15 / 2.17 / 2.2 anahtarı; yalnızca `daemon_manage` açıkken; `icc=false` mevcut köprüye yalnızca konteynerler durdurulup Docker yeniden başlatılınca işler), `hardening_docker_restart` (Docker yeniden başlar, `live-restore` yoksa konteynerler durur), `hardening_kernel_disable_ipv6_ra` (IPv6'sını yalnızca yönlendirici duyurusundan alan sunucuyu keser), `hardening_auditd_grub_audit` (`audit=1`, yeniden başlatma gerekir, geri alma kapsamında değil), `hardening_auditd_restart_services` (servis kesintisi), `hardening_ufw_prune_ssh` (kural siler).

**Varsayılan KAPALI (Grup 2), sunucu türüne göre açılır:** `hardening_disable_coredump`, `hardening_shell_timeout_seconds` (`TMOUT`), `hardening_password_inactive_days`, `hardening_log_file_permissions` ve **`hardening_remove_legacy_clients`** (`telnet`/`ftp` kaldırma). Sonuncusu için not: bu programlar port açmaz (güvenlik riski yaratmaz), ama `telnet host port` ile port yoklayan betikleri ve `ftp` kullanan yedek akışlarını **kırar**; kaldırma `apt remove` ile yapılır (`purge` değil), geri alma `apt install`dır. **`ubuntu-standard` metapaketi de kalkar** (bir ftp istemcisi ister, yoksa apt bir istemciyi kaldırınca öbürünü kurar); dosya içermez, ama `apt autoremove` ondan gelen otomatik paketleri aday gösterebilir. Ayrıntı: [docs/ROADMAP.md](docs/ROADMAP.md). **Henüz kodlanmadı:** `/tmp` ve `/dev/shm` `noexec`, `su` kısıtı, kullanıcı dot dizinleri (tasarım gerekir).

## Testler
`test/` altındaki testler her PR'da CI'da (`.github/workflows/ci.yml`) çalışır; yerelde:

```bash
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.txt
PATH="$PWD/.venv/bin:$PATH" test/run-all.sh          # hepsi
PATH="$PWD/.venv/bin:$PATH" test/run-all.sh summary  # adı "summary" içerenler
```

| Test | Neyi korur |
|---|---|
| `test_lint.sh` | `--syntax-check`, `yamllint --strict`, `ansible-lint` (0 bulgu), shellcheck |
| `test_access_guards.sh` | `allow_from` boş/geçersiz/kaynak dışı, `SSH_CONNECTION` yok, root, IPv4/IPv6 |
| `test_expressions.py` | sshd portlarının `ss` çıktısından türetilmesi, efektif fail2ban `ignoreip` |
| `test_templates.py` | Şablonların varsayılan çıktısı (golden dosyalar) ve güvenli varsayılanlar |
| `test_scan_dir.py` | Tarama dizini varsayılanı kullanıcı klasörüdür (HOME/XDG), paket klasörüne yazılmaz, izinler 0700/0600, HOME yoksa durur |
| `test_summary.py` | `summary.json` alanları, `null` davranışı, dizin/dosya izinleri |
| `test_tags_and_hosts.sh` | `--tags` ile preflight/korumaların atlanmaması, `hardening`/`ubuntu` grubu seçimi ve olmayan grup için uyarı çıkmaması |
| `test_facts_namespace.sh` | Fact'ler yalnızca `ansible_facts[...]` ile okunur (`INJECT_FACTS_AS_VARS=False` altında OS denetimi), üst düzey fact adı yasağı |
| `test_docker_scripts.py` | Docker karar betikleri (gerçek `docker ps`/`daemon.json` biçimleriyle): yayınlanan port raporu, docker grubu, TCP API, `daemon.json` birleştirme (mevcut ayarları silmez, bozuk JSON'a dokunmaz, idempotent) |
| `test_docker_tasks.py` | `hardening_docker` görevleri uçtan uca (sahte okuma çıktısı + gerçek betik): varsayılan kapalı, Docker yoksa atla, okumalar salt okunur, yedekli yazma, auditd'de yalnız var olan yollar |
| `test_examples.py` | `examples/` tutarlılığı: gerçek `ansible-inventory` ile `group_vars` birleşimi, sshpocket dosyalarıyla aynı; yalnız var olan değişkenler, ek ufw kuralları doğrulama kalıbına uyar, DB portu açılmaz |
| `test_usb_storage.py` | `hardening_disable_usb_storage`: varsayılan true; false iken kural dosyası silinir, USB depolama tekrar kullanılabilir |
| `test_ansible_cfg.py` | `ansible.cfg` ssh canlılık seçenekleri (ölü bağlantıda takılmama), varsayılan `ssh_args` ezilmez |
| `test_apt_listchanges.py` | `apt-listchanges`: kurulum + bloklamayan yapılandırma (`confirm=false`, `frontend=text`), idempotent, `warn_if` yok |
| `test_pam_faillock.py` | hesap kilitleme: korumalar (güvenlik ağı kapalı/armed değil → durur), yığın SIRASI (gerçek Ubuntu çıktısı ve bozuk varyantlar), `faillock.conf` satırları, rescue geri alma |
| `test_rpi_platform.py` | Raspberry Pi platformu: algılama, `raspberry-pi` reddi (Pi değilse), `generic` + Pi notu, `usb-storage` gevşetmesi, Proxmox gevşetmesinin Pi'yi kapsamaması |
| `test_pve_report.py`, `test_pve_report_tasks.py` | Proxmox VE host durum raporu (`playbooks/pve-report.yml`): gerçek Proxmox 9.2 değerleriyle karar mantığı + görev zinciri, salt okunur, harden.yml'e bağlı değil |
| `test_pve_firewall_plan.py`, `test_pve_firewall_tasks.py` | Proxmox güvenlik duvarı (`playbooks/pve-firewall.yml`): karar betiği (küme, allow_from, kontrol makinesi, kullanıcı dosyası reddi), görev sırası (enable 0 → compile → enable 1), apply kapısı, ön izleme zinciri; `test_rollback_script.sh` bölüm 10: cluster.fw yedek/geri alma |
| `test_pwhistory.py` | parola geçmişi (`pam_pwhistory`): pam-auth-update profili (sıra), `pwhistory.conf` satırları gerçek dosyada, rescue ile geri alma, varsayılan kapalı |
| `test_tmp_plan.py`, `test_tmp_noexec_tasks.py` | `/tmp` ve `/dev/shm` noexec UYGULAMA: plan kararları (yalnız ayrı+tmpfs, fstab satırı ezilmez) + gerçek `copy`/`lineinfile` zinciri, idempotens |
| `test_tmp_report.py`, `test_tmp_tasks.py` | `/tmp` ve `/dev/shm` bağlama seçenekleri raporu (CIS 1.1.2): `nodev`/`nosuid`/`noexec`/ayrı bağlama kararları + gerçek görev zinciri, salt okunur |
| `test_root_env_report.py`, `test_root_env_tasks.py` | root ortamı raporu (CIS 5.4.2, PATH/umask): `PATH` ve `umask` kararları (betik) + gerçek görev zinciri, salt okunur, kapatılabilir |
| `test_aide_timer.py` | AIDE günlük zamanlayıcısı (CIS 6.3.2): `dailyaidecheck.timer` açık+başlatılmış, AIDE işi değişmez, `warn_if` yok |
| `test_su_restrict.py` | `su` kısıtı (CIS 5.2.7): gerçek `/etc/pam.d/su` üzerinde `lineinfile` (`pam_rootok` sonrası, çoğalmaz), geçersiz grup adı reddedilir, varsayılan kapalı |
| `test_lynis_small.py` | Lynis'ten çıkan küçük maddeler: ek sysctl (şablon varyantları) ve `libpam-tmpdir` (gerçek `when`), `warn_if` yok |
| `test_cis_group2.py` | Grup 2 (hepsi varsayılan kapalı): core dump, `telnet`/`ftp` kaldırma (`remove`, purge yok), `TMOUT` ve `INACTIVE` sınırları ve idempotensi, mevcut hesaplara dokunulmaması |
| `test_cis_group1.py` | apport ve `update-notifier-motd` kapatma (olmayan birime dokunulmaz, kendi değişkeniyle kapanır, `lineinfile` idempotent) ve SUID/SGID özetinin salt okunur kalması |
| `test_files_role.py` | dosya izinleri gerçek `ansible-playbook` ile geçici ağaçta: yalnızca sıkılaşır (0600 gevşemez), olmayan dosya oluşturulmaz, sembolik bağ izlenmez, `--check` değiştirmez, ikinci koşu `changed=0` |
| `test_sudo_role.py` | sudoers drop-in: `visudo -cf` ile doğrulanır (üretilen içerik gerçek `visudo` ile), `become` denemesi, başarısızlıkta temizlik, `NOPASSWD` yok |
| `test_cis_quickwins.py` | CIS kolay kazançlar: modül listeleri, ufw `routed` ilkesi, `audit=1` (gerçek `replace` modülüyle, idempotent), ssh yeniden başlatma yasağı, riskli seçeneklerin varsayılanı kapalı |
| `test_time_report.py` | zaman raporu kararı (gerçek `chronyc -c sources` biçimiyle): sağlıklı, bayat/kayık saat, servis kapalı, kaynak yok, eşik, bozuk satır |
| `test_time_tasks.py` | zaman rolü salt okunur kalır: yalnızca okuma modülleri, `--check`'te çalışır, kapatılabilir, saati değiştiren komut yok |
| `test_ufw_extra_allow.py` | ufw ek kuralları: grup ve sunucu listeleri birleşir, geçersiz girdi (14 örnek) roller çalışmadan reddedilir, iki doğrulayıcı aynı kalıpta, sshpocket değişkeni |
| `test_ufw_stale_rules.py` | ufw eski SSH kuralı kararı: ağ normalleştirme, kontrol makinesi/boş allow_from/extra_allow korumaları, eksik kural tespiti |
| `test_ufw_prune_tasks.py` | ufw silme görevlerinin yapısı: varsayılan kapalı, `--check`'te silmez, silme sonrası doğrulama ufw enable'dan önce |
| `test_auditd_unaudited.py` | auditd'den önce başlamış süreçlerin salt okunur tespiti (sahte `ps`/`systemctl` ile), çekirdek iş parçacıkları ve eşik dışarıda |
| `test_auditd_rules_order.py` | auditd kuralları servis başladıktan hemen sonra yüklenir (handler/play sonu değil), `--check`'te atlanır |
| `test_handlers.py` | Her `notify` bir handler'a bağlı |
| `test_vars_defined.py` | `group_vars` olmadan değişkenler tanımlı, güvenli varsayılanlar |
| `test_consistency.sh` | `VERSION`/`component.yml`/destek matrisi tutarlılığı (kasıtlı bozmalar yakalanır) |
| `test_rollback_script.sh` | geri alma betiği: arm/disarm/restore (önceki içeriği geri yükler, silmez), sahte komutlarla |
| `test_release_script.sh` | `scripts/release.sh`: gerçek imzalama/doğrulama, reddedilme senaryoları |
| `test_repo_hygiene.sh`, `test_ip_addresses.py` | Anahtar/token/IP sızıntısı, paket içeriği |

CI ayrıca Python 3.12/3.13/3.14'te hash'li kurulumu dener ve gerçek bir Linux'ta (`linux-smoke`) `harden.yml --check` çalıştırır.

> **Sınır:** CI canlı sunucu testi yerine geçmez; firewall/SSH değişiklikleri uygulanmaz (runner'ın kendi bağlantısını keserdi).
> Golden dosyaları bilerek değiştirirseniz: `UPDATE_GOLDEN=1 python3 -I test/test_templates.py` ve farkı PR'da inceleyin.

## Lisans

MIT, bkz. [LICENSE](LICENSE). Kullanım sorumluluğu size aittir: sertleştirme erişimi kesebilir; önce test sunucusunda deneyin.
