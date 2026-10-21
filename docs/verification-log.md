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

**23. apt-listchanges, gerçek VM (2026-10-19).** `--tags base`: `ok=24 changed=2` (paket + `/etc/apt/listchanges.conf` `0644 root:root`), ikinci koşu `changed=0`. Paket `apt-listchanges 4.8+nmu1` (Ubuntu arşivi). Etkileşimsiz çalışma bozulmadı: `apt-get -s upgrade </dev/null` rc=0, `unattended-upgrade --dry-run -v` rc=0, `apt-get install --reinstall -y </dev/null` rc=0 (onay beklemedi). Lynis: DEB-0811 `Installed and enabled for apt`; `apt-listbugs` hâlâ `Not Installed` (DEB-0810 önerisi kalır, paket Ubuntu 26.04'te yok). Puan 81 (öncesi 80). Yalnızca tek VM.

**24. AIDE günlük zamanlayıcı, gerçek VM (2026-10-19).** `--tags aide`: iki koşu da `ok=7 changed=0` (paket `dailyaidecheck.timer`'ı zaten açık kuruyor). Zamanlayıcı bilerek `disable --now` ile kapatıldı, rol yeniden çalıştı: `changed=1`, `enabled`/`active` geri geldi. Mevcut düzenin bulguları (rol değiştirmedi): `COMMAND=update`, `COPYNEWDB=no`; kontrol ~8,5 dk, ~7,5 dk CPU, ~2,4 GB bellek tepesi; günlükte `mail(1)` uyarısı (e-posta teslim edilmiyor), sonuç yalnızca `/var/log/aide/aide.log`. **CI'da yakalanan hata (düzeltildi):** temiz sunucuda `--check` ile paket kurulmadığı için `dailyaidecheck.timer` birimi yoktu ve görev `Could not find the requested service` ile düşüyordu (`linux-smoke`). Mini labda (AIDE kurulu olmayan konteyner) yeniden üretildi: düzeltmeden önce `failed=1`, sonra `failed=0`; görev artık `--check` + paket kurulacaksa atlanır. Gerçek VM'de (AIDE kurulu) davranış değişmedi. Yalnızca tek VM.

**25. Docker `daemon.json` seçenekleri, mini lab (2026-10-19).** `hl-server2` (docker.io 29.1.3, `vfs`): üç seçenek açık + `daemon_manage` + `restart`: ilk koşu `changed=2`, ikinci `changed=0`; `daemon.json`'da `no-new-privileges`, `userland-proxy=false`, `icc=false` eklendi, mevcut anahtarlar (`storage-driver`, `registry-mirrors`) korundu. Sonuçlar: yeni konteynerde `NoNewPrivs: 1`; `docker-proxy` süreci yok, yayınlar (80, 6379, 127.0.0.1:8080) çalışıyor. **Bulgu:** `live-restore` açıkken Docker yeniden başlatıldıktan sonra bile `icc` etkisizdi (`docker network inspect bridge` `enable_icc` hâlâ `true`, iki konteyner birbirine ping atabildi). Konteynerler durdurulup `systemctl restart docker` yapılınca `enable_icc:false`, `DOCKER-FORWARD ... -i docker0 -o docker0 -j DROP` ve ping %100 kayıp. Yalnızca mini lab (iç içe Docker); gerçek ana makine Docker'ında denenmedi.

**26. `su` kısıtı, gerçek VM (2026-10-19).** `--tags sudo -e hardening_su_restrict=true`, ikinci bir SSH oturumu açık tutularak: ilk koşu `ok=12 changed=2` (grup + `/etc/pam.d/su`), ikinci koşu `changed=0`. Öncesi: `pam_wheel` yok, `sugroup` yok, kullanıcı `su` için parola isteniyordu (`Authentication failure`). Sonrası: `/etc/pam.d/su` satır 7 `auth required pam_wheel.so use_uid group=sugroup` (`pam_rootok` satırından hemen sonra), `sugroup` boş. Kullanıcı hesabı `su -c id root` ve `su -c id nobody`: `su: Permission denied`; `sudo -n id -u` → `0`; `sudo su -s /bin/sh -c 'id -un' nobody` ve `sudo su - kullanıcı -c 'id -un'` (root olarak) çalıştı; yeni SSH bağlantısı çalıştı; açık tutulan ikinci oturum etkilenmedi. `su` yine `Password:` istemini yazdırıyor ama sonuç `Permission denied` (öncesinde `Authentication failure` parola yanlışından geliyordu). Yalnızca tek VM; VM'de kısıt AÇIK bırakıldı.

**27. Root ortamı raporu, gerçek VM + mini lab (2026-10-19).** Gerçek VM, `--check --tags auth`: `ok=17 changed=0`, "root PATH temiz (7 dizin) ve umask 027". Mini labda `hl-server1` root ortamı bilerek bozuldu (`/root/.profile`: `umask 022`, `PATH`'e `::`, `/yok/dizin`, `.` ve 777'li `/opt/yazilabilir` eklendi); rapor hepsini yakaladı (boş girdi, `.`, olmayan dizin, root'a ait olmayan, yazılabilir dizin, `umask` 0022), geri alınınca "temiz". **Yolda bulunan iki hata:** (1) `command` modülü komut satırındaki `$PATH`'i kendisi açıp sudo'nun PATH'ini veriyordu (bozuk `PATH` görünmedi); `shell` modülüne geçildi. (2) `printenv PATH` dışa aktarılmamış PATH'te boş döndü ("PATH boş" yanlış alarmı); `echo "$PATH"` kullanıldı. Sınır: gerçek giriş oturumunun PAM ortamı taklit edilmez. Yalnızca tek VM ve tek mini lab.

**28. `/tmp` ve `/dev/shm` raporu, gerçek VM + mini lab (2026-10-19).** `--check --tags files`: gerçek VM `changed=0`, çıktı "NOT (tmp): /tmp: tmpfs nodev,nosuid; /dev/shm: tmpfs nodev,nosuid" + iki `noexec yok` notu. Mini lab konteyneri: `/dev/shm` zaten `noexec` (tek not `/tmp` için). `-e ansible_remote_tmp=/tmp/.ansible` ile "UYARI (tmp): Ansible uzak geçici dizini ... noexec açılırsa Ansible modülleri çalışmaz". Hiçbir şey değişmedi. Yalnızca tek VM ve tek mini lab; `noexec` açma etkisi DENENMEDİ (seçenek yok).

**29. v0.4.0, sshpocket üzerinden TAZE kurulum, gerçek VM (2026-10-20; sshpocket 3.6.4 tarafından bildirildi).** Snapshot'tan geri yüklenmiş Ubuntu 26.04.1 VM'inde, sshpocket akışıyla: `audit` (Lynis `hardening_index` 62, 0 uyarı) → `preview` → `apply`: `ok=131 changed=38 failed=0`; yeni SSH bağlantı doğrulaması geçti, güvenlik ağı `disarm` edildi. Uygulama sonrası bakılanlar: `kernel.sysrq=0`, `fs.protected_fifos=2`, `/etc/sudoers.d` `0750`, `libpam-tmpdir`, `apt-listchanges`, AIDE zamanlayıcısı. **`warn_if` onayı çıkmadı** (#74 gerçek akışta çalışıyor). Bu kayıt v0.4.0 notundaki "tüm yeni varsayılanlarla sıfırdan tam kurulum yapılmadı" cümlesini kapatır. **Henüz yapılmadı:** `apply` SONRASI `audit` (önce/sonra Lynis karşılaştırması) ve v0.3.0 üzerine ikinci koşu (`changed=0`). Kaynak: sshpocket tarafı raporu; ham çıktılar bu repoda yok. Yalnızca tek VM.

**30. Proxmox koruması ve saat düzeltme, gerçek VM (2026-10-20).** `--check --tags auth` (gerçek VM, Proxmox değil): normal akış `ok=18 failed=0`. `hardening_proxmox_markers` bilerek VM'de var olan bir dosyaya (`/etc/hostname`) çevrilince rol `failed=1` ile durdu ("Bu sunucu bir Proxmox VE hostu ...") ve `hardening_allow_unsupported=true` ile BİLE durdu. **Denenmedi:** gerçek bir Proxmox hostu. Mini lab (Colima) o sırada kapalıydı. Yalnızca tek VM.

**31. `hardening_time_makestep`, gerçek VM (2026-10-20).** VM saati `date -s` ile 3 gün geri alındı: chrony tüm kaynakları `?` yaptı, zaman raporu "~3 gün geride" + "Hiçbir kaynak seçilmedi" uyardı (`fix=restart`). `hardening_time_makestep=true` ile `--tags time`: `changed=1`, "Restart chrony" görevi çalıştı, "Step the clock" atlandı; birkaç saniye içinde VM saati kontrol makinesiyle eşleşti (fark 1-2 sn, ssh gecikmesi), kaynaklar `+`/`*`. Saat 2 dk geri alınınca da kaynaklar 2 dakikadan uzun `?` kaldı ve aynı `restart` yolu saati düzeltti. Saat doğruyken `makestep=true` ikinci koşu: `changed=0`, düzeltme görevleri atlandı. **Denenmedi:** `makestep` dalı (kaynak SEÇİLİYKEN büyük kayma): kaymadan sonra chrony kaynakları `?` yaptığı için bu durum VM'de üretilemedi; yalnız birim ve görev testleri var. Yalnızca tek VM.

**32. v0.4.0+ (main `88b9118`): sshpocket'le kurulmuş VM'e tam `harden` ve idempotens (2026-10-20).** VM, sshpocket'in v0.4.0 taze kurulumunun (madde 29) üstünde. Bu repodan `playbooks/harden.yml` (kendi `ssh_allow_from` değerlerimle): 1. koşu `ok=127 changed=2` (tek fark: `fail2ban` sshd jail'i, büyük olasılıkla sshpocket'in verdiği `ignoreip` ile benim değişken dosyamın farkı; ayrıştırılmadı). 2. koşu bağlantı kopmasıyla yarım kaldı (`UNREACHABLE: Shared connection to ... closed`, "Read ufw rules added so far" görevinde; o ana dek 104 görev `changed=0`; VM sonradan erişilebilirdi, fail2ban yasağı yok, sebep belirlenmedi). 3. koşu: **`ok=126 changed=0 unreachable=0 failed=0`**. Uygulama sonrası Lynis: **hardening index 80** (sshpocket'in uygulama öncesi ölçümü 62), `apt-listchanges` "Installed and enabled", uyarı yok, 23 öneri. **Bilinmeyen:** 2. koşudaki kopmanın tekrarlanıp tekrarlanmadığı (3. koşuda olmadı); ağ/ssh `ControlMaster` kaynaklı olabilir. Yalnızca tek VM.

**33. `/tmp` ve `/dev/shm` noexec, gerçek VM, PHP ile (2026-10-20).** VM (Ubuntu 26.04.1, `/tmp` ve `/dev/shm` tmpfs, `tmp.mount` etkin, fstab'da `/dev/shm` yok). `--tags files`: 1. koşu `ok=32 changed=5` (drop-in dizini + dosyası, daemon-reload, fstab satırı, 2 remount), 2. koşu `changed=0`. Sonuç: `/tmp` ve `/dev/shm` `nodev,nosuid,noexec`; `/tmp`'e kopyalanan `/bin/true` ve `./betik.sh` `Permission denied` (rc=126), `sh betik.sh` çalışır (beklenen sınır), home'dan çalıştırma etkilenmez. **Genel PHP denemesi (Ubuntu arşivinden php 8.5.4, php-fpm, nginx, composer 2.9.5; noexec AÇIKKEN kuruldu):** `apt install` hatasız (dpkg betiklerinde `Permission denied` yok); nginx+php-fpm: dosya yükleme (`/tmp/php...` geçici dosya, `move_uploaded_file` başarılı), `exec('/bin/true')` çalışır, `/tmp`'e yazılan betiğin doğrudan çalıştırılması `rc=126` (beklenen), `sh ile` çalışır, oturum, GD PNG, ZipArchive (`sys_get_temp_dir()`'e yazar) çalışır; composer `validate`/`install` çalışır. php-fpm servisi bu Ubuntu paketinde `PrivateTmp=no` (yani PHP doğrudan sunucunun `/tmp`'ini kullanır). Ansible kendisi `~/.ansible/tmp` kullandığı için etkilenmedi (`-vvv` ile görüldü). **Reboot sonrası:** drop-in ve fstab satırı kalıcı, `/tmp` ve `/dev/shm` `noexec`, tüm servisler (`tmp.mount`, `ssh`, `nginx`, `php8.5-fpm`, `fail2ban`, `ufw`, `auditd`) `active`, `--tags files` `changed=0`. **Denenmedi:** PDF üreten dış programlar (wkhtmltopdf, chromium), Java/Node uygulamaları, Docker, `fstab`'ta hazır `/dev/shm` satırı olan sunucu (yalnız birim testli). Kullanıcının eski bir PHP projesinde gördüğü hata tekrarlanamadı (hata metni bilinmiyor). Yalnızca tek VM.

**34. Parolalı sudo taban çizgisi (faillock YOK), gerçek VM (2026-10-20).** `lhtest` adlı geçici test hesabı (rastgele parola yalnızca yerel dosyada; SSH anahtarı; `sudo` kuralı parola ister). Ölçümler: doğru parola `rc=0`; 7 art arda yanlış parola sonrası doğru parola yine `rc=0` (kilit yok); `sudo -n` `rc=1` ve sayaç artmaz; yanlış parolalı her `sudo -S` günlükte 1 `authentication failure`; tek çağrıda 3 yanlış satır `maximum 3 incorrect authentication attempts`; SSH anahtar girişi etkilenmedi. **Ansible ile:** `become` parolası doğru da yanlış da olsa `Timeout (12s) waiting for privilege escalation prompt` (`UNREACHABLE`). Sebep elle görüldü: sudo-rs çıktısı `[sudo: [sudo via ansible, key=abc] password:] Password:`; ansible-core 2.21 `check_password_prompt` istemin satır BAŞINDA olmasını ister. `-e ansible_become_exe=/usr/bin/sudo.ws` ile doğru parola `ok=3`, yanlış parola `Incorrect sudo password` ve koşu başına sayaç +1 (3 ayrı yanlış koşu = +3). Bu, bu paketten bağımsız bir Ubuntu 26.04 + Ansible bulgusudur; `HOWTO.md` ve `docs/known-issues.md`'ye yazıldı. Yalnızca tek VM; sshpocket'in `become` akışı denenmedi.

**35. `pam_pwhistory` (parola geçmişi), gerçek VM (2026-10-20).** `--tags auth -e hardening_pam_pwhistory_remember=2`: önizleme `changed=3`, 1. koşu `ok=25 changed=4`, 2. koşu `changed=0`. `/etc/pam.d/common-password` sırası `pam_pwquality`, `pam_pwhistory use_authtok`, `pam_unix` (beklenen); `pwhistory.conf` `remember = 2`. `enforce_for_root=true` ile 2. koşu da `changed=0`. **Ölçülen davranış:** (1) `remember=2`, test hesabı `lhtest`: `opasswd`'de her zaman en çok 2 eski hash; mevcut + önceki parola reddedilir, ondan eski kabul edilir (yani `remember=N` mevcut + N-1 önceki). (2) Root'un `chpasswd`'si `enforce_for_root` KAPALIYKEN "Password has been already used" mesajı alır AMA parola yine değişir; `enforce_for_root` AÇIKKEN `password not changed`. (3) Normal kullanıcı `passwd` (pty): önceki parola `already used` ile reddedildi, `password unchanged`. (4) SSH anahtar girişi ve `sudo` etkilenmedi. **Yolda düzelen:** başta tahmin ettiğim "chpasswd betikleri varsayılan ayarla kırılır" yanlıştı: yalnızca `enforce_for_root=true` ile kırılır. **Denenmedi:** `faillock`, başka hesap türleri, `pam-auth-update` ile başka profillerin birlikte etkinleştirilmesi. Yalnızca tek VM.

**36. Geri alma güvenlik ağı PAM'i kapsıyor, gerçek VM (2026-10-20).** `hardening_rollback` rolü `hardening_rollback_timeout=90` ile arm edildi (yedek: `common-*`, `/var/lib/pam/*`, `faillock.conf`). Sonra `common-auth`'un başına bilerek `auth requisite pam_deny.so` yazıldı: `lhtest` hesabı doğru parolayla `sudo.ws` denediğinde `Sorry, try again` (yığın gerçekten bozuk). Kendi kanalım (SSH anahtarı + parolasız sudo) etkilenmedi. **90 sn sonra zamanlayıcı kendiliğinden tetiklendi (13:55:41):** günlükte `PAM dosyalari onceki icerige donduruldu` ve `geri alma tamamlandi`; `common-auth` özgün içeriğe döndü, `status` `armed=no timer=inactive`, `lhtest` doğru parolayla `sudo` yeniden çalıştı. Birim testi: `test/test_rollback_script.sh` bölüm 9 (68 kontrol; 9 mutasyon yakalanıyor): yedek/geri yükleme, sonradan eklenen `hardening-faillock` profilinin silinmesi, eski profil varsa eski içeriğin yazılması, kilit sayaçlarının silinmesi, disarm'da yedeğin silinmesi, PAM'in ssh/ufw'den ÖNCE geri alınması. **Henüz yok:** `faillock` rolü (bu PAM penceresini kullanacak) ve `harden.yml` bağlantısı. Yalnızca tek VM.

**37. `pam_faillock` (hesap kilitleme), gerçek VM (2026-10-20).** `harden.yml --tags pam -e hardening_pam_faillock=true -e deny=3 -e unlock_time=300`: önizleme `changed=3`; gerçek koşu `ok=33 changed=6` (arm, profiller, `pam-auth-update`, doğrulama, disarm; koşu sonunda `armed=no`); **ikinci koşu `ok=32 changed=0`**. Üretilen yığın tasarlandığı gibi ilk denemede çıktı (`preauth` → `pam_unix [success=2]` → `authfail`; `account`'ta `faillock` pam_unix'ten önce). **Korumalar (VM):** `-e hardening_rollback_enabled=false` ile rol "REDDEDİYORUM" diyerek durdu; arm edilmeden yalnızca faillock rolü çalıştırılınca "ARMED değil" diyerek durdu (PAM'e dokunulmadı). **Ölçülen davranış** (`lhtest`, `deny=3`): doğru parola çalışır, başarıda sayaç sıfırlanır; sudo-rs yanlış parolada çağrı başına 1 kayıt, klasik sudo (`sudo.ws`) ve Ansible koşusu başına **2 kayıt** bırakır (yani deny=5 ile 3 yanlış Ansible koşusu kilitler); 3 kayıttan sonra DOĞRU parola da reddedilir (sudo-rs: `maximum 3 incorrect authentication attempts`); Ansible'da kilitliyken hata `Shared connection closed` (yanıltıcı); **kilitliyken SSH anahtar girişi ve başka hesap (syhgorath) etkilenmedi**; `sudo -n` etkilenmedi; `faillock --user lhtest --reset` anında açar; `unlock_time` dolunca (20 sn ile denendi) kilit kendiliğinden açıldı. **Denenmedi:** `even_deny_root`, `fail_interval` süre sınırı, rescue yolunun gerçek tetiklenmesi (yalnız yapı testi; geri alma betiğinin kendisi madde 36'da kanıtlandı), konsol (`login`) ve `su`. Yalnızca tek VM.

**38. v0.5.0 (main `5d9e024`): SIFIRDAN tam kurulum ve ikinci koşu, gerçek VM (2026-10-21).** Temiz snapshot'a dönmüş Ubuntu 26.04.1 VM'i (saat 12 gün geride: `chrony` yeniden başlatılarak düzeltildi). Tüm varsayılanlarla `playbooks/harden.yml`: `--check --diff` `ok=116 changed=34 failed=0`; **1. koşu `ok=143 changed=43 unreachable=0 failed=0`** (~13 dk, AIDE ilk veritabanı dahil); **2. koşu `ok=133 changed=0 failed=0`**. Sonuç durumu: `/tmp` ve `/dev/shm` `nodev,nosuid,noexec` (`/tmp`'e kopyalanan `/bin/true` `Permission denied`); `ssh`, `ufw`, `auditd`, `fail2ban`, `chrony`, `tmp.mount`, `dailyaidecheck.timer` etkin; geri alma ağı `armed=no` (doğrulama sonrası disarm); sshd `permitrootlogin no`, `passwordauthentication no`, `maxauthtries 3`; `kernel.sysrq=0`, `fs.protected_fifos=2`; `/etc/sudoers.d` `750`; `faillock` yığında YOK (varsayılan kapalı); yeni bir SSH bağlantısı çalışıyor; `apt-listchanges` etkin. Lynis `hardening_index` **75** ve 1 uyarı (`PKGS-7392`, güvenlik güncellemesi bekleyen paketler: snapshot eski, `unattended-upgrades` henüz çalışmadı; paketimizden bağımsız, madde 21/22'de de aynıydı). **Bu kayıt v0.5.0 sürüm notundaki "sıfırdan tam kurulum ve ikinci koşu yapılmadı" cümlesini kapatır.** Denenmedi: sshpocket üzerinden akış (madde 29 yalnız v0.4.0 için), seçeneklerin (faillock, pwhistory, makestep) varsayılan kapalıyken ÇOK sayıda birlikte açık kombinasyonu. Yalnızca tek VM.

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
