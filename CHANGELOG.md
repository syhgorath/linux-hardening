# Değişiklik günlüğü

Bu dosya [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) biçimini ve
[Anlamsal Sürümleme](https://semver.org/lang/tr/) kullanır.

## [Yayımlanmamış]

### Düzeltildi
- ansible-core 2.24 hazırlığı (#36): fact'ler artık `ansible_facts['distribution']`, `ansible_facts['distribution_version']` ve
  `ansible_facts['getent_passwd']` ile okunur (`hardening_preflight` OS denetimi, `hardening_ssh` anahtar kontrolü).
  2.24'te üst düzey `ansible_distribution` / `getent_passwd` tanımsız olacağından bu erişim kaybı korumaları kırılırdı.
  `ansible.cfg` artık `inject_facts_as_vars = False` ayarlar (2.21'deki `DEPRECATION WARNING` kalkar); testler de bunu zorlar.

### Değişti
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

[Yayımlanmamış]: https://github.com/syhgorath/linux-hardening/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/syhgorath/linux-hardening/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/syhgorath/linux-hardening/releases/tag/v0.1.0
