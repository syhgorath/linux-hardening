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

## Ne yapmaz (kapsam sınırları)

Bu proje **tam CIS Benchmark uyumu iddia etmez**: hedef "Level 1 Server *yaklaşımı*". Hangi CIS maddelerinin karşılandığı henüz **madde numarasıyla eşlenmedi**
(eşleme CIS Benchmark PDF'iyle çıkarılacak, bkz. [docs/ROADMAP.md](docs/ROADMAP.md)); bu yüzden aşağıdaki tablo madde değil **alan** bazlıdır ve yalnızca kodda
doğrulanmış sınırları listeler. "Bilerek" yazılanlar belgeli kararlardır; diğerleri **henüz yapılmadı**, atlandığı anlamına gelmez. Eksik bir alan görürseniz issue açın.

| Alan | Durum | Not |
|---|---|---|
| SSH portunu değiştirmek | Bilerek yok | ufw kuralı sshd'nin gerçekten dinlediği porttan yazılır ([decisions.md](docs/decisions.md)) |
| Otomatik yeniden başlatma | Bilerek yok | Otomatik güvenlik güncellemesi açılır, reboot **yok** ([HOWTO.md](HOWTO.md)) |
| Kullanıcı, parola, anahtar yönetimi | Tasarım gereği yok | Kullanıcıyı siz oluşturursunuz; rol yalnızca parola girişini kapatmadan önce `authorized_keys`'in dolu olduğunu doğrular |
| Uygulama sertleştirmesi (nginx, MySQL vb.) | Kapsam dışı | Yalnızca işletim sistemi |
| Başka dağıtım/sürüm | Şimdilik yok | Yalnızca Ubuntu 26.04; Raspberry Pi/Proxmox planlı ([SUPPORT.md](docs/SUPPORT.md)) |
| Geri alma | Kısmi | Yalnızca sshd drop-in ve ufw geri alınır; paketler, sysctl, auditd, fail2ban, AIDE geri alınmaz |
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
| `test_cis_group1.py` | apport ve `update-notifier-motd` kapatma (olmayan birime dokunulmaz, kendi değişkeniyle kapanır, `lineinfile` idempotent) ve SUID/SGID özetinin salt okunur kalması |
| `test_files_role.py` | dosya izinleri gerçek `ansible-playbook` ile geçici ağaçta: yalnızca sıkılaşır (0600 gevşemez), olmayan dosya oluşturulmaz, sembolik bağ izlenmez, `--check` değiştirmez, ikinci koşu `changed=0` |
| `test_sudo_role.py` | sudoers drop-in: `visudo -cf` ile doğrulanır (üretilen içerik gerçek `visudo` ile), `become` denemesi, başarısızlıkta temizlik, `NOPASSWD` yok |
| `test_cis_quickwins.py` | CIS kolay kazançlar: modül listeleri, ufw `routed` ilkesi, `audit=1` (gerçek `replace` modülüyle, idempotent), ssh yeniden başlatma yasağı, riskli seçeneklerin varsayılanı kapalı |
| `test_time_report.py` | zaman raporu kararı (gerçek `chronyc -c sources` biçimiyle): sağlıklı, bayat/kayık saat, servis kapalı, kaynak yok, eşik, bozuk satır |
| `test_time_tasks.py` | zaman rolü salt okunur kalır: yalnızca okuma modülleri, `--check`'te çalışır, kapatılabilir, saati değiştiren komut yok |
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
