# Zaman senkronizasyonu rolü (tasarım notu, kod yok)

> **Durum: yalnızca tasarım.** Bu belge bir rolün nasıl olabileceğini ve karar bekleyen konuları yazar; `harden.yml` bu belgede anlatılan
> hiçbir şeyi yapmaz. "Doğrulanacak" işaretli yerler kontrol edilmeden kod yazılmaz.

## Neden
- Saat kayması sessiz ama pahalı bir sorundur: TLS/`apt` doğrulaması, `auditd` ve günlük zaman damgaları, AIDE, fail2ban `bantime` hesapları saate bağlıdır.
- Somut vaka bizde yaşandı: Proxmox snapshot'ına dönünce test VM'inin saati ~28 saat geride kaldı ve `apt`/TLS hataları çıktı
  (`docs/verification-log.md`, `HOWTO.md` §7). Çözüm bugün elle: `chronyc makestep`.
- ROADMAP'te "Zaman senkronizasyonu rolü" maddesi var (`docs/ROADMAP.md`).

## Bugünkü durum
| Konu | Durum | Kaynak |
|---|---|---|
| Repoda zaman rolü | **Yok** | `roles/` |
| Ubuntu 26.04 varsayılan servisi | **chrony 4.8 (`+NTS`)** aktif ve etkin; `systemd-timesyncd` **kurulu değil** (`not-found`); `ntpsec`/`ntpd-rs` yok | **test VM'inde okundu** (2026-10-17) |
| Varsayılan kaynaklar | `/etc/chrony/sources.d/ubuntu-ntp-pools.sources`; gözlenen kaynaklar Canonical **NTS** sunucuları (`ntp-nts-*.canonical.com`). `conf.d/ubuntu-nts.conf` bootstrap sertifikasını çok geniş geçerlilikle güvenir: "çok büyük ilk saat kayması olan sistemler NTS kullanabilsin" diye | test VM'inde okundu |
| Drop-in dizinleri | `chrony.conf` içinde `confdir /etc/chrony/conf.d` ve `sourcedir /etc/chrony/sources.d` **var** (ayrıca `sourcedir /run/chrony-dhcp`: DHCP'den gelen NTP kaynakları da kabul edilir) | test VM'inde okundu |
| Adımlama politikası | Varsayılan `makestep 1 3` ve `rtcsync` | test VM'inde okundu |
| `ntpd-rs` | Canonical 26.10 için test, varsayılan değişim daha sonra; 26.04'te **yok** | duyuru; kesin tarih doğrulanmadı |
| İki servis birlikte | Çakışır; chrony kurulunca timesyncd devre dışı kalır | genel bilgi, doğrulanacak |
| LAB (Docker) | Hiçbir zaman servisi çalışmıyor; `timedatectl`: `NTP service: n/a`, saat çalıştıran VM'den gelir | LAB'da okundu (2026-10-17) |
| Test VM (Proxmox) | Ubuntu 26.04.1; **auditd kurulu değil** (`auditctl` yok; temiz snapshot durumu). Saat **~8 gün geride** (VM `2026-10-09 13:27 UTC`, Mac `2026-10-17 17:09 UTC`) ama `timedatectl` "System clock synchronized: yes" diyor ve `chronyc tracking` bayat bir "0,016 s yavaş" gösteriyor. `journalctl -u chrony`: kaynaklar "Root distance … exceeds maxdistance of 3.000 seconds" ile reddediliyor. **Gözlem ve düzeltme (2026-10-17):** adımlamadan önce chrony ofseti **zaten ölçmüştü** (`System time: 704508 seconds slow of NTP time`, kaynak seçili) ama varsayılan `makestep 1 3` yalnızca başlangıçtaki ilk 3 güncellemede adımlar; snapshot dönüşü yeniden başlatma olmadığından **adımlamadı**, `timedatectl` de "synchronized: yes" demeye devam etti. Elle `chronyc makestep` tek seferde düzeltti (`System clock was stepped by 704508.177569 seconds`); düzeltmeden hemen sonra `timedatectl` kısa süre "synchronized: no" gösterdi (çekirdek bayrağı bir sonraki chrony güncellemesinde döner, tam geri dönüş süresi ölçülmedi) | test VM'inde okundu (2026-10-17) |

## Hedef (neyi garanti etmek istiyoruz)
1. Sunucuda **tek** zaman servisi aktif, saat senkron.
2. Zaman kaynakları **bilinçli** seçilmiş (iç NTP sunucusu olan ortamlar kendi listesini verebilir), mümkünse doğrulamalı (NTS).
3. Sunucu **istemci**dir: dışarıdan zaman isteği dinlemez/yanıtlamaz (`allow` yok).
4. Snapshot/askıdan dönüş gibi büyük kaymalarda saat **kontrollü** düzelir.
5. Durum denetlenebilir: `audit.yml` ya da bir `status` eylemi senkron olup olmadığını söyler.

## Seçenekler
| | Ne yapar | Artı | Eksi |
|---|---|---|---|
| **A. Yalnızca doğrula** | Hiçbir şey yapılandırmaz; servis aktif mi, senkron mu kontrol edip uyarır | En güvenli, davranış değişmez | Kaynak/kayma sorunlarını çözmez |
| **B. Dağıtım servisini yapılandır (öneri)** | Mevcut servisi (26.04'te chrony) **drop-in** dosyalarıyla yapılandırır: kaynaklar, `makestep` politikası, dinleme kapalı | Dağıtımın ana dosyasına dokunmaz, geri alması kolay | Her dağıtım/sürüm için ayrı eşleme gerekir |
| **C. Servisi zorla değiştir** | Her yerde chrony kur, diğerini kapat | Tek davranış | Dağıtım varsayılanıyla savaşır, 24.04/Debian'da riskli |

**Öneri: B**, A'nın doğrulamasıyla birlikte. Servis adı `vars/<dagitim>-<surum>.yml` içinde tutulur (bugünkü OS katmanı mekanizması), yeni sürüm eklemek bir satır olur.

## Önerilen yapı
```
roles/hardening_time/
  defaults/main.yml        # değişkenler (aşağıda)
  tasks/main.yml           # doğrula -> drop-in yaz -> servis -> senkron bekle/denetle
  templates/               # chrony drop-in şablonları (golden testli)
  handlers/main.yml        # servis yeniden başlatma
vars/ubuntu-26.04.yml      # hardening_time_daemon: chrony   (yeni anahtar)
playbooks/harden.yml       # roles listesine { role: hardening_time, tags: [time] }
```
Yapılandırma dosya yolları **doğrulandı** (26.04 test VM'i): `confdir /etc/chrony/conf.d` ve `sourcedir /etc/chrony/sources.d` ana dosyada tanımlı;
rol yeni drop-in dosyaları ekler, `chrony.conf` ana dosyasına dokunmaz.

### Değişkenler (öneri)
| Değişken | Varsayılan | Anlam |
|---|---|---|
| `hardening_time_manage` | `true` | `false` = rol hiçbir şey yapmaz (kaçış anahtarı; "alan başına aç/kapa" fikriyle uyumlu) |
| `hardening_time_servers` | `[]` | Boşsa **dağıtım varsayılanı** kullanılır; doluysa bu liste |
| `hardening_time_nts` | dağıtım varsayılanı | 26.04'te Canonical kaynakları **zaten NTS**. Rol bunu bozmamalı; kendi `servers` listesi verilirse NTS'siz kaynaklar için `false` gerekir, aksi hâlde senkron bozulur |
| `hardening_time_makestep` | dağıtım varsayılanı | Büyük kaymada adımlama politikası (snapshot dönüşü için) |
| `hardening_time_daemon` | OS dosyasından | `chrony` \| `systemd-timesyncd` (kullanıcı değiştirmez; `vars/`) |

Değerler `component.yml` `vars`'a eklenirse tür/varsayılan/açıklama zorunlu (`check-consistency.py`).

## Etkileşimler ve riskler
- **auditd ve zaman: iki ayrı bulgu (ölçüldü, test VM'i, Ubuntu 26.04.1, x86_64, çekirdek 7.0.0-38-generic, auditd 4.1.2, chrony 4.8).**
  Kuralımız: `-a always,exit -F arch=b64 -S adjtimex,settimeofday,clock_settime -k time-change`
  (`roles/hardening_auditd/templates/hardening.rules.j2`).
  1. **chrony `clock_adjtime` (syscall 305) kullanıyor; kuralımız onu kapsamıyor.** `chronyd`'yi yeniden başlattıktan sonra yalnızca `chronyd`
     süreçlerine geçici bir "tüm syscall'lar" kuralı bağlandı (kalıcı değil, silindi): 133 saniyede **33 `clock_adjtime`** çağrısı; `adjtimex`,
     `settimeofday` ve `clock_settime` **hiç yok**. Yani mevcut `time-change` kuralı chrony'nin saat ayarını **hiç yakalamaz** (yalnızca elle `date -s`
     gibi çağrıları yakalar; pozitif kontrol: `date`, `syscall=227`, 1 olay).
  2. **auditd'den önce başlamış süreçler denetlenmiyor.** İlk ölçümde (auditd kurulduktan sonra 21 dk) chrony ham günlükte **hiç** görünmüyordu:
     VM açılışında başlamış (auditd'den önce), `harden` ile auditd sonradan kurulmuştu. Hem `time-change` kuralı hem `chronyd`'ye bağlı "tüm syscall'lar" kuralı
     0 olay verdi, chrony'nin kendi günlüğü ise iki adımlamayı kaydetmişti. **`chrony` yeniden başlatılınca aynı kural olay üretmeye başladı.** Yani
     denetim yalnızca değişiklikten sonra başlayan süreçleri görüyor; çekirdek komut satırında `audit=1` de yok (`/proc/cmdline`, boş). Bu, bilinen Linux
     denetim davranışıyla uyumlu; çekirdek mekanizmasını ayrıca doğrulamadık, gözlem yeniden başlatma öncesi/sonrası farkına dayanıyor.
  - **Gürültü tahmini (dikkat: kaba).** `clock_adjtime` eklenseydi: dakikada 17, 8, 8 olay (yeniden başlatma, `makestep` ve `burst` sonrası; yeniden
    başlatmadan hemen sonra chrony hızlı yoklar, kararlı durumda daha az olabilir). Kararlı durum **ölçülmedi**; en kötü durum günde ~10 binlerce kayıt.
    Karar öncesi yeniden başlatmadan uzak, sakin bir dönemde ölçülmeli.
  - **Sonuç:** (a) `clock_adjtime`'ı kurala eklemek görünürlüğü getirir ama gürültü üretir; (b) bu bulgu zaman rolünden bağımsız ve daha geniş:
    `hardening_auditd` yalnızca auditd'yi kurup başlatıyor, ondan önce başlamış servisler (chrony, sshd, cron...) yeniden başlatılana kadar **denetlenmiyor**.
    Çözüm seçenekleri: GRUB'a `audit=1` (yeniden başlatma gerekir, önyükleyici ayarı geri almamıza dahil değil) ve/veya `harden` sonunda önemli servisleri
    yeniden başlatmak. İkisi de davranışı değiştirir; ayrı bir konu olarak ele alınmalı (aşağıda açık soru 5).
- **DHCP kaynakları.** `sourcedir /run/chrony-dhcp` ile DHCP sunucusunun verdiği NTP kaynakları kabul edilir. Güvenilmeyen ağlarda bu bir tercih konusudur
  (sertleştirme bunu kapatmalı mı: açık soru 3).
- **ufw.** Varsayılan `allow outgoing` olduğundan NTP (UDP 123) ve NTS-KE (TCP 4460) çıkışı çalışır. Operatör çıkışı kapatırsa bu portları açması gerekir; belgelenmeli.
- **Geri alma güvenlik ağı** yalnızca sshd drop-in ve ufw'yi kapsar; zaman ayarları **geri alınmaz**. Büyük bir adımlama (saat birdenbire değişir) çalışan servisleri,
  `cron` ve token/sertifika süreleri olan uygulamaları etkileyebilir.
- **Çakışma:** `docs/known-issues.md`'ye eklenmeli (hangi sunucuda kendi NTP'si/PTP'si varsa `hardening_time_manage: false`).
- **Konteyner/LAB:** saat konteyner değil, onu çalıştıran VM çekirdeğine aittir. Zaman servisi LAB'da **çalıştırılmamalı** (paylaşılan saati kaydırabilir).

## Test planı
1. **Şablonlar:** golden dosya testi (mevcut `test_templates.py` deseni); varsayılan ve doluysa `servers`/`nts` için ayrı golden.
2. **Birim:** `--check` ile; `hardening_time_manage: false` iken hiçbir görev değişmez.
3. **LAB:** yalnızca yapılandırma dosyalarının yazıldığını ve servisin **başlatılmadığını** doğrular (çalıştırmak paylaşılan saati etkileyebilir).
4. **Gerçek sunucu/VM (zorunlu):** kayma simülasyonu (saati elle geri al; test VM'i zaten ~8 gün geride, gerçek bir örnek) ve `makestep` davranışı; auditd ölçümü **yapıldı** (yukarıda); kalan: kararlı durum gürültüsü (sakin dönemde).

## Açık sorular (cevaplanmadan kod yazılmaz)
1. ~~Hedefte chrony mı, hangi sürüm?~~ **Kapandı:** chrony 4.8 (+NTS), timesyncd kurulu değil (test VM'i, 2026-10-17).
2. ~~Drop-in dizinleri okunuyor mu?~~ **Kapandı:** `confdir` ve `sourcedir` ana dosyada tanımlı.
3. DHCP'den gelen NTP kaynakları (`sourcedir /run/chrony-dhcp`) kabul edilsin mi? Güvenilmeyen ağlarda kapatmak mantıklı; değişkenle mi?
4. `makestep` için varsayılan ne olmalı? Test VM'inde snapshot dönüşünde `makestep 1 3` sorunu çözmedi (saat ~8 gün geride kaldı), elle `chronyc makestep` çözdü. Seçenekler: (a) varsayılanı korumak ve durumu yalnızca **uyarmak/raporlamak** (`audit`/`status` "chrony ofseti > N sn, `chronyc makestep` gerekli" der), (b) otomatik adımlama (`makestep 1 -1`), sürpriz saat atlaması riski taşır (cron, token/sertifika süreleri). Öneri: önce (a); (b) ölçülmeden önerilmez.
5. ~~auditd `time-change` gürültüsü?~~ **Ölçüldü** (yukarıda): mevcut kural chrony'yi yakalamıyor (`clock_adjtime` kapsam dışı) ve auditd'den önce başlayan süreçler denetlenmiyor.
   Yeni sorular: `clock_adjtime` kurala eklensin mi (gürültü karşılığı görünürlük)? `audit=1` ve/veya servis yeniden başlatma `hardening_auditd` kapsamına girsin mi? Kararlı durum gürültüsü sakin dönemde ölçülmeli.
6. Varsayılan kaynak listesi ortamınızda erişilebilir mi (kurumsal/izole ağlarda iç NTP gerekir)?
7. 24.04 / Debian için ne yapılacak (timesyncd mi, chrony mi)? OS katmanı eklendiğinde ayrıca karar.

## Kapsam dışı
- PTP/donanım saati, GPS kaynakları.
- Çoklu zaman bölgesi/yerelleştirme (`timezone`) ayarı.
- Kendi NTP sunucumuzu çalıştırmak.
