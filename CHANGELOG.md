# Değişiklik günlüğü

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) biçimini ve
[Anlamsal Sürümleme](https://semver.org/lang/tr/) kullanır.

## [Yayımlanmamış]

### Düzeltildi
- `hardening_auditd`: denetim kuralları artık auditd başladıktan **hemen sonra** yükleniyor (handler yerine görev; `auditctl -l` ile kural yoksa da yeniden yüklenir). Eskiden kurallar play sonunda yükleniyordu; test VM'inde auditd başlangıcından 652 sn sonra, yani `fail2ban`/`aide`/`ufw`/`ssh` değişiklikleri izlenmiyordu. Davranış tek yönlü iyileşir. Test: `test_auditd_rules_order.py`.

### Eklendi
- `hardening_auditd`: `harden` sırasında **salt okunur** bir uyarı: auditd'den ÖNCE başlamış ve yeniden başlatılmamış programları listeler (denetlenmezler; örn. `sshd`, `cron`, `rsyslogd`). Davranışı değiştirmez, `--check`'te de çalışır; auditd kurulu değilse sessizdir. Test: `test_auditd_unaudited.py`.
- `docs/known-issues.md`: sertleştirmenin meşru kullanımları bozabileceği yerler (ufw+Docker, SSH yönlendirme, mail sunucusu kaldırma, umask vb.) ve her biri için kaçış değişkeni ya da "anahtar yok" notu. Birçok satır Docker LAB'ında denendi; denenemeyenler ⚠️ olarak işaretli.
- auditd kapsamı için tasarım notu: `docs/design/auditd-kapsam.md` (kod yok). Test VM'inde ölçülen üç bulgu: kurallar play sonunda yükleniyor, auditd'den önce başlayan süreçler denetlenmiyor, `time-change` kuralı chrony'yi (`clock_adjtime`) kapsamıyor.
- Zaman senkronizasyonu rolü için tasarım notu: `docs/design/zaman-ntp.md` (kod yok; seçenekler, değişkenler, riskler, açık sorular).
- Proxmox VE hostu için **işlevsiz iskelet** ve tasarım notu: `docs/design/proxmox-host.md`, boş roller `hardening_pve_firewall` ve
  `hardening_pve_access`, `hardening_preflight/tasks/platform.yml`. `harden.yml` bunlara bağlı değil; yanlışlıkla çağrılırsa durur.
  Davranış değişmez.

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

[Yayımlanmamış]: https://github.com/syhgorath/linux-hardening/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/syhgorath/linux-hardening/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/syhgorath/linux-hardening/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/syhgorath/linux-hardening/releases/tag/v0.1.0
