# Canlı doğrulama günlüğü

Bu belge, sürümün **gerçek bir sunucuda** nasıl denendiğini kayıt altına alır (PR yorumlarına dağılmış kanıtların
özeti). Hepsi 2026-10-10'da, Proxmox üzerindeki **tek bir test VM'inde** (Ubuntu 26.04.1 LTS) yapıldı. IP/anahtar
yazılmamıştır. "Test VM'i" bir üretim sunucusu değildir.

> **Kapsam uyarısı:** aşağıdakiler **tek VM / tek yapılandırma** için kanıttır. Bkz. "Doğrulanmayanlar".

## Özet
| # | Deneme | Sonuç |
|---|---|---|
| 1 | Sertleşmiş VM'e yeni rollerle `--check --diff` | `ok=44 changed=1 failed=0`; tek fark `ignoreip` (beklenen davranış değişikliği) |
| 2 | Gerçek uygulama, ardından 2. koşu | `changed=2` → **`changed=0`**; doğrulama rolü ilk kez gerçek bağlantıyla çalıştı |
| 3 | `-e ansible_python_interpreter=auto_silent` | **Hata yakalandı** (kaynak-IP denetimi anahtar sözcüğü program yolu sandı) → #18 |
| 4 | Eski `rescue` yolu bilerek tetiklendi | Çalıştı, ama sertleşmiş sunucuyu **zayıflattı** (parola girişi açık, `maxauthtries` 6) → tasarım notu |
| 5 | Yeni güvenlik ağı, başarı yolu | `armed` → `disarmed` 17 sn; 2. koşuda `changed=0` |
| 6 | **Senaryo 1:** doğrulama başarısız (yeni bağlantı reddedilir) | Sunucu **sertleşmiş kaldı** (drop-in/ufw md5 aynı) |
| 7 | **Senaryo 2:** kontrol makinesi `SIGKILL` | Sunucu ~5 dk sonra **kendini** geri aldı |
| 8 | **Senaryo 3:** `armed` iken sunucu yeniden başlatıldı | Açılışta ~5 dk sonra geri aldı |
| 9 | **Sıfırdan kurulum** (temiz snapshot) | `--check failed=0`; ilk kurulum `ok=65 changed=22 failed=0`; 2. koşu `changed=0`; Lynis 77 |

## Ayrıntılar
**4. Eski `rescue` yolu.** Engel `DenyUsers` ile (mevcut oturum açık kalır, yeni bağlantılar reddedilir). Playbook
`rescued=1` verdi, drop-in silindi, ufw kapandı. Zaten sertleşmiş sunucuda bu, başlangıçtan **daha zayıf** durum
bıraktı. Bu bulgu, "sil" yerine "önceki durumu geri yükle" tasarımının nedeni (`docs/design/rollback-timer.md`).

**6-8. Yeni geri alma güvenlik ağı** (`hardening_rollback`; kalıcı systemd zamanlayıcısı + `armed` işaret dosyası +
önceki durum yedeği):
- *Senaryo 1:* `rescued=1`, `Restore previous state` çalıştı, eski sil/kapat görevleri **atlandı**. Drop-in md5,
  ufw `user.rules` md5, `passwordauthentication no`/`permitrootlogin no`/`maxauthtries 3` **öncekiyle aynı**.
- *Senaryo 2:* `armed` görüldüğü an `ansible-playbook` `SIGKILL` ile öldürüldü, drop-in'e işaret satırı eklendi.
  Sunucu `armed=yes, timer=active` kaldı; ~5 dk sonra drop-in başlangıç md5'ine döndü, işaret silindi.
- *Senaryo 3:* `armed` + işaret → `systemctl reboot`. Açılışta `armed=yes` ve timer `enabled` korunmuştu; açılıştan
  ~5 dk sonra geri alma tetiklendi. (`systemd-run --on-active` geçici zamanlayıcısı bu senaryoda kaybolurdu;
  kalıcı unit seçiminin gerekçesi.)

**9. Sıfırdan kurulum.** Temiz snapshot'ta: (A) `--check` `failed=0`; (B) `--tags ufw,ssh` + engel → geri alma
sunucuyu tam başlangıç haline döndürdü (ufw `inactive`, drop-in yok, `user.rules` md5 aynı); (C) tam uygulama
~12 dk (çoğu AIDE ilk veritabanı), arm → doğrulama → disarm; (D) 2. koşu `changed=0`; (E) `audit.yml`: Lynis
hardening index **77**, uyarı **0**, `summary.json` doğru, izinler 0700/0600.

