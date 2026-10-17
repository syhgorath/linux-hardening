# Bilinen çakışmalar: sertleştirme neyi bozabilir

`harden.yml` bir sunucuya uygulanınca bazı **meşru** kullanımlar çalışmaz hâle gelebilir. Bu belge, kendi rollerimizin yaptığı
ayarlardan çıkarıldı ve her satırda **kaçış yolunu** söyler. Önce test sunucusunda deneyin, snapshot alın, `--check --diff` ile bakın.

**Nasıl okunur**
- **Doğrulama** sütunu: ✅ = ayar kodumuzda var (dosya adı yazılı); ⚠️ = ayar kodda var ama *etkisi* genel Linux bilgisidir ve burada ayrıca
  denenmedi.
- **Kaçış** sütunu yalnızca gerçekten var olan değişkenleri yazar. "Anahtar yok" ise tek seçenek ilgili rolü atlamaktır
  (`--skip-tags <rol>`, rol adı = etiket; örn. `--skip-tags base`), bu rolün **tüm** ayarlarını atlar.
- Geri alma güvenlik ağı yalnızca **sshd drop-in ve ufw'yi** geri alır. Aşağıdaki diğer satırlar geri alınmaz.

## Uygulamadan önce sunucuda bakın (salt okunur)
```bash
sudo ss -tlnp                                    # dinleyen servisler: ufw bunlardan hangisini kapatacak?
dpkg -l | grep -E 'postfix|courier|exim'         # çalışan bir mail sunucusu var mı? (base rolü kaldırır)
command -v docker && sudo docker ps              # Docker var mı? (ufw ile birlikte bkz. tablo)
sudo ls /etc/ssh/sshd_config.d/ && sudo sshd -T | grep -iE 'allowtcpforwarding|allowagentforwarding|maxsessions'
```

## Erişim ve ağ

| Alan | Ne yapıyoruz | Neyi bozabilir / belirti | Doğrulama | Kaçış |
|---|---|---|---|---|
| **ufw** | `allow_from` ağlarından sshd portuna izin, varsayılan `deny incoming` | `allow_from` dışındaki her ağdan **SSH ve tüm gelen trafik** kesilir. Yalnızca VPN yazılırsa LAN'dan SSH zaman aşar (ping/ARP çalışır). Web, izleme (Prometheus vb.) portları da kapanır | ✅ `roles/hardening_ufw` | `hardening_ssh_allow_from` (**tüm** bağlantı ağlarını yaz), `hardening_ufw_extra_allow` (ek portlar, örn. `443/tcp`) |
| **ufw + Docker** | Yukarıdaki kurallar | Docker, yayınladığı portları kendi iptables zincirine yazar; ufw "deny" demesine rağmen **konteyner portu dışarıdan erişilebilir kalabilir**, ufw güvenlik hissi verir ama korumaz | ⚠️ bilinen Docker davranışı, bizde denenmedi | Anahtar yok. Docker hostunda firewall'u ayrıca doğrulayın (`sudo iptables -S DOCKER-USER`) ya da `--skip-tags ufw` |
| **sshd: TCP yönlendirme** | `AllowTcpForwarding no` | **Bu sunucu üzerinden** `ssh -J` / ProxyJump, `ssh -L`/`-R`, bazı IDE uzak bağlantıları çalışmaz ("administratively prohibited") | ✅ `sshd-hardening.conf.j2`; etki ⚠️ | `hardening_ssh_allow_tcp_forwarding: local\|remote\|yes` |
| **sshd: agent yönlendirme** | `AllowAgentForwarding no` | Bu sunucuya `ssh -A` ile bağlanıp oradan başka yere (örn. git/ssh) agent anahtarıyla bağlanamazsınız | ✅ şablon; etki ⚠️ | **Anahtar yok** (`--skip-tags ssh` tüm ssh rolünü atlar) |
| **sshd: deneme/oturum sınırı** | `MaxAuthTries 3`, `MaxSessions 4` | Agent'ta 3'ten çok anahtar varsa "Too many authentication failures"; tek bağlantı üzerinden 4'ten çok oturum (çoklama kullanan araçlar) reddedilir | ✅ şablon; `docs/HOWTO` 7a | **Anahtar yok.** Çözüm: `IdentitiesOnly yes` + tek anahtar (`ansible_ssh_private_key_file`) |
| **sshd: canlılık** | `ClientAliveInterval 300`, `ClientAliveCountMax 2` | İstemci ~10 dk yanıt vermezse oturum düşer: dizüstü uykusu, VPN kopması, flaky ağ | ✅ şablon; etki ⚠️ | **Anahtar yok** |
| **sshd: root** | `PermitRootLogin no`; ayrıca playbook root ile bağlanınca durur | `root` ile yönetilen sistemler (örn. Proxmox hostu, bazı otomasyonlar) kilitlenir | ✅ şablon + `hardening_preflight` | **Anahtar yok**; root yerine sudo'lu bir kullanıcı gerekir |
| **sshd: parola** | `PasswordAuthentication no` (anahtar yoksa rol durur) | Anahtarsız kullanıcılar giremez | ✅ `hardening_ssh` | `hardening_ssh_disable_password: false`, `hardening_ssh_kbdinteractive` |
| **Banner** | `/etc/issue` ve `/etc/issue.net`, sshd `Banner` | Her SSH bağlantısında banner metni **stderr'e** yazılır; stdout/stderr ayrıştıran betikler ve araçlar bozulabilir | ✅ `hardening_base` + şablon; çıktıda gözlemlendi | **Anahtar yok** (`--skip-tags base` banner'ı da atlar) |
| **fail2ban** | sshd jail: `maxretry 5`, `bantime 1h`; `ignoreip` yalnızca `127.0.0.1/8 ::1` + kontrol makinesinin adresi | Aynı NAT çıkışını paylaşan **başka yöneticiler** ya da parola hataları yapan otomasyon banlanabilir | ✅ `roles/hardening_fail2ban` | `hardening_fail2ban_ignoreip`, `hardening_fail2ban_maxretry`, `hardening_fail2ban_bantime` |

