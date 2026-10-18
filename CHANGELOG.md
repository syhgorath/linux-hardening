# Değişiklik günlüğü

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) biçimini ve
[Anlamsal Sürümleme](https://semver.org/lang/tr/) kullanır.

## [Yayımlanmamış]

### Eklendi
- `hardening_files` (yeni rol, etiket `files`): CIS dosya izinleri: `/etc/passwd`, `group`, `shadow`, `gshadow` (+ `-` yedekleri), `shells`, `opasswd`; `sshd_config`, `sshd_config.d` ve içindeki `.conf` dosyaları, ana bilgisayar anahtarları; cron dosyaları/dizinleri; `/etc/motd`; `/boot/grub/grub.cfg`. **Yalnızca fazla izni kaldırır** (sembolik modlar: 0600 olan dosya 0644 olmaz), olmayan dosyayı oluşturmaz (`cron.allow`/`at.allow` dahil: boş `cron.allow` crontab kullanımını kapatırdı), sembolik bağı izlemez. `hardening_files_enabled=false` ile kapanır. `hardening_ssh` artık drop-in'i `0600` yazar. Geri alma güvenlik ağı kapsamında değil.
- `hardening_sudo` (yeni rol, etiket `sudo`, en sonda): `/etc/sudoers.d/60-hardening` ile `use_pty`, `logfile=/var/log/sudo.log`, `timestamp_timeout=15` (CIS 5.2.2, 5.2.3, 5.2.6). `visudo -cf` ile doğrulanır, yazıldıktan hemen sonra `become` denenir (başarısızsa dosya silinir ve play durur); `!authenticate` bulunursa yalnızca uyarır. `hardening_sudo_enabled=false` ile kapanır. Geri alma kapsamında değil.
- `hardening_ssh`: açık yazılan CIS 5.1.x seçenekleri: `DisableForwarding yes` (yalnız `hardening_ssh_allow_tcp_forwarding=no` iken), `GSSAPIAuthentication no`, `HostbasedAuthentication no`, `IgnoreRhosts yes`, `PermitUserEnvironment no`, `UsePAM yes`, `MaxStartups 10:30:60` ve `MACs` için zayıf listenin çıkarılması. Çoğu varsayılan zaten uygundu (test VM'inde `sshd -T`); açık yazmak denetlenebilirlik içindir. **Davranışı değiştirenler:** `MaxStartups` (Ubuntu varsayılanı `10:30:100`), `MACs` (umac-64/umac-128-etm kapanır), `DisableForwarding` (StreamLocal da kapanır). Bkz. `docs/known-issues.md`.
- CIS 26.04 eşlemesinden çıkan "kolay kazançlar" (`docs/cis-esleme.md`), **hepsi `test_cis_quickwins.py` ile sınandı**:
  - `hardening_kernel`: `secure_redirects=0` (CIS 3.3.1.10/11), `route_localnet=0` (3.3.1.19); modül yasağı `cramfs`, `freevxfs`, `hfs`, `hfsplus`, `jffs2`, `firewire-core` (1.1.1.x) ve `atm`, `can` (3.2.1/3.2.2). `hardening_kernel_disable_ipv6_ra` (varsayılan `false`): `accept_ra=0` (3.3.2.7/8), IPv6'sını RA'dan alan sunucuyu kesebileceği için kapalı.
  - `hardening_ufw`: `ufw default deny routed` (4.1.5), `hardening_ufw_routed_deny` (varsayılan `true`) ile kapatılabilir.
  - `hardening_auditd`: `clock_adjtime` kuralı yalnız kullanıcı oturumundan gelirse (`auid>=1000`, chronyd gürültüsü yok); `hardening_auditd_restart_services` (varsayılan `[]`, `ssh`/`sshd` reddedilir) ve `hardening_auditd_grub_audit` (varsayılan `false`, `audit=1`, yeniden başlatma gerekir, geri alma kapsamında değil).
  Varsayılan davranış değişiklikleri: yeni sysctl satırları, yeni modül yasakları ve `routed deny` **varsayılan açıktır**; bkz. `docs/known-issues.md`.
- `hardening_time` (yeni rol, etiket `time`): **salt okunur** zaman raporu. chrony çalışıyor mu, kaynaklar ulaşılabilir ve seçili mi, saat kaynaklara göre ne kadar kayık? `harden` çıktısında `ZAMAN:` ya da `UYARI (zaman):` verir.
  Snapshot dönüşünde `timedatectl` "synchronized: yes" derken saatin günlerce kayık olduğu görüldü; rapor bunu kaynakların ölçtüğü ofsetten yakalar. Saati ya da yapılandırmayı **değiştirmez**, `--check`'te de çalışır.
  Değişkenler: `hardening_time_report` (varsayılan `true`), `hardening_time_max_offset_seconds` (varsayılan `5`). Testler: `test_time_report.py`, `test_time_tasks.py`.
- README (TR/EN): **"Ne yapmaz (kapsam sınırları)"** bölümü: alan bazlı tablo; "bilerek" (belgeli karar) ile "henüz yapılmadı" ayrımı. Madde numaralı CIS eşlemesi henüz yok, bölüm bunu açıkça söyler.
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

[Yayımlanmamış]: https://github.com/syhgorath/linux-hardening/compare/v0.2.2...HEAD
[0.2.2]: https://github.com/syhgorath/linux-hardening/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/syhgorath/linux-hardening/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/syhgorath/linux-hardening/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/syhgorath/linux-hardening/releases/tag/v0.1.0
