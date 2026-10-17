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
| Ubuntu 26.04 varsayılan servisi | **chrony** (üçüncü taraf kaynaklar; resmî sürüm notu doğrudan adlandırmıyor). `systemd-timesyncd` yedek/yükseltme durumunda olabilir. **Doğrulanacak:** hedefte `systemctl is-active chrony` ve `chronyc -v` | arama + bizim `chronyc makestep` notumuz |
| `ntpd-rs` | Canonical 26.10 için test, varsayılan değişim daha sonra; 26.04'te **yok** | duyuru; kesin tarih doğrulanmadı |
| İki servis birlikte | Çakışır; chrony kurulunca timesyncd devre dışı kalır | genel bilgi, doğrulanacak |
| LAB (Docker) | Hiçbir zaman servisi çalışmıyor; `timedatectl`: `NTP service: n/a`, saat çalıştıran VM'den gelir | LAB'da okundu (2026-10-17) |
| Test VM (Proxmox) | Ağdan ulaşılamadı; chrony kullandığı **varsayım** (`chronyc makestep` notundan) | doğrulanmadı |

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
Yapılandırma dosya yolları (chrony için `conf.d`/`sources.d` drop-in dizinleri) **doğrulanacak**; dağıtım paketinin gerçekten bu dizinleri
okuduğuna bakılmadan şablon yazılmaz.

### Değişkenler (öneri)
| Değişken | Varsayılan | Anlam |
|---|---|---|
| `hardening_time_manage` | `true` | `false` = rol hiçbir şey yapmaz (kaçış anahtarı; "alan başına aç/kapa" fikriyle uyumlu) |
| `hardening_time_servers` | `[]` | Boşsa **dağıtım varsayılanı** kullanılır; doluysa bu liste |
| `hardening_time_nts` | `false` | NTS (doğrulamalı zaman). Kaynaklar NTS destekliyorsa açılır; destek yoksa açmak senkronu **bozar**, bu yüzden varsayılan kapalı |
| `hardening_time_makestep` | dağıtım varsayılanı | Büyük kaymada adımlama politikası (snapshot dönüşü için) |
| `hardening_time_daemon` | OS dosyasından | `chrony` \| `systemd-timesyncd` (kullanıcı değiştirmez; `vars/`) |

Değerler `component.yml` `vars`'a eklenirse tür/varsayılan/açıklama zorunlu (`check-consistency.py`).

## Etkileşimler ve riskler
- **auditd gürültüsü (önemli).** Kurallarımızda zaman değişimi izleniyor: `-a always,exit -F arch=b64 -S adjtimex,settimeofday,clock_settime -k time-change`
  (`roles/hardening_auditd/templates/hardening.rules.j2`). Zaman servisi saati ayarlarken `adjtimex` çağırır; bu kural **çok sayıda olay**
  üretebilir. Etkisi **denenmedi** (LAB'da gerçek denetim yok). Ölçülmeden karar verilmez; seçenekler: kuralı servis hesabı hariç tutacak şekilde
  daraltmak ya da yalnızca `settimeofday`/`clock_settime` izlemek.
- **ufw.** Varsayılan `allow outgoing` olduğundan NTP (UDP 123) ve NTS-KE (TCP 4460) çıkışı çalışır. Operatör çıkışı kapatırsa bu portları açması gerekir; belgelenmeli.
- **Geri alma güvenlik ağı** yalnızca sshd drop-in ve ufw'yi kapsar; zaman ayarları **geri alınmaz**. Büyük bir adımlama (saat birdenbire değişir) çalışan servisleri,
  `cron` ve token/sertifika süreleri olan uygulamaları etkileyebilir.
- **Çakışma:** `docs/known-issues.md`'ye eklenmeli (hangi sunucuda kendi NTP'si/PTP'si varsa `hardening_time_manage: false`).
- **Konteyner/LAB:** saat konteyner değil, onu çalıştıran VM çekirdeğine aittir. Zaman servisi LAB'da **çalıştırılmamalı** (paylaşılan saati kaydırabilir).

## Test planı
1. **Şablonlar:** golden dosya testi (mevcut `test_templates.py` deseni); varsayılan ve doluysa `servers`/`nts` için ayrı golden.
2. **Birim:** `--check` ile; `hardening_time_manage: false` iken hiçbir görev değişmez.
3. **LAB:** yalnızca yapılandırma dosyalarının yazıldığını ve servisin **başlatılmadığını** doğrular (çalıştırmak paylaşılan saati etkileyebilir).
4. **Gerçek sunucu/VM (zorunlu):** kayma simülasyonu (saati elle geri al) ve `makestep` davranışı; auditd olay sayısı ölçümü. Test VM şu an ağdan ulaşılamıyor.

## Açık sorular (cevaplanmadan kod yazılmaz)
1. Hedefte gerçekten chrony mı çalışıyor, hangi sürüm, hangi kaynaklar (`chronyc sources`)? Test VM'inde ve LAB dışı bir 26.04'te doğrulanmalı.
2. Dağıtımın chrony paketi `conf.d`/`sources.d` drop-in dizinlerini okuyor mu?
3. Varsayılan kaynak listesi ortamınızda erişilebilir mi (kurumsal/izole ağlarda iç NTP gerekir)?
4. `makestep` için varsayılan ne olmalı, snapshot dönüşünde otomatik adımlama istenir mi, yoksa elle mi kalmalı (sürpriz saat atlaması riski)?
5. auditd `time-change` kuralı bu rolle birlikte ne olacak (yukarıdaki gürültü)?
6. 24.04 / Debian için ne yapılacak (timesyncd mi, chrony mi)? OS katmanı eklendiğinde ayrıca karar.

## Kapsam dışı
- PTP/donanım saati, GPS kaynakları.
- Çoklu zaman bölgesi/yerelleştirme (`timezone`) ayarı.
- Kendi NTP sunucumuzu çalıştırmak.
