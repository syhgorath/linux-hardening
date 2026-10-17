# auditd kapsamı: kurallar ne zaman devreye giriyor, kim denetleniyor (tasarım notu, kod yok)

> **Durum: yalnızca tasarım.** `hardening_auditd` rolü bu belgede anlatılan hiçbir şeyi yapmaz. Bulgular **tek bir test VM'inde** (Ubuntu 26.04.1,
> x86_64, çekirdek 7.0.0-38-generic, auditd 4.1.2) 2026-10-17'de ölçüldü; başka ortamlarda doğrulanmadı. "Doğrulanmadı" işaretli yerler kontrol edilmeden kod yazılmaz.

## Rol bugün ne yapıyor (koddan)
`roles/hardening_auditd/`: değişken yok (`defaults/` yok), tek şablon, tek handler.

| Adım | Ne | Not |
|---|---|---|
| 1 | `auditd` ve `audispd-plugins` kurulur | |
| 2 | `/etc/audit/rules.d/60-hardening.rules` yazılır (şablon) | `notify: Load audit rules` |
| 3 | `auditd` etkinleştirilir ve başlatılır | `--check`'te atlanır |
| 4 (handler) | `augenrules --load` | **play sonunda** çalışır (Ansible handler'ları görev listesi bitince çalıştırır) |

Kurallar: `identity` (passwd/group/shadow/gshadow), `scope` (sudoers), `sshd` (sshd_config ve sshd_config.d), `logins` (lastlog, faillock),
`time-change` (`adjtimex,settimeofday,clock_settime` ve `/etc/localtime`), `modules` (`init_module,finit_module,delete_module`).
Kural dosyası kalıcı olarak "değiştirilemez" yapılmaz (`-e 2` yok).

`harden.yml` sırası: `base` → `auth` → `kernel` → **`auditd`** → `fail2ban` → `aide` → `rollback` → `ufw` → `ssh`. `hardening_rollback` yalnızca sshd drop-in ve
ufw'yi geri alır; auditd geri alınmaz.

## Ölçümler (test VM'i, 2026-10-17)
| Gözlem | Değer | Nasıl |
|---|---|---|
| Çekirdek komut satırında `audit=` | **yok** | `/proc/cmdline` |
| `auditd` başlangıcı → ilk kural yükleme kaydı | **652 sn** (`DAEMON_START` epoch 1792257808, ilk `CONFIG_CHANGE add_rule` 1792258460) | ham `audit.log` |
| `chronyd` (VM açılışında, auditd'den **önce** başlamıştı) | `-S all` ile pid'ine bağlı geçici kural **0 kayıt** verdi; chrony günlüğü aynı sırada saat adımlaması gösteriyordu | geçici çalışma zamanı kuralı |
| Aynı `chronyd` **yeniden başlatılınca** | aynı kural 133 sn'de olay üretti; zaman ile ilgili tek syscall: **33 × `clock_adjtime` (305)**; `adjtimex`, `settimeofday`, `clock_settime` yok | geçici kural, ham günlük |
| Mevcut `time-change` kuralı | chrony'den **0** olay; yalnızca elle `date -s` (`syscall=227`) 1 olay üretti (pozitif kontrol) | ham günlük |
| `clock_adjtime` olay hızı | dakikada 17, 8, 8 (yeniden başlatma, `makestep`, `burst` sonrası; **kararlı durum ölçülmedi**) | zaman damgaları |

## Sorunlar

### P1. auditd'den önce başlamış süreçler denetlenmiyor
Gözlem: yeniden başlatma öncesi sıfır, sonrası olay. Bu, Linux denetiminin bilinen davranışıyla uyumlu (denetim bağlamı süreç oluşturulurken verilir); çekirdek
mekanizmasını ayrıca doğrulamadık, kanıtımız fark. Sonuç: `harden` bitince `auditd` "aktif" görünür ama ondan önce çalışan uzun ömürlü servisler (chrony,
sshd ana süreci, cron, rsyslog…) yeniden başlatılana kadar **görünmez**. Yeni oturum süreçlerinin (sshd'nin sonradan fork ettikleri) denetlenip
denetlenmediği **ölçülmedi** (girişler `USER_LOGIN` olarak göründü, ama bu PAM'in kendi kaydı olabilir).

### P2. `time-change` kuralı chrony'yi kapsamıyor
chrony saati `clock_adjtime` ile ayarlıyor, kural bunu izlemiyor. Kuralın amacı net değil: **kullanıcı müdahalesini** mi (elle `date -s`) yoksa **her** saat
değişimini mi yakalamak istiyoruz? Bu karar kuralın biçimini belirler (aşağıda).

### P3. Kurallar play sonunda yükleniyor
`augenrules --load` handler olduğundan, `auditd` başladıktan sonra play bitene kadar kurallar yok (bu denemede ~11 dk, çünkü arada AIDE ilk veritabanı üretildi).
Bu sürede `fail2ban`, `aide`, `ufw`, `ssh` rollerinin yaptığı değişiklikler izlenmiyor.

## Seçenekler

### P3 için (en küçük, en güvenli)
| | Ne | Artı | Eksi |
|---|---|---|---|
| **3a (öneri)** | Şablon görevinden hemen sonra handler'ı çalıştır (`meta: flush_handlers`) ya da kuralları servisten önce yükle | Pencere kapanır; davranış tek yönlü iyileşir | Çok küçük bir sıra değişikliği |
| 3b | Olduğu gibi bırak | Değişiklik yok | Yarım kapsam, belge gerekir |

### P1 için
| | Ne | Artı | Eksi |
|---|---|---|---|
| **1a** | GRUB'a `audit=1` | Önyüklemeden itibaren her süreç denetlenir (çekirdek davranışı, **doğrulanmadı**) | **Yeniden başlatma gerekir**; önyükleyici ayarı geri alma güvenlik ağımıza dahil değil; bulut imajlarında GRUB yapılandırması farklı olabilir; Raspberry Pi'de `cmdline.txt`; konteyner/LXC'de çekirdek denetimi yok |
| **1b** | `harden` sonunda seçili servisleri yeniden başlat | Reboot gerekmez | Servis kesintisi riski (özellikle `sshd`, `fail2ban`); hangi servisler? Kapsamı kullanıcıya bırakmak gerekir |
| **1c (öneri, ilk adım)** | Davranışı **değiştirme**; `audit`/durum eyleminde "auditd'den önce başlamış süreçleri" uyarı olarak raporla (örn. süreç başlangıç zamanı < auditd başlangıcı) ve `harden` sonunda "yeniden başlatın" notu ver | Güvenli, dürüst | Sorunu çözmez, sadece görünür kılar |
| 1d | Yalnızca belge (`known-issues.md`) | En ucuz | Kullanıcı farkında olmayabilir |

### P2 için
| | Ne | Not |
|---|---|---|
| 2a | Kuralı olduğu gibi bırak, amacı belgele ("kullanıcı müdahalesi") | Bugünkü davranış |
| 2b | `clock_adjtime` ekle | Chrony'nin her ayarı kayda girer; gürültü kararlı durumda ölçülmeli |
| **2c (öneri, doğrulanacak)** | Kullanıcı oturumundan gelen çağrıları izle (`-F auid>=1000 -F auid!=unset` deseni), `clock_adjtime` dahil | Daemon gürültüsünü eler, amaca (müdahale) uyar. **Doğrulanacak:** `auid` filtresi hem `date -s` (ssh oturumundan) hem chrony için beklendiği gibi davranıyor mu, VM'de ölçülmeli |

**Öneri sırası:** 3a → 1c (+1d) → P2'yi ölçüp karar ver → 1b'yi isteğe bağlı değişkenle, 1a'yı en son ve ayrı PR'da.

## Değişken önerisi (henüz yok)
| Değişken | Varsayılan | Anlam |
|---|---|---|
| `hardening_auditd_restart_services` | `[]` | `harden` sonunda yeniden başlatılacak servisler (1b); boşken hiçbir şey yeniden başlatılmaz |
| `hardening_auditd_grub_audit` | `false` | GRUB'a `audit=1` (1a); `true` yeniden başlatma gerektirir ve uyarı verir |
| `hardening_auditd_manage` | `true` | `false` = rol hiçbir şey yapmaz (kaçış anahtarı; "alan başına aç/kapa" fikriyle uyumlu) |

Eklenirse `component.yml` `vars`'ına tür/varsayılan/açıklama zorunlu (`check-consistency.py` denetler).

## Etkileşimler ve riskler
- **Geri alma:** auditd ve GRUB ayarı `hardening_rollback` kapsamında **değil**; `audit=1` bir yeniden başlatma sonrası etkili olur ve elle geri alınır.
- **`--check`:** `audit=1` ve servis yeniden başlatma `--check`'te atlanmalı (rol zaten servis başlatmayı atlıyor).
- **Zaman rolü** tasarım notu (`docs/design/zaman-ntp.md`, henüz birleşmemiş ayrı bir yerel dalda): chrony'nin `clock_adjtime` hızı ve P2 kararı ona bağlı.
- **Erişim kaybı:** 1b'de `sshd` yeniden başlatmak mevcut bağlantıyı kesmez ama geçici erişim sorunu yaratabilir; `harden` zaten bağlantı doğrulaması yapıyor, yine de `sshd`'yi listede varsayılan yapmamak gerekir.
- **Gürültü/disk:** denetim günlüğü büyür (bu denemede ham günlük ~250 KB idi, `harden` bittikten kısa süre sonra); rotasyon ve boyut ayarı bu notun kapsamı dışında. Kural eklemek (örn. `clock_adjtime`) bu hızı artırır.

## Test planı
1. **Birim:** şablon golden testi (mevcut `test_templates.py` deseni); P3 sıra değişikliği için görev sırası testi (`--list-tasks`).
2. **LAB (Docker) yetersiz:** LAB'da çekirdek denetimi yok, auditd taklit ediliyor (sshpocket reposundaki `test/e2e/lab/README.md`); bu notun ölçümleri **gerçek VM** gerektirir.
3. **Gerçek VM:** ölçüm yöntemi tekrarlanabilir (pid'e bağlı geçici `-S all` kuralı + ham `audit.log`); `audit=1` için **yeniden başlatma sonrası** chronyd'nin denetlendiği doğrulanmalı (snapshot gerekir).
4. **Mutasyon:** her değişiklik için eski davranışa dönünce test düşmeli.

## Açık sorular (cevaplanmadan kod yazılmaz)
1. `audit=1` ile yeniden başlatmadan sonra `chronyd` ve `sshd` ana süreci gerçekten denetleniyor mu? (VM'de yeniden başlatma ile doğrulanacak.)
2. `sshd`'nin sonradan fork ettiği oturum süreçleri, ana süreç denetim dışıyken denetleniyor mu?
3. Hangi servisler 1b listesinde varsayılan önerilmeli (varsa)? Servis kesintisi kabul edilebilir mi?
4. `time-change` kuralının amacı "kullanıcı müdahalesi" mi, "her değişim" mi? (2a/2b/2c seçimi.) CIS Benchmark PDF'i ile karşılaştırılacak.
5. P3 sıra değişikliği (3a) başka bir şeyi bozar mı (ilk koşuda auditd + kuralların yüklenme süresi, `--check` davranışı)?
6. Raspberry Pi / bulut imajı / LXC için `audit=1` stratejisi (ayrı profiller).

## Kapsam dışı
- Kural setini genişletmek (ayrı konu: CIS eşlemesi).
- Kuralları değiştirilemez kılmak (`-e 2`), uzak günlük gönderimi, `auditd.conf` rotasyon/boyut ayarları.
