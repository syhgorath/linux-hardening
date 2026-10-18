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
- Kontrol makinesinin ağ değiştirmesi (VPN ↔ LAN) sırasında koşu.
- Raspberry Pi / Proxmox profilleri (`planned`).
- sshpocket üzerinden uçtan uca bileşen kurulumu ve çalıştırma.
- Tam CIS Benchmark uyumu (bilerek "yaklaşım").
