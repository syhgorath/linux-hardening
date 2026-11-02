# Tasarım: sunucu eklerken platform seçimi

> **Durum: ÖNERİ (kod yok); `apply_vars` kullanıcı tarafından onaylandı, `requires_vars` onay bekliyor.** sshpocket koordinatörüyle kullanıcının ilkeleri temel alındı; denenmedi.
> Bu not `component.yml`'i, rolleri ya da testleri DEĞİŞTİRMEZ. Karar ve uygulama ayrı PR'larla gelir; test planı §9, açık sorular §10.

## 1. Sorun
Kullanıcı USB'deki `fizikiproxmox` sunucusu için `preview` çalıştırdı ve "Bu sunucu bir Proxmox VE hostu, `generic` platformla
sertleştirilmez" hatasını aldı: `hardening_platform=proxmox-host` yerelde vardı, sunucunun vars dosyasında yoktu. Hata doğru
(preflight yanlış platformu durdurur), ama GitHub'dan indirip Proxmox'a uygulayan biri neyi değiştireceğini bulamayabilir.

Bugün `hardening_platform` bir **paket değişkenidir** ve varsayılanı `generic`'tir; platformu söyleme işi kullanıcıda kalıyor.

## 2. Bugün pakette ne var (ölçülen)
| Bilgi | Nerede | Not |
|---|---|---|
| Platform değişkeni | `platform_var: hardening_platform` (`component.yml`) | sshpocket değişken listesini bununla süzer |
| Bilinen platformlar | `generic`, `proxmox-host`, `raspberry-pi` | **üç yerde ayrı yazılı**: `roles/hardening_preflight/defaults/main.yml` (`hardening_platforms_known`), `scripts/check-consistency.py` (`PLATFORMS`), `component.yml` yorumu |
| Platforma özgü değişken | `vars[].platforms` | 128 değişkenin 10'u `[proxmox-host]` (tümü grup `Proxmox`); 118'i her platformda. `raspberry-pi` etiketli değişken YOK |
| Platforma özgü eylem | `actions[].platforms` | `pve_firewall_preview`, `pve_firewall_apply` |
| Yanlış seçimde koruma | preflight | Proxmox + `generic` → DURUR; `proxmox-host`/`raspberry-pi` + o donanım değil → DURUR; `hardening_allow_unsupported` bunları atlatmaz. Pi + `generic` → yalnızca not düşer |
| Proxmox'ta gerçek değişiklik kapısı | `hardening_pve_apply` | `false` iken preflight gerçek koşuyu durdurur (`--check` serbest) |

## 3. İlkeler (kullanıcıyla vardığımız; bu notun temeli)
1. **Yanlış seçim güvenli kalır.** Preflight'ın iki yönlü doğrulaması (Proxmox'u `generic` yapma / Proxmox olmayanı `proxmox-host` yapma) aynen kalır. Menü yalnızca kolaylıktır, güvenlik tarafı değildir.
2. **Değişkenler üç gruba ayrılır** (§4).
3. **Platform bilgisi pakette olur**; sshpocket "Proxmox nedir" bilmez, paketin bildirdiğini gösterir ve seçileni yazar.
4. **`auto` yok.** `hardening_platform` her zaman somut bir değerdir (§6).

## 4. Üç değişken grubu
128 değişkeni tek tek sınıflamıyoruz; mevcut etiketlerden türeyen kural:

| Grup | Kural | Örnek | Davranış |
|---|---|---|---|
| **(a) Sunucu NE** | yalnızca `platform_var` | `hardening_platform` | Seçimden otomatik yazılır |
| **(b) Platform varsayılanı** | `platforms:` etiketli değişkenler (10 Proxmox) | `hardening_pve_pveproxy_allow_from` (boş), `hardening_pve_keep_banner` (true), `hardening_aide_pve_excludes` | **Yeni yazılacak bir şey yok**: değişken zaten kendi `default`'unu taşıyor; platform seçilince menüde görünür olur. Elle `-e` ile gevşetmek gerekmez |
| **(c) Erişimi/sunucuyu etkileyen** | `warn_if` taşıyanlar (45 değişken) ve `hardening_ssh_allow_from` | `hardening_ufw_prune_ssh`, `hardening_rpi_strict`, `hardening_pve_strict`, `hardening_pve_apply`, `hardening_fail2ban_pve_web`, `hardening_ssh_allow_from` | **Asla sessizce yazılmaz.** İstisnalar aşağıda |