**10. `rollback_status` sonuç satırı (2026-10-16, #28).** Aynı test VM'inde (Ubuntu 26.04.1, gerçek systemd), `rollback.yml --tags status`
`result_format = yaml` ile: (A) **eski v0.1.0 betiği kuruluyken** playbook satır üretmiyordu → eski çıktıyı satıra çeviren geri
dönüş eklendi, canlıda `armed=no timer=inactive remaining_seconds=unknown timeout_seconds=unknown` verdi; (B) `harden.yml`
ile yeni betik kuruldu (`failed=0`); (C) `armed=no` → `remaining_seconds=unknown timeout_seconds=300`; (D) `arm` sonrası
`armed=yes timer=active remaining_seconds=297`, 20 sn sonra `273` (systemd `list-timers` "4min 31s" ≈ 271 ile uyumlu);
(E) `disarm` sonrası tekrar `armed=no timer=inactive`. Satır YAML çıktısında katlanmadan tek satır geldi.

**11. Temiz kurulumda 0.2.2 (2026-10-17).** Test VM'i snapshot'ından temiz hâle döndürüldü (auditd, fail2ban, AIDE, geri alma betiği yok; ufw kapalı). Önce VM saati ~8,27 gün geriydi:
`chronyc makestep` hiçbir şey yapmadı (kaynaklar `^?`), `systemctl restart chrony` saati birkaç saniyede düzeltti (`stepped by 714422.9 seconds`). Sonra: `--check --diff`
`ok=50 changed=17 failed=0`; tam `harden` (v0.2.2) `ok=72 changed=24 failed=0` (~12 dk, AIDE ilk veritabanı ~10 dk), uyarı yok (`DEPRECATION`/`host pattern`).
**auditd kural yükleme (P3 düzeltmesi):** auditd paketi kurulurken başladı (`DAEMON_START` 19:57:37), kurallar 19:57:44'te yüklendi, yani **7 sn** (eski tasarımda 652 sn); kurallar fail2ban (19:57:45),
AIDE (19:57:59 – 20:07:53), ufw (20:08:00) ve ssh (20:08:08) rollerinden **önce** devreye girdi (rol başına zaman damgalı kayıtla). **P1 uyarısı:** "27 program auditd'den ÖNCE başlamış" (VM yeniden açılmıştı;
`chronyd` dahil). **İkinci koşu:** `ok=67 changed=0 failed=0` (73 sn). Durum: `armed=no`, ufw aktif 2 kural, 13 audit kuralı yüklü, saat senkron.
Doğrulanmayan: eski tasarımın 652 sn değeri bu temiz kurulumda değil önceki bir denemede ölçüldü (aynı VM, farklı koşu); `audit=1` ile yeniden başlatma sonrası kapsam; tek VM.

**12. CIS kolay kazançlar, gerçek VM (2026-10-17, temiz snapshot).** Varsayılan tam `harden`: `ok=79 changed=25 failed=0`; ikinci koşu `changed=0`.
Yeni modüller (`cramfs`, `hfs`, `firewire-core`, `atm`, `can`) `modprobe` ile yüklenemiyor (`install ... /bin/false`); `secure_redirects=0`, `route_localnet=0`;
`clock_adjtime` kuralı yüklü (`-F auid>=1000 -F auid!=-1`: auditctl `unset`'i bu biçimde gösterir); ufw `DEFAULT_FORWARD_POLICY="DROP"`
(`ufw status` "disabled (routed)" yazar, çünkü `ip_forward=0`). Opt-in koşusu (`hardening_kernel_disable_ipv6_ra`, `hardening_auditd_restart_services=[cron, chrony]`,
`hardening_auditd_grub_audit`): `accept_ra=0`, iki servis yeniden başlatıldı, `/etc/default/grub` içinde `audit=1`. **Yeniden başlatma sonrası** `/proc/cmdline` içinde `audit=1`,
auditd etkin; "auditd'den önce başlamış süreç" uyarısı **23-28 programdan 1'e (`systemd`)** düştü (chronyd ve sshd artık listede değil). **Ölçülmedi:** bu süreçlerin sistem çağrılarının
gerçekten denetim günlüğüne düştüğü (yalnızca başlangıç zamanı ölçütü), `clock_adjtime` kuralının tetiklenmesi, `deny routed`'ın gerçek yönlendirmede etkisi.
Docker LAB'da (Ubuntu 26.04 konteyner) aynı kod uygulandı; `auditctl -l` konteynerde rc=255 verdiği için okuma görevi `failed_when: false` yapıldı (gerçek VM'de rc=0).

**13. SSH CIS 5.1.x seçenekleri, gerçek VM (2026-10-18).** `--tags ssh` (geri alma güvenlik ağı devrede, doğrulama sonrası `armed=no`): `ok=32 changed=2 failed=0`, ikinci koşu `changed=0`.
`sshd -T`: `disableforwarding yes`, `maxstartups 10:30:60`, `gssapiauthentication no`, `hostbasedauthentication no`, `ignorerhosts yes`, `permituserenvironment no`, `usepam yes`;
`macs` listesinden `umac-64`, `umac-64-etm`, `umac-128-etm` çıktı, `hmac-sha2-*-etm` kaldı. İstemciden: `-c aes256-ctr -o MACs=umac-64-etm@openssh.com` → "no matching MAC found";
`hmac-sha2-256-etm` ile bağlanıldı. (AEAD şifre `chacha20-poly1305` MAC kullanmadığı için MAC testi `aes256-ctr` ile zorlandı.) Unix soket yönlendirmesi denendi: dinleyici açıldı,
sunucu tarafı kanalı reddetti (`open failed`); nedenin `DisableForwarding` olduğu ayrıca ayrıştırılmadı. Varsayılanlar (`sshd -T`, OpenSSH 10.2): şifre/KEX/MAC listelerinde CBC/3DES/SHA1-KEX yok;
`maxstartups` varsayılanı `10:30:100`. **Ölçülmedi:** `MaxStartups`'ın paralel bağlantılı otomasyonda etkisi, eski istemcilerle MAC uyumu.

**14. Dosya izinleri ve sudo, gerçek VM (2026-10-18).** `--tags files,ssh,sudo`. İlk koşuda sudo rolü düştü: Ubuntu 26.04'ün varsayılanı **sudo-rs** ve `Defaults logfile` desteklemiyor
(`visudo -cf`: "unknown setting: 'logfile'"). Doğrulama (`validate`) dosyayı yazdırmadı, rescue çalıştı, **sudo bozulmadı** (`sudo -n id -u` = 0); rol `visudo --version` ile sudo-rs'i
algılayıp `logfile`ı yalnızca klasik sudo'da yazacak şekilde düzeltildi (VM'de her iki `visudo` da kurulu, `update-alternatives` sudo-rs'e işaret ediyor). Düzeltilmiş koşu: `ok=44 changed=1 failed=0`,
ikinci koşu `changed=0`. Sonuç izinler: `passwd`/`group`/`shells` 644, `shadow`/`gshadow` 640 root:shadow, `sshd_config` 600, `sshd_config.d` 700, ana bilgisayar anahtarları 600 / `.pub` 644,
`cron.d`/`cron.daily` 700, `crontab` 600, `grub.cfg` 600, `sudoers.d/60-hardening` 440; içerik `use_pty` + `timestamp_timeout=15`. **Ölçülmedi:** `use_pty`'nin arka plana atılan sudo süreçlerine
etkisi, `grub.cfg`'nin sonraki `update-grub`'da 0444'e dönüp dönmediği, `timestamp_timeout`'un sudo-rs'te gerçekten uygulandığı (yalnızca sözdizimi kabul edildi). Bir `--check` koşusunda tek seferlik
"privilege escalation prompt" zaman aşımı görüldü, iki tekrarda çıkmadı (nedeni bilinmiyor).

**15. CIS grup 1 (apport, update-notifier-motd, APT izinleri, journald), gerçek VM (2026-10-18).** `--tags base,files`: `ok=33 changed=6 failed=0`, ikinci koşu `changed=0`.
`/etc/default/apport` `enabled=0`, `apport.service` ve `update-notifier-motd.timer` maskeli, journald drop-in etkin (`systemd-analyze cat-config`: `Storage=persistent`, `Compress=yes`),
APT dizinleri 755, `sources.list.d` dosyaları ve `.gpg` anahtarları 644, `sudo` çalışıyor. **Yolda bulunan hata:** zamanlayıcı tek çağrıda (`state: stopped` + `masked: true`) maskelenince
`systemctl --failed`'te `failed (Result: resources)` ("Unit to trigger vanished") görünüyordu; durdurma ve maskeleme ayrı görevlere bölündü. Zamanlayıcı VM'de geri açılıp (`unmask`, `start`) düzeltilmiş rol
yeniden uygulandı: `masked`/`inactive`, `systemctl --failed` boş, ikinci koşu `changed=0`. SUID/SGID özeti VM'de 24 dosya (0,7 sn). **Ölçülmedi:** apport'un kapalıyken çökme davranışı,
`apt update`'in kısıtlı izinlerle etkisi (yalnızca izinler değişti).

**16. CIS grup 2 (seçenekler AÇIK), gerçek VM (2026-10-18).** `--tags kernel,base,auth,files` + hepsi açık: `ok=55 changed=9 failed=0`, ikinci koşu `changed=0`. `TMOUT=600` ve `readonly` (kabukta
`TMOUT=9` → "readonly variable"), `ulimit -c` = 0, `systemd-coredump` `Storage=none`/`ProcessSizeMax=0`, `useradd -D` `INACTIVE=45`, `/var/log` dosyalarının diğer izni kalktı (yalnız `wtmp` ve `lastlog` 0664 kaldı, bilerek),
`sudo` çalışıyor. **Yolda bulunan:** `ftp`/`telnet` paketleri kaldırılınca `/usr/bin/ftp` `update-alternatives` ile **`ftp-ssl`**e düştü (aynı komutu sağlayan başka paket); varsayılan paket listesine
`ftp-ssl` ve `telnet-ssl` eklendi. Bu da yetmedi: `ubuntu-standard` metapaketi bir ftp istemcisi ister; `apt remove` bir istemciyi kaldırınca bir ÖBÜRÜNÜ otomatik kurdu (apt geçmişi: ftp -> ftp-ssl -> ftp+tnftp,
her koşuda `changed=1`). Çözüm: `ubuntu-standard`ı aynı işlemde kaldırmak (listeye eklendi; tek `apt-get remove` işleminde hepsi gider). Mevcut hesap uyarısı gerçek veriyle çalıştı (`syhgorath` INACTIVE 45 değil, değiştirilmedi). **Ölçülmedi:** TMOUT'un gerçek boşta oturumu kapatması, core dump kapalıyken
gerçek bir çökme, günlük izinlerinin izleme ajanlarına etkisi.

**17. Üç sunuculuk senaryo, Docker/Colima mini lab (2026-10-18).** `examples/` gerçek haliyle denendi: özel Docker ağı `192.168.1.0/24`, üç systemd'li Ubuntu 26.04 konteyneri (`server1` web, `server2` Docker, `server3` Redis/günlük/yedek;
mevcut `sshpocket-lab:ubuntu26` imajı, indirme yok) + bir yabancı konteyner (`192.168.1.99`). Envanter `examples/inventory.example.yml` ile aynı gruplar, `group_vars` = `examples/group_vars`. `--skip-tags aide` ile tam `harden`:
üçünde `ok=107 changed=32 failed=0`; ikinci koşu yalnızca LAB'a özgü `augenrules` (`changed=1`). **Bağlantı matrisi (22 kontrol, 0 hata):** `server1:80` yalnızca `server2`'den açık (`server3` ve yabancıdan kapalı), `server1:3306` kimseden açık değil;
`server2:80/443` herkese açık, `8080` kapalı; `server3:6379` ve `514` yalnızca `server1`/`server2`'den açık (yabancıdan kapalı), `9100` kapalı; SSH LAN'dan açık. **`host_vars` birleşmesi:** `server3`'e
`hardening_ufw_extra_allow_host` ile `9100` (yalnız `server1`'den) eklenince grup kuralları (6379, 514) **durdu**, yeni kural eklendi. **sshpocket yolu:** `group_vars` olmadan `-e @examples/sshpocket/<sunucu>.yml` üç sunucuda da `changed=0`
(group_vars ile kurulmuş durumla aynı). **Ölçülmedi:** gerçek Redis/nginx/Docker (yalnızca port dinleyicileri), VPN, ev yönlendiricisi/ters vekil, Docker'ın yayınladığı portların ufw'yi atlaması (Docker içinde Docker kurulmadı), harici USB disk.

**18. Gerçek Docker, mini lab `hl-server2` (2026-10-18).** `docker.io` 29.1.3 (Ubuntu paketi, ~80 MB, `ports.ubuntu.com`, arm64) konteynere kuruldu; iç içe Docker için `daemon.json`'a **önceden** `storage-driver: vfs` yazıldı (overlay-on-overlay çalışmaz); `apt` servisi
başlatmadı, elle `systemctl start docker`. Alpine imajı Docker Hub'dan değil, ana makinenin Docker'ından `docker save | docker load` ile aktarıldı. Dört konteyner: `proxy` (80), `redis` (6379, bilerek yayınlandı), `db` (yayınlanmamış), `app` (`127.0.0.1:8080`).
- **ufw atlaması doğrulandı:** ufw'de yalnızca 22/80/443 vardı; `hl-other` (yabancı) `server2:6379`'a **bağlandı** (`OPEN`), `8080` (loopback) kapalıydı.
- **Rapor (`hardening_docker_enabled=true`):** `tester` docker grubunda, `redis:6379/tcp` izinli listede değil → uyarı; `proxy` (80, izinli), `app` (loopback), `db` (yayınlanmamış) uyarı DEĞİL; `live-restore` ve günlük boyutu için NOT.
- **`daemon.json` birleştirme:** mevcut `storage-driver: vfs` ve `registry-mirrors` korundu, `live-restore`, `log-driver`, `log-opts` eklendi, yedek alındı, ikinci koşu `changed=0`.
- **live-restore (önemli):** `daemon.json`'da olup çalışan daemon'a yüklenmemişken `systemctl restart docker` **tüm konteynerleri durdurdu**. `systemctl reload docker` (SIGHUP) ise `live-restore`'u konteynerler **durmadan** açtı; sonraki yeniden başlatmada konteynerler ayakta kaldı.
  Bunun üzerine rol, `daemon.json` değişince önce `reload` yapar (yalnız `hardening_docker_restart=false` iken), tam yeniden başlatma yalnız `true` iken. Rol ile baştan sona doğrulandı (live-restore kapalı → rol → `Live Restore Enabled: true`, konteynerler durmadan, sonraki restart'ta da ayakta).
- **Dosya izinleri:** `/etc/docker` 777→755, `daemon.json` 666→644; `docker.sock` `root:docker` 660, containerd soketi 660 korundu. **auditd:** var olan 10 Docker yolu için `-w ... -p wa -k docker` kuralı yazıldı (olmayan yollar atlandı).
- Yolda: ardışık dört `systemctl restart docker` systemd'in başlatma sınırına takıldı ("start of the service was attempted too often"); `systemctl reset-failed` ile çözüldü (test artefaktı; rol tek yeniden başlatma yapar).
**Ölçülmedi:** `userland-proxy`, `icc`, `no-new-privileges` seçenekleri (rolde yok), Docker'ın kendi depo sürümü (`docker-ce`), gerçek ters vekil (Traefik/nginx), `docker.sock`'a bağlanan konteyner, `DOCKER-USER` kuralları.

**19. v0.3.0 adayı: gerçek VM'de temiz kurulum (2026-10-18). İkinci koşu önce yarım kaldı, ağa dönülünce doğrulandı.** VM temiz snapshot'a döndürüldü (ufw kapalı, auditd yok, `telnet`/`ftp` kurulu, saat ~9 gün geride). `main` + sürüm commit'i, varsayılanlarla tam `harden`
(`-e @vm-vars.yml`: yalnızca `allow_from`), birinci koşu **13:28:37-13:44:11 UTC, `ok=117 changed=35 failed=0`** (~15,5 dk, AIDE ilk veritabanı ~10 dk). auditd başlangıcından kural yüklemeye **3 sn**, kurallar fail2ban ve AIDE'den önce.
- **Zaman raporu (saat 9 gün geride, `chrony` yeniden başlatılmadan önce, `--check`):** "Kaynakların ölçtüğü ofset ~9.2 sn ama hiçbir kaynak seçilmediği için bu değere GÜVENİLMEZ … Sunucu saati, kontrol makinesinin saatine göre **~9 gün 1 dk geride**". Önceki sürüm aynı durumda yalnızca "~9.2 sn kayık" diyordu (madde 15'te bulunan hata, düzeltme bu vakada doğrulandı). `chrony` yeniden başlatılınca saat düzeldi; tam koşuda `ZAMAN: chrony senkron: 5 kaynak … ofset 2 ms`.
- Tam koşu çıktısında: SUID/SGID özeti (23 dosya), "auditd'den önce başlamış 27 program" uyarısı (beklenen; varsayılan `hardening_auditd_restart_services` boş, `audit=1` kapalı).
- **İkinci koşu, ilk deneme (yarım kaldı):** 13:46'da başladı, 13:48:03'te `hardening_fail2ban : Configure sshd jail` görevinde çıktı verdi, sonra takıldı ve 14:02'de elle durduruldu (rc=143). O sırada kontrol makinesi **ağ değiştirmişti** (başka bir LAN + VPN); VM'e ping ve TCP/22 yanıt vermiyordu. Neden kesin söylenemez, hardening kaynaklı olduğunu gösteren bir kanıt yok.
  Gözlem: `ansible.cfg`'de `ServerAliveInterval`/`timeout` yoktu; ölü bağlantıda `ansible-playbook` 14 dakika takıldı (önlem: madde 20).
- **İkinci koşu, ağa dönülünce (VM'e yeniden ulaşıldı, 5 saat kesintisiz çalışıyordu, geri alma ağı `armed=no`):** 17:41-17:43 UTC, **`ok=112 changed=2 failed=0`**. Değişen yalnızca `hardening_fail2ban : Configure sshd jail` ve onun `Restart fail2ban` handler'ı.
  **Neden (doğrulandı):** jail dosyasındaki `ignoreip`, kontrol makinesinin sunucudan görünen adresini içerir (kendini banlamasın diye, tasarım gereği). Önceki yarım koşu başka bir adresten çalışmıştı; adres değişince rol dosyayı yeniden yazar ve fail2ban'ı bir kez yeniden başlatır.
  Aynı denetleyiciden `--tags fail2ban` tekrarı `changed=0`; `ignoreip` elle başka bir adresle değiştirilip rol çalıştırılınca diff yalnızca o satırı gösterdi (`-ignoreip … <eski adres>` / `+ignoreip … <denetleyici adresi>`). Yani idempotens **aynı denetleyici adresinden** geçerlidir.
- **Üçüncü tam koşu (aynı adresten, 17:47 UTC): `ok=111 changed=0 failed=0`.** Temiz kurulumda uçtan uca idempotens doğrulandı.
- İdempotens kanıtı bu sürümde ayrıca **parça parça** var: madde 12-16 (VM), madde 17 (mini lab).

**20. Ölü bağlantıda zaman aşımı (2026-10-18, mini lab).** Madde 19'daki takılmanın (14 dk) önlemi: `ansible.cfg` `ssh_extra_args = -o ServerAliveInterval=15 -o ServerAliveCountMax=3`. Ölçüm: `hl-server1`'de `sleep 600` görevi sürerken konteynerde `iptables -I INPUT/OUTPUT 1 -j DROP`
ile **sessiz** kesinti (RST yok). Ayar yokken (`ANSIBLE_SSH_EXTRA_ARGS=" "`) ansible **153 sn** sonra ("Connection timed out during banner exchange", UNREACHABLE), ayarla **58 sn** sonra pes etti. Fark gerçek ama bu simülasyonda sonsuz takılma
görülmedi; 14 dakikalık vaka başka bir kopma biçimiydi (ağ arayüzünün değişmesi). **Ölçülmedi:** gerçek ağ değişimi altında yeni ayarın davranışı, çok yavaş bağlantılarda yanlış kopma.

**21. Lynis önce/sonra, gerçek VM (2026-10-18).** Temiz snapshot'a dönülmüş VM (Ubuntu 26.04.1, Lynis 3.1.6 snapshot'ta kuruluydu, indirme yok); saat `chrony` yeniden başlatılarak düzeltildi, sonra salt okunur sistem incelemesi (paketler, dinleyen portlar, hesaplar, `sshd -T`, sysctl, izinler)
ve `lynis audit system`. Ardından varsayılanlarla tam `harden` (**`ok=117 changed=35 failed=0`**, 13 dk; madde 19'daki temiz kurulumla aynı sayılar), sonra aynı iki ölçüm. Ham raporlar repoda YOK (ana makine adı ve paket listesi içerir): kullanıcının makinesinde `~/.local/share/linux-hardening/scans/` altında (0700/0600).
| | Önce | Sonra |
|---|---:|---:|
| **Lynis hardening index** | **58** | **73** |
| Uyarı | 2 | 1 |
| Öneri (ham satır) | 94 | 26 |
| `sysctl` değeri farklı | 15 | 5 |
Kategori (öneri sayısı, önce→sonra): SSH 18→2, AUTH 14→2, NETW 8→0, BANN 4→0, USB 2→0, BOOT 6→3, FILE 6→2, DEB 8→4, PKGS 8→4, ACCT 4→1, LOGG 4→2. Okunan ayar farkları (19): `sshd` (parola girişi, root, forwarding, banner, `MaxAuthTries`...), `rp_filter`, `accept_redirects`, `send_redirects`, `log_martians`, `kptr_restrict`, `suid_dumpable`.
**Kalan öneriler, sınıflandırma:**
- *Bilerek yapılmayan / tasarım ister:* SSH `Port` (port değiştirme desteklenmez), `MaxSessions 2` (CIS en çok 10 ister; 4 seçildi, Ansible çoklaması oturum kullanır), GRUB parolası, `/home` ve `/var` ayrı bölüm (kurulum kararı), `kernel.modules_disabled=1` (yeniden başlatmaya dek geri alınamaz), uzak günlük sunucusu, derleyici kısıtı, kötü amaçlı yazılım tarayıcısı.
- *Küçük ve güvenli, yapılabilir:* `fs.protected_fifos=2`, `kernel.sysrq=0`, `net.core.bpf_jit_harden=2`; AIDE sağlama toplamı SHA256/SHA512 (FINT-4402, `hardening_aide` kurulduktan sonra çıkan yeni öneri); `libpam-tmpdir`. Düşük değerli paketler: `debsums`, `apt-listchanges`, `apt-listbugs`, `apt-show-versions`, `acct` (süreç muhasebesi). `fail2ban jail.local`: kozmetik (bizim ayar zaten `jail.d/` içinde, güncellemeden etkilenmez).
- *Ortam:* `PKGS-7392` uyarısı (`python3-jwt`, `python3-urllib3` için bekleyen güvenlik güncellemesi): Lynis `apt-get update` yapınca görüyor, snapshot eski; `unattended-upgrades` açık ve günlük uyguluyor. Temiz kurulumdan hemen sonra puan, güncel olmayan paketler yüzünden düşük çıkabilir.
Not: Lynis puanı CIS uyumu değildir; öznel bir araçtır. Aynı sunucuda ölçüldü, başka sunucuda puanlar farklı olabilir. **Ölçülmedi:** `systemd-analyze security` (servis sandbox puanları, Lynis BOOT-5264), farklı bir sunucu türü (web/Docker), Lynis'in eski sürümleri.

**22. Küçük Lynis maddeleri, gerçek VM (2026-10-19).** `--tags kernel,auth` ile (zaten sertleştirilmiş VM'in üstüne): `ok=15 changed=3`, ikinci koşu `changed=0`. `sysctl`: `kernel.sysrq=0`, `fs.protected_fifos=2`, `net.core.bpf_jit_harden=2` (root ile okundu);
`libpam-tmpdir` 0.11build1 (12 KB, Ubuntu arşivi) kuruldu, `common-session`'da `pam_tmpdir.so`; yeni SSH oturumunda `TMPDIR=/tmp/user/1000`, `sudo` altında `/tmp/user/0`; `sudo` çalışıyor.
**Lynis: 73 → 80, uyarı 1 → 0, öneri 26 → 24, farklı sysctl 5 → 2** (kalan: `kernel.modules_disabled`, bilerek yok; `kernel.unprivileged_bpf_disabled` 2 vs 1, eşdeğer güvence).
**Puanın ne kadarı bizden? (Lynis günlüğünü okuyarak):** alınan puan 272 → 277 (**+5**: `DEB-0280` +2, ek sysctl ~+3). Bizden gelen fark ~**+1,5 puanlık endeks** (73 → ~75). Kalan ~5 endeks puanı **ortamdan**: önceki taramada `PKGS-7392` ("13 güvenlik güncellemesi bekliyor") 25 puan
üzerinden 0 almıştı; bu arada `unattended-upgrades` güncellemeleri uyguladı (apt geçmişi: 18 Eki 06:18 ve 19 Eki 06:52), test artık "no vulnerable packages" der ve 25 puanlık ağırlık paydadan düştü (olası puan 368 → 343). Yani "80" gerçek, ama güncel olmayan bir snapshot'ta aynı sertleştirme ~75 gösterir;
puan, Lynis'in o anki paket durumuna da bağlıdır. (Bu çıkarım Lynis günlüğündeki `Hardening: assigned` satırlarından; Lynis'in iç hesabını doğrulamadım.)
**Sonradan (aynı gün):** Lynis ekranında hem öncesi hem sonrası taramada kırmızı `Permissions for directory: /etc/sudoers.d [WARNING]` vardı (`AUTH-9252`: dizin `0755`; Lynis `0750` veya daha kısıtlısını bekler). `hardening_files` hedeflerine `/etc/sudoers.d` (`g-w,o-rwx`) eklendi; VM'de `--tags files` `changed=1`, ikinci koşu `changed=0`, dizin `drwxr-x---`, `sudo` çalışıyor, Lynis artık `directory /etc/sudoers.d permissions OK` (endeks 80 aynı: test puan vermiyor, yalnızca uyarı gösteriyordu).
`FINT-4402` (AIDE özetleri) bilerek düzeltilmedi (yanlış pozitif, `docs/known-issues.md`). **Ölçülmedi:** `libpam-tmpdir`'in uzun süren servis/cron işleri ve Docker/web sunucusu üzerindeki etkisi, `sysrq=0`'ın gerçek VM konsolundaki etkisi.

## Yolda bulunan ve düzeltilenler
| Bulgu | Düzeltme |
|---|---|
| `include_role` etiketleri içteki görevlere uygulanmıyordu (`--tags` ile korumalar atlanıyordu) | `apply: tags` (#10) |
| `auto_silent` yorumlayıcı anahtar sözcüğü program yolu sanılıyordu | Fact'teki gerçek yorumlayıcı (#18) |
| Disarm boş `ufw/` yedek klasörünü bırakıyordu | `rmdir` (#21) |
| journald'da her satır iki kez | systemd altında `logger` atlanır (#25) |
| Eski betik kuruluyken `rollback.yml` sonuç satırı üretmiyordu (yalnızca canlıda görüldü) | Eski çıktıdan satır kurulur (#31) |
| Zaman raporu, snapshot dönüşünde (kaynaklar `~`) saati ~9 sn kayık gösterdi; gerçek kayma ~8 gün idi. "Hiçbir kaynak seçilmedi" uyarısı yine çıktı ama büyüklük yanlıştı | Düzeltildi (`zaman-raporu-tilde` PR'ı): seçili kaynak yokken ofset "güvenilmez" denir ve sunucu saati kontrol makinesiyle de karşılaştırılır |
| Snapshot dönüşünde VM saati ~28 saat geride kaldı | `chronyc makestep` (HOWTO'ya yazıldı); kaynaklar `^?` iken yetmez, `systemctl restart chrony` (2026-10-17, HOWTO güncellendi) |

## Doğrulanmayanlar
- Başka sunucular/yapılandırmalar; ikinci bir Ubuntu 26.04 kurulumu.
- **Gerçek ağ/ufw düzeyi kesinti** (engel sshd katmanındaydı).
- Kontrol makinesinin ağ değiştirmesi (VPN ↔ LAN) sırasında koşu: 2026-10-18'de kazara yaşandı (madde 19); koşu takıldı, sonuç ve neden belirsiz. Kasıtlı bir deneme yapılmadı. Adres değişince fail2ban `ignoreip` dosyası bir kez yeniden yazılır (beklenen).
- Raspberry Pi / Proxmox profilleri (`planned`).
- sshpocket üzerinden uçtan uca bileşen kurulumu ve çalıştırma.
- Tam CIS Benchmark uyumu (bilerek "yaklaşım").