## Çekirdek, modüller ve donanım

| Alan | Ne yapıyoruz | Neyi bozabilir / belirti | Doğrulama | Kaçış |
|---|---|---|---|---|
| **sysctl: `rp_filter=1`** | Katı ters yol filtresi | Çok arayüzlü sunucularda, asimetrik yönlendirmede ya da bazı VPN/tünel kurulumlarında paketler sessizce düşer | ✅ `sysctl.conf.j2`; etki ⚠️ | **Anahtar yok** (`--skip-tags kernel` tüm sysctl ve modül ayarlarını atlar) |
| **sysctl: `ptrace_scope=1`** | `kernel.yama.ptrace_scope = 1` | Çalışan bir sürece `gdb -p` / `strace -p` ile bağlanmak yalnızca kendi alt süreçlerine ya da root'a izinli | ✅ ayar; etki ⚠️ | **Anahtar yok** |
| **sysctl: `dmesg_restrict`, `kptr_restrict`** | Çekirdek günlüğü ve adres bilgisi kısıtlanır | root olmayan kullanıcı `dmesg` okuyamaz; bazı performans/izleme araçları eksik bilgi görür | ✅ ayar; etki ⚠️ | **Anahtar yok** |
| **sysctl: `log_martians=1`** | Hatalı kaynak adresli paketler günlüğe yazılır | Gürültülü ağlarda günlük şişer | ✅ ayar; etki ⚠️ | **Anahtar yok** |
| **ip_forward** | **Dokunmuyoruz** (kernel şablonunda yok) | Bizde çakışma beklemiyoruz; yönlendirme gerektiren hostlar (Proxmox, VPN, k8s) kendi ayarlarını yapar | ✅ şablon incelendi | — |
| **Kernel modül yasağı** | `dccp`, `sctp`, `rds`, `tipc` yüklenemez | SCTP kullanan uygulamalar (bazı telekom/mesajlaşma yığınları) çalışmaz | ✅ `hardening_kernel`; etki ⚠️ | **Anahtar yok** (`--skip-tags kernel`) |
| **USB depolama** | `usb-storage` yüklenemez | USB disk ile yedekleme/kurtarma, USB bellekten veri alma çalışmaz | ✅ `hardening_base` | **Anahtar yok** (`--skip-tags base`) |

## Hesaplar ve dosyalar

| Alan | Ne yapıyoruz | Neyi bozabilir / belirti | Doğrulama | Kaçış |
|---|---|---|---|---|
| **Parola politikası** | `pwquality` (varsayılan `minlen 14`) | Zayıf parolayla `passwd`/`chpasswd` kullanan otomasyon reddedilir | ✅ `hardening_auth` | `hardening_pwquality_minlen` |
| **`login.defs` yaşlandırma** | `PASS_MAX_DAYS 365` vb. | Yalnızca **yeni** oluşturulan hesapları etkiler; mevcut hesaplara `chage` **uygulamıyoruz** | ✅ `hardening_auth` (yalnızca `login.defs` düzenlenir) | `hardening_pass_max_days`, `_min_days`, `_warn_age` |
| **umask** | `UMASK 027` (login oturumları) | SSH/cron oturumlarında oluşan dosyalar "diğer" kullanıcılara kapalı olur; bir web sunucusunun (`www-data`) okuması gereken yüklenen içerik okunamaz | ✅ `hardening_auth`; etki ⚠️ | `hardening_umask` |
| **Mail** | `dma` kurulur, **`postfix` ve `courier-*` `purge` edilir** | Sunucuda çalışan bir mail sunucusu/relay varsa **kaldırılır**, yapılandırması silinir | ✅ `hardening_base` (`purge: true`) | **Anahtar yok**: `--skip-tags base` (güncellemeler, banner, usb dahil atlanır). Mail sunucusu olan hostlarda `base` rolünü çalıştırmayın |
| **Otomatik güncelleme** | `unattended-upgrades` açılır, otomatik reboot yok | Sürüm sabitleyen (pin) kurulumlar, bakım penceresi dışında güncelleme istemeyenler çakışır | ✅ `hardening_base` | **Anahtar yok** (`--skip-tags base`) |
| **auditd** | Kurallar ve servis | Çekirdek denetimi (audit) olmayan ortamlarda (konteyner, bazı LXC/VPS) çalışmaz; LAB'da bu yüzden taklit edilir | ✅ `hardening_auditd`; LAB README | `--skip-tags auditd` |
| **AIDE** | Kurulur, ilk veritabanı üretilir | İlk veritabanı **dakikalar** sürer ve disk G/Ç'si harcar; küçük/yavaş disklerde ilk koşu uzar | ✅ `hardening_aide` (async 1800 sn) | `--skip-tags aide` |

## Bu tablo neyi kapsamıyor
- Proxmox hostu, Raspberry Pi: bkz. [design/proxmox-host.md](design/proxmox-host.md) (henüz işlevsiz).
- Uygulama düzeyinde (nginx, MySQL vb.) sertleştirme bu projenin kapsamında değil.
- ⚠️ işaretli etkiler genel Linux bilgisine dayanır; sizin ortamınızda doğrulanmadan kesin kabul etmeyin.