(c) içinde üç ayrı davranış:
- **Sunucu eklerken SORULUR:** yalnızca `hardening_ssh_allow_from` (öneri sunulabilir, otomatik doldurulmaz; fail2ban `ignoreip` kararındaki ilkeyle aynı: kontrol makinesinin adresi sessizce eklenmez). Paket manifestte `onboarding_vars` ile bildirir.
- **Apply anında türer:** `hardening_pve_apply` (§5).
- **Asla otomatik:** `hardening_ufw_prune_ssh` (siler), `hardening_pve_strict`, `hardening_rpi_strict` (korumaları gevşeten/sıkılaştıran), diğer tüm `warn_if` değişkenleri. Kullanıcı değişken ekranından bilinçli açar.

## 5. `hardening_pve_apply` için apply onayı
**Gözlem:** `apply` eylemi zaten `confirm: type-server-name` ve `requires: [preview]` taşıyor; `pve_firewall_apply` aynı onayı kendi içinde taşıyor ve `hardening_pve_apply`'a BAĞLI DEĞİL. Yani Proxmox'ta gerçek koşu için kullanıcı hem sunucu adını yazıyor hem vars dosyasına `hardening_pve_apply=true` yazıyor: ikinci adım ikincil bir kapı, ayrı bir karar değil.

**Öneri:** `platform_choices[].apply_vars` (§7) yalnızca `apply` eyleminde, onay verildikten SONRA `-e hardening_pve_apply=true` olarak geçirilir; vars dosyasına hiç yazılmaz. Böylece `fizikiproxmox` türü "vars'ta eksik" hatası bu değişken için de oluşmaz, ama bir `preview` hiçbir zaman gerçek koşu olamaz.

**Riskler (paket davranışı değişir):**
1. **`-e` vars dosyasını ezer.** Kullanıcı dosyaya bilerek `hardening_pve_apply=false` yazmışsa `-e` onu aşardı. Kural: sshpocket `apply_vars`'ı **yalnızca değişken vars dosyasında YOKSA** geçirir. Açık soru 3.
2. **Uyarı metinleri Ubuntu'ya göre.** `apply` uyarıları ufw/PAM'den söz ediyor; Proxmox'ta hipervizörü, VM'leri, `pve-firewall`'u ilgilendiren uyarılar gerekir. `platform_choices`'ta platform başına `apply_warnings` olmalı ve onay ekranında gösterilmeli.
3. **Eski sshpocket kataloğu bilmez.** O zaman `hardening_pve_apply` hiç geçmez ve preflight Proxmox'ta gerçek koşuyu **durdurur**: güvenli yönde başarısız olur (hata mesajı zaten değişkeni söylüyor). Davranış kaybı yok, yalnızca eski elle yol.
4. **Değişken kalır.** `hardening_pve_apply` `component.yml`'den kalkmaz; elle `-e`/vars ile kullananlar (ve eski sürümler) aynı çalışır. Bu yüzden "türetme" yalnızca eksik olanı doldurur.
5. Onay gücü aynı kalır (`type-server-name`); gevşetme yok. Gerçek Proxmox'ta apply hâlâ `DENENMEDİ` notları taşıyor, bu değişiklik onları kaldırmaz.

## 6. Platformu kim algılar? ( `auto` neden yok )
sshpocket değişken listesini `hardening_platform` değerine göre süzüyor; değer `auto` kalırsa süzemez. Bu yüzden değer sunucu eklenirken **bir kez somut olarak** yazılır.

**Öneri: algılamayı (isteğe bağlı bir ÖNERİ olarak) paket raporlar; sunucu ekleme akışı ona bağlı değildir (§10-2).** Salt okunur yeni bir eylem (örnek ad `platform_detect`): preflight/erişim korumalarını ÇALIŞTIRMAZ (`rollback_*` gibi), `sudo` gerektirmez, tek bir sonuç satırı yazar:

```
SSHPOCKET_RESULT linux-hardening.platform_detect platform=proxmox-host hint=none os=debian-13
SSHPOCKET_RESULT linux-hardening.platform_detect platform=generic hint=raspberry-pi os=debian-13
```

