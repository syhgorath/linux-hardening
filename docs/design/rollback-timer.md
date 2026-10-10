# Tasarım: hedef taraflı geri alma zamanlayıcısı

> **Durum: kararlar onaylandı (§9), uygulama başladı.** Uygulama ayrı PR'larla (§10) ve **gerçek bir hedefte denenerek**
> yapılıyor. Sınırlar ve açık riskler §7'de.

## 1. Amaç
`harden.yml` ufw ve SSH ayarlarını değiştirirken sunucuya **erişimin kalıcı olarak kaybedilmemesi**: değişiklik
yapıldıktan sonra erişim doğrulanamazsa, **bağlantıdan bağımsız** olarak sunucu kendi önceki durumuna dönmeli.

## 2. Sorun: bugünkü geri alma neyi kaçırıyor
Şu an `hardening_verify_access` yeni bir SSH bağlantısı dener; başarısızsa **hâlâ açık olan eski oturum**
üzerinden `rescue` ile geri alır. Bu, 10 Ekim 2026'daki canlı denemede (test VM'i, Ubuntu 26.04.1) doğru çalıştı
(`rescued=1`, 82 sn'lik koşu). Ama şunlara dayanıyor:

| Durum | Bugünkü davranış |
|---|---|
| Eski oturum da kopar (ağ düşer, Mac uyur, ControlPersist biter) | `rescue` çalışamaz, **sunucu kilitli kalır** |
| Controller (Mac) kitlenir/yeniden başlar, Ansible ölür | `rescue` hiç çalışmaz |
| Sunucu değişiklik sırasında yeniden başlar | Yarım uygulanmış durumda açılır, geri alma yok |
| Zaten sertleşmiş sunucuda doğrulama başarısız olur | `rescue` drop-in'i **siler**: sunucu başlangıçtan **daha zayıf** olur |

Son satır canlı denemede görüldü: `passwordauthentication no` → `yes`, `maxauthtries 3` → `6`.

## 3. Hedefler ve hedef olmayanlar
**Hedefler**
- Erişim kaybı durumunda **sunucu kendini** (controller'a ihtiyaç duymadan) geri alır.
- Geri alma **önceki durumu** geri yükler (siler değil): sertleşmiş sunucu daha zayıf kalmaz.
- Kontrol makinesi dönünce durumu görmek ve "tamam, dur" demek için basit komutlar.
- Yeniden başlatmaya dayanıklı.
- `--check` ve idempotency (`changed=0`) bozulmaz.

**Hedef olmayanlar**
- Paket/sysctl/auditd/fail2ban/AIDE değişikliklerini geri almak (yalnızca ufw ve SSH).
- Ağ düzeyindeki her kesintiyi kapsamak (yalnızca "yeni bağlantı doğrulanamadı" sinyali).
- Sunucuya erişimi tamamen kaybetmiş birini kurtarmak; son çare Proxmox konsolu/snapshot kalır.

## 4. Tasarım

### 4.1 Bileşenler (hedef sunucuda)
| Parça | Yol | Rol |
|---|---|---|
| Durum yedeği | `/var/lib/hardening-rollback/state/` | Değişiklikten **önceki**: `00-hardening.conf` içeriği (varsa), ufw durumu (active/inactive) ve kuralları |
| Geri alma betiği | `/usr/local/sbin/hardening-rollback` | Yedekten önceki durumu geri yükler; **idempotent** |
| İşaret dosyası | `/var/lib/hardening-rollback/armed` | "Kuruldu ama onaylanmadı" demek. Betik **yalnızca bu dosya varsa** geri alır |
| Zamanlayıcı | `hardening-rollback.timer` + `.service` (kalıcı unit) | `OnActiveSec=` (kurulumdan N sn sonra) ve `OnBootSec=` (yeniden başlatmadan sonra) |

İşaret dosyası + kalıcı unit seçildi çünkü `systemd-run --on-active` gibi **geçici** zamanlayıcılar yeniden
başlatmada kaybolur (bkz. §6, senaryo 4).

### 4.2 Akış
```
1. ARMA     (hardening_ufw ve hardening_ssh'tan HEMEN ÖNCE)
   - önceki durumu yedekle
   - armed işaret dosyasını yaz
   - timer'ı başlat (N sn sonra betiği çalıştırır)

2. DEĞİŞTİR (ufw kuralları, ufw enable, sshd drop-in, reload)

3. DOĞRULA  (hardening_verify_access: kontrol makinesinden YENİ ssh bağlantısı)
   - başarılı  -> DISARM: işaret dosyasını sil, timer'ı durdur
   - başarısız -> rescue betiği HEMEN çalıştırır (şimdiki gibi) ve disarm eder
   - hiçbir şeye ulaşılamıyor -> disarm gelmez -> N sn sonra timer betiği çalıştırır
```

### 4.3 Geri alma betiği (`hardening-rollback`)
1. `armed` yoksa **hiçbir şey yapmaz** ve 0 ile çıkar (idempotent, onaylanmış değişikliğe dokunmaz).
2. Yedekteki `00-hardening.conf` varsa **geri yazar**, yoksa mevcut dosyayı siler.
3. `sshd -t` ile doğrular, ardından sshd'yi `reload` eder.
4. ufw'yi yedekteki duruma getirir (önceden aktifse aktif bırakır, kapalıysa kapatır).
5. `armed`'ı siler ve neyi geri aldığını journald'a yazar (`logger -t hardening-rollback`).

### 4.4 Komutlar (kontrol makinesinde)
| Komut | Ne yapar |
|---|---|
| `playbooks/rollback.yml -t status` | Zamanlayıcı kurulu mu, kaç sn kaldı, `armed` var mı |
| `playbooks/rollback.yml -t disarm` | "Değişiklik iyi": `armed`'ı siler, timer'ı durdurur |
| `playbooks/rollback.yml -t now` | Hemen geri al (elle) |

### 4.5 Değişkenler
| Değişken | Varsayılan | Anlam |
|---|---|---|
| `hardening_rollback_enabled` | `true` | `false` = güvenlik ağı kapalı (bilinçli, belgeli kaçış; uyarı verir) |
| `hardening_rollback_timeout` | `300` | Saniye; uzun koşuda yanlışlıkla tetiklenmesin diye ufw/ssh'tan **hemen önce** kurulur |

## 5. `--check`, idempotency, güvenlik
- **`--check`:** arma/disarm atlanır; durum yedeği alınmaz; hiçbir şey değişmez.
- **Idempotency:** arma/disarm `changed_when: false`; değişiklik yoksa timer hemen disarm edilir. Zaten
  sertleşmiş sunucuda yedek = mevcut durum olduğundan geri alma **no-op** olur.
- **İzinler:** `/var/lib/hardening-rollback` 0700 root; betik 0750 root; içerik gizli bilgi taşımaz.
- **Girdi doğrulama:** betik ve unit içeriği şablonla üretilir; dışarıdan gelen değişkenler (yalnızca saniye
  değeri) tamsayı olarak doğrulanır, kabuğa ham aktarılmaz.
- **Tek zamanlayıcı:** ikinci bir koşu mevcut `armed`'ı bulursa devam etmeden önce açıkça uyarır/durur
  (iki koşunun birbirinin yedeğini ezmesini önlemek için).

## 6. Senaryolar (davranış tablosu)
| # | Senaryo | Sonuç |
|---|---|---|
| 1 | Değişiklik iyi, doğrulama başarılı | Disarm; hiçbir şey geri alınmaz |
| 2 | Doğrulama başarısız, eski oturum açık | `rescue` hemen geri alır (öncekine döner), disarm |
| 3 | Controller kitlenir, N sn içinde döner | `status` ile görülür; erişim iyiyse `disarm` |
| 4 | Sunucu değişiklikten sonra yeniden başlar | `OnBootSec` timer'ı + `armed` sayesinde açılışta geri alınır |
| 5 | Controller N sn'den uzun kapalı | Sunucu kendini geri almıştır; dönünce `harden.yml` yeniden çalıştırılır |
| 6 | Uzun bir rol (örn. AIDE ilk kurulum) sürerken | Arma ufw/ssh'tan **önce** ve onlardan sonra disarm; uzun roller aralıkta çalışmaz |
| 7 | `systemd-run`/systemd yok | Güvenlik ağı kurulamaz: ufw/ssh'a **dokunmadan durur** (açık hata) |

## 7. Bilinen riskler ve ödünleşimler
- **Gereksiz geri alma:** controller N sn'den uzun donarsa ve değişiklik aslında iyiydiyse sunucu geri alır.
  Bilinçli seçim: *erişim kaybı yerine gereksiz geri alma*.
- **Kısa süreli zayıflama olasılığı:** geri alma, önceki durumu geri yüklediği için sertleşmiş sunucuyu zayıflatmaz;
  ama sunucu daha önce sertleşmemişse eski (zayıf) hâline döner. Bu beklenen davranıştır.
- **Saat/zamanlama:** `OnActiveSec` sunucunun saatine bağlı değil (monoton), `OnBootSec` de öyle.
- **ufw geri yüklemesi:** kural listesinin birebir geri yazımı için `ufw` komutları yeterli mi, yoksa
  `/etc/ufw/*.rules` dosyalarını yedeklemek mi gerekir? (Açık soru, §9.)

## 8. Test planı
**Yerel (CI):**
- Geri alma betiği mantığı (sahte dizin/komutlarla): `armed` yoksa no-op, yedek varsa geri yükler, yoksa siler.
- Şablonlanan unit/betikte değişken doğrulaması; `--check`'te atlanma; `changed=0`.
- Yeni görevler için `ansible-lint`, `yamllint`, golden dosyalar.

**Gerçek VM (elle, snapshot ile):**
1. Başarılı akış: arma → değiştir → doğrula → disarm; `changed=0` ikinci koşuda.
2. Doğrulama başarısız (engel dosyasıyla): `rescue` önceki durumu geri yüklüyor mu (silmiyor mu).
3. **Controller ölümü:** koşu sırasında `ansible-playbook` süreci öldürülür; N sn sonra sunucu kendini geri alır.
4. **Yeniden başlatma:** `armed` varken sunucu yeniden başlatılır; açılışta geri alınır.
5. Disarm: süre dolmadan `disarm` → geri alma tetiklenmez.
6. Zaten sertleşmiş sunucuda doğrulama başarısızlığı: sunucu **başlangıçtan zayıf kalmaz**.

## 9. Kararlar (kullanıcı onayı: varsayılanlarla ilerle)
| # | Soru | Karar | Not |
|---|---|---|---|
| 1 | Varsayılan açık mı? | **Açık** (`hardening_rollback_enabled: true`) | Güvenlik ağı olmadan ufw/ssh'a dokunmak daha riskli; kapatmak bilinçli ve uyarılı |
| 2 | Süre | **300 sn**, `30..3600` aralığında doğrulanır | |
| 3 | ufw yedeği | **Dosya yedeği** (`/etc/ufw/ufw.conf`, `user.rules`, `user6.rules`) + aktif/pasif durumu | İlk öneri "komutla" idi; kural listesini `ufw` komutlarıyla birebir yeniden kurmak kırılgan (sıra, IPv6, varsayılan politikalar). Dosyaları geri yazıp `ufw --force enable/disable` daha doğru |
| 4 | `status`/`disarm` menüde mi? | **Evet**, `component.yml` eylemleri (PR 4) | sshpocket tarafı ayrı |
| 5 | Bildirim | Playbook mesajı + `journald` (`logger -t hardening-rollback`) | sshpocket'te gösterim sshpocket tarafının işi |

## 9b. Uygulama kararları
- Mantık **kurulu bir betikte** (`/usr/local/sbin/hardening-rollback`: `arm` / `disarm` / `restore` / `status`); Ansible ince kalır.
  Böylece betik yerelde sahte komutlarla test edilebilir (`HR_ROOT`, `HR_UFW`, `HR_SSHD`, `HR_SYSTEMCTL`).
- Zamanlayıcı yalnızca **armed iken enable** edilir; disarm'da `disable --now` (kalıcı iz bırakmaz). `OnActiveSec`
  kullanıldığı için yeniden başlatmada da, timer yeniden etkinleştirildiğinden N sn sonra tetiklenir.
- Zaten `armed` ise **ilk yedek korunur**, yalnızca geri sayım yenilenir (gerçek "önceki durum" ezilmez).
- **PR 1 playbook'lara BAĞLANMAZ** (rol ölü kod olarak gelir). Bağlanmadan arm eden ama disarm etmeyen bir sürüm,
  N sn sonra sertleştirmeyi geri alırdı; bağlama ve disarm aynı PR'da (PR 2) yapılır.

## 10. Uygulama planı (ayrı PR'lar)
| PR | İçerik | Canlı VM |
|---|---|---|
| **0** | Bu tasarım notu | Gerekmez |
| **1** | `hardening_rollback` rolü: betik, kalıcı unit, arma/disarm, yedek | Evet |
| **2** | `hardening_verify_access` entegrasyonu; `rescue`'i "sil" yerine "önceki duruma dön" yap | Evet |
| **3** | `playbooks/rollback.yml` (`status`/`disarm`/`now`), HOWTO | Evet |
| **4** | `component.yml` eylemleri ve sshpocket'e not | Hayır |

PR 2, mevcut `rescue` davranışını değiştirir (siler → önceki duruma döner); bu **davranış değişikliği** olarak
işaretlenecek ve `docs/decisions.md`'ye yazılacaktır.