- İşaretler (`/etc/pve`, `/usr/bin/pveversion`; Pi için `/etc/rpi-issue`, `/boot/firmware/config.txt`) preflight'taki mevcut listelerle **aynı** değişkenlerden okunur; ikinci bir kopya yazılmaz.
- **`raspberry-pi` hiçbir zaman `platform=` olmaz, yalnızca `hint=`.** Platform seçimi `usb-storage` engelini gevşetir; USB diskten açılan bir Pi'de yanlış otomatik seçim sessizce yanlış politika demektir. Menü "Pi gibi görünüyor, Raspberry Pi seçilsin mi?" diye sorar, kullanıcı onaylar.
- sshpocket önerilen değeri gösterir, kullanıcı değiştirebilir; seçilen vars dosyasına yazılır. Preflight yine doğrular (ilke 1).
- **Alternatif (reddedildi):** sshpocket'in ssh ile `/etc/pve`'ye bakması. Proxmox bilgisini sshpocket'e taşır (ilke 3'ü bozar) ve her yeni platformda onu da değiştirmek gerekir. Açık soru 2.

## 7. Manifest önerisi
sshpocket notuyla (docs/sunucu-ekleme-platform-secimi.md) uzlaşılan adlar. Hepsi **isteğe bağlı** üst düzey alanlar; `platform_var` zaten var.

```yaml
platform_var: hardening_platform          # mevcut
platform_choices:
  - id: generic
    label: "Ubuntu / Debian"
    description: "Genel sunucu. Varsayılan."
    defaults: {}
    auto_detect: true
  - id: proxmox-host
    label: "Proxmox VE hostu"
    description: "Hipervizör. ufw ve bazı kernel/dosya kuralları uygulanmaz; gerçek değişiklik apply onayıyla."
    defaults: {}
    auto_detect: true
    apply_vars: { hardening_pve_apply: true }
    apply_warnings:
      - "Proxmox VE hostunu değiştirir; önce snapshot alın, VM'ler etkilenebilir."
  - id: raspberry-pi
    label: "Raspberry Pi"
    description: "usb-storage engeli gevşetilir (USB'den açılan Pi için)."
    defaults: {}
    auto_detect: false                    # yalnızca ipucu; kullanıcı onaylar
onboarding_vars: [hardening_ssh_allow_from]   # sunucu eklerken SORULUR (platformdan bağımsız, tek liste)
```

- `id` aynı zamanda `hardening_platform` değeridir; sshpocket onu `platform_var`'a yazar. `defaults` **ek** değişkenler içindir (bugün hepsi boş: (b) grubu zaten `default` taşıyor).
- `onboarding_vars` yalnızca sorulabilir değişkenleri içerir. `hardening_pve_apply`, `hardening_ufw_prune_ssh` ve diğer `warn_if` değişkenleri (allow_from hariç) **burada ve `defaults`'ta bulunamaz**: tutarlılık denetimi paketi, sshpocket da menüyü reddeder (iki yönlü).
- `apply_vars`/`apply_warnings` (§5) `defaults`'tan AYRI tutulur: sunucu eklerken değil yalnızca `apply` onayından sonra geçer. sshpocket notunda bu alan yoksa eklenmesi gerekir (açık soru 7).
- **Tek kaynak:** `hardening_platforms_known`, `check-consistency.py` içindeki `PLATFORMS` ve katalog (`platform_choices`) bugünkü üç ayrı listenin yerini alır; tutarlılık denetimi eşitliği kanıtlar. Yeni platform: katalog girişi + rol/preflight + (varsa) `platforms:` etiketli değişkenler. Menü kendiliğinden büyür.
- `component.json`'a `make-component-json.py` ile aynen taşınır. `sshpocket_api: 1` kalır.
- sshpocket tarafı `auto`/bilinmeyen `platform_var` değerini "belirsiz" sayıp süzmez; paket yine de somut değer yazılmasını bekler (ilke 4).

**Algılama eylemi** (§6) çıktı anahtarları sshpocket notuyla aynı: `platform=` (algılanan; emin değilse boş) ve `hint=` (yalnızca ipucu).

## 8. Eski paket ve vars dosyalarıyla uyum
- `hardening_platform` yoksa davranış değişmez: `generic`. Proxmox'ta bu preflight'ta durur; hata iletisine "vars dosyasına `hardening_platform=proxmox-host` ekleyin" ipucu eklenir (küçük, ayrı PR; bugün ileti yalnızca `--check -e …` önerisini veriyor).
- Katalog yok ya da sshpocket tanımıyorsa her şey bugünkü gibi çalışır.
- Eski sunucu klasörlerinin vars dosyaları geçerli kalır; yeni alan hiçbir değişkenin anlamını değiştirmez. `hardening_pve_apply` vars'ta zaten `true` ise `apply_vars` hiçbir şey eklemez.
- README/HOWTO'ya Proxmox için tek satırlık "platformu söyle" notu (GitHub'dan indirenler için).

## 9. Test planı (uygulama PR'larında; şimdi yazılmadı)
1. **Katalog tutarlılığı:** `platform_choices` kimlikleri = `hardening_platforms_known` = `PLATFORMS`; `onboarding_vars`, `defaults` ve `apply_vars` adları `vars`'ta var; `onboarding_vars`/`defaults` içinde `hardening_ssh_allow_from` dışında `warn_if` değişken yok; `apply_vars` yalnızca `warn_if` bool. Mutasyon: birine fazladan kimlik ekle → test kırılır.
2. **`platform_detect`** (+ manifestte `effects: []`, `requires_sudo: false`, `requires`/`confirm` yok, `required` değişken yok) (gerçek Ansible, sahte işaret dosyalarıyla, `test_rpi_platform.py` desenindeki gibi): Proxmox → `platform=proxmox-host`; Pi işaretli → `platform=generic hint=raspberry-pi` (asla `platform=raspberry-pi`); ikisi de yok → `generic`; tek satır, `SSHPOCKET_RESULT` öneki; `sudo` gerektirmez; `--check`'te de çalışır; preflight'ı çalıştırmaz.
3. **Geriye uyum:** katalogsuz `component.json` ile tutarlılık denetimi geçer; `hardening_pve_apply=false` açık yazılmış vars `apply_vars` ile ezilmez (bu kural sshpocket testidir, pakette yalnızca belge).
4. **Preflight ipucu:** Proxmox + `generic` iletisi vars dosyası ipucunu içerir (golden).
5. **Gerçek VM:** Proxmox'ta `platform_detect` → `apply` (onay + `apply_vars`) bir kez; bugün hiçbir şey bu yolla denenmedi. `verification-log.md`'ye yazılır.

## 10. Kararlar ve açık sorular
**Kullanıcı cevapları (koordinatör aracılığıyla, 2026-11-02):**
1. Bilinmeyen üst düzey alan: sshpocket doğrulayıcısı **yok sayar** (yalnızca bilinmeyen `required_features` ve daha yeni `sshpocket_api` reddedilir). Alan isteğe bağlı eklenir, `sshpocket_api: 1` kalır, eski sshpocket bozulmaz (yeni özelliği göstermez).
2. **Platformu kullanıcıya doğrudan sor.** Algılama zorunlu değil: `platform_detect` varsa yalnızca ÖNERİ, yoksa düz soru. Ajan/sudo/host key gerektiren algılama sunucu ekleme akışının ön koşulu OLMAZ; kapılar eksikse tahmin atlanır (sshpocket cevabı: eylem "çalıştırılmadı" döner).
3. "Yalnızca vars dosyasında yoksa geçir" kuralını kimin uygulayacağı: **AÇIK**, sshpocket oturumuna soruldu. İlke karar: kullanıcının yazdığı değer ezilmez. Öneri: sshpocket uygular (vars dosyasını o okuyor); paket tarafı ara değişken (`hardening_pve_apply_auto`) yalnızca sshpocket yapamazsa.
4. **`hardening_ssh_allow_from` zorunlu; boşsa eylemler ÇALIŞMASIN.** Bugünkü durum: manifestte `required` DEĞİL (bilerek: ufw VE ssh alanı ikisi de kapalıyken liste gerekmez, `component.yml` yorumu). Zorlama paketin kendisinde var: `roles/hardening_preflight/tasks/access.yml` boş/tanımsız listede `harden.yml`'i hiçbir şey yazmadan durdurur (`preview` dahil, çünkü preflight `--check`'te de çalışır). `audit` ve `rollback_*`/`kaldir_*` bu kapıdan geçmez (salt okunur / kontrol kaybından sonra da çalışmalı). Öneri: sshpocket sunucu eklerken değeri zorunlu SORAR (`onboarding_vars`), boşsa sunucuyu kaydetmez ya da `apply`/`preview` eylemlerini devre dışı bırakır; `required: true` manifest işaretine **geçilmez**, çünkü `required` alan gizlendiğinde de zorunlu kalır ve `audit`'i de kilitlerdi (`audit` için liste gereksiz). Paket davranışı değişmez.
5. **Çok düğümlü Proxmox: desteklenmiyor / doğrulanmadı.** Kullanıcıda küme yok, test edilemez. `pve_firewall_*` küme reddi zaten var; `harden.yml` için küme doğrulaması yazılmaz, uygulama vaadi verilmez. `platform_choices` açıklamasına "tek düğüm" yazılır.
6. **Raspberry Pi:** `hardening_rpi_strict` sunucu eklerken ASLA sorulmaz, varsayılan kapalı kalır (`onboarding_vars`/`defaults`'ta bulunamaz). `apply_warnings` Pi için kısa ve açık: "USB'den açılan ya da USB depolama kullanan Pi'de usb-storage engeli sistem diskine erişimi keser; `raspberry-pi` platformunda bu engel gevşetilir." Pi donanımında DENENMEDİ (arm64 Debian konteynerinde denendi, `verification-log.md` madde 44); bu `description`'a da yazılır.

**Hâlâ açık:**
- **`apply_vars`/`apply_warnings`: KULLANICI ONAYLADI (2026-11-02, koordinatör aracılığıyla); sshpocket koşullu kabul etti. Uygulama bu PR'da YOK, ayrı iş olarak kalır.** Kural: Proxmox'ta `apply`, sunucu adı onayından sonra `hardening_pve_apply`'ı kendisi geçirir; "dosyada varsa ezme" ilkesi geçerli (kuralı sshpocket uygular). Koşullar (sshpocket notu §5):
  a) `apply_vars` doluysa `apply_warnings` zorunlu; metin `type-server-name` sorusundan ÖNCE gösterilir.
  b) Vars dosyasına yazılmaz, yalnızca o koşuya `-e` ile geçer; dosyada varsa ezilmez; günlük başlığında "bu koşuya özel: hardening_pve_apply=true" satırı.
  c) Yalnızca değişiklik yapan eylemlerde (preview/audit değil) ve platform açıkça seçilmişse (`platform_var` dosyada yazılı; auto/belirsiz değil).
  d) Yalnızca tanımlı bool/enum değişkenler; `hardening_ufw_prune_ssh` gibi silici bulunamaz.
  Paket tarafı karşılığı: tutarlılık denetimi `apply_vars` doluysa `apply_warnings`'in boş olmamasını ve yalnızca `warn_if` bool değişkenleri içermesini zorunlu kılar; `hardening_ufw_prune_ssh` reddedilir. Elle yazılmış `hardening_pve_apply` yine geçerlidir; hiçbir şey kaybolmaz.
- **Eylem düzeyi `requires_vars` (sshpocket önerisi, paket tarafı kabul etti, kullanıcı henüz görmedi):** `actions.<ad>.requires_vars: [hardening_ssh_allow_from]`, isteğe bağlı yeni alan. sshpocket, değişken vars dosyasında boş/yoksa o eylemi ssh'a gitmeden reddeder; `sshpocket_api` artmaz, eski sshpocket alanı yok sayar (preflight `access.yml` yine durdurur: kemer + pantolon). Paketteki yeri: `preview`, `apply`, `pve_firewall_preview`, `pve_firewall_apply` (hepsi allow_from'a göre kural yazar/gösterir). `audit`, `rollback_*`, `kaldir_*` etkilenmez. `required: true` kullanılmaz: gizli değişkeni de zorunlu tutar ve sshpocket'in kapısı (effects'i boş olmayan her eylem + başka eylemin `requires` ön koşulu) 0.11.0 manifestinde 10 eylemi kapatır (`audit`, `preview`, `apply`, `pve_firewall_*`, `rollback_disarm`, `rollback_now`, `kaldir_onizle`, `kaldir`, `kaldir_geri_yukle`); yalnız `rollback_status` çalışır. `requires_vars` yalnız seçilen 4 eylemi kapatır. Sınır: ufw VE ssh alanı ikisi de kapalıyken `preview`/`apply` allow_from istemez, ama `requires_vars` yine de ister; bu bilinçli sıkılık (sunucu eklerken zaten zorunlu sorulur). `check-consistency.py` `requires_vars` adlarının `vars`'ta tanımlı olmasını denetler. Paket davranış değişikliği yeni sürüm gerektirir.
- **`hardening_ssh_allow_from` önerisi:** sshpocket nereden üretir (kontrol makinesinin yerel ağları)? Öneri hiçbir zaman sessizce yazılmaz.
- **Küçük ayrı PR (kullanıcıya sorulacak, yazılmadı):** preflight "generic + Proxmox" hata iletisine "vars dosyasına `hardening_platform=proxmox-host` ekleyin" ipucu.
