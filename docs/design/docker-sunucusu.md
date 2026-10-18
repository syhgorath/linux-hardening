# Tasarım notu: Docker çalıştıran sunucu (kod YOK)

**Durum:** ilk dilim KODLANDI (rapor, `daemon.json` birleştirme, dosya izinleri, auditd kuralları; hepsi güvenli varsayılanlarla, Docker rolü varsayılan kapalı). Aşağıdaki açık sorular varsayılanları belirler; kullanıcı kendi ayarını değişkenlerle verir. Gerçek Docker'la doğrulama bekliyor (kurulum indirme gerektirir). Kaynak: **CIS Docker Benchmark v1.9.0** (09-30-2026, 117 madde). CIS metni bu depoya alınmaz; yalnızca madde
numaraları ve kendi sözlerimizle kısa açıklamalar var (PDF'i [CIS'ten](https://www.cisecurity.org/cis-benchmarks) indirin). Senaryo: `examples/` içindeki "server2" (Docker + ters vekil, home lab).

## Kapsam kararı
| CIS bölümü | Madde (L1 / L2) | Bu proje | Neden |
|---|---|---|---|
| 1 Ana bilgisayar | 8 / 12 | **Kısmen** (denetim kuralları, rapor) | Ana bilgisayar sertleştirmesi bu projenin işi; ayrı bölüm gibi maddeler sunucu düzenine bağlı |
| 2 Docker daemon | 13 / 6 | **Seçili ayarlar**, `daemon.json` birleştirerek | Aşağıda ayrıntı |
| 3 Yapılandırma dosyaları | 18 / 6 | **Evet** (dosya izinleri) | `hardening_files` ile aynı yöntem, düşük risk |
| 4 İmajlar | 9 / 2 | Hayır | İmajı **siz** üretirsiniz (Dockerfile) |
| 5 Konteyner çalıştırma | 28 / 4 | Hayır | `docker run` / compose bayrakları sizin; yalnızca **kontrol listesi** belgesi |
| 6 İşletim | 2 / 0 | Hayır | Süreç maddeleri |
| 7 Swarm | 9 / 0 | Hayır | Swarm kullanılmıyor |

Sayılar PDF'ten betikle çıkarıldı. Bölüm 5'in en önemlileri (kullanıcı tarafı, kontrol listesi olarak belgelenir): `--privileged` kullanma, `docker.sock`'u konteynere bağlama, salt okunur kök dosya sistemi,
bellek/CPU sınırı, `no-new-privileges`, kök olmayan kullanıcı, gizli bilgileri imaja gömme.

## Bölüm 3: dosya sahibi ve izinleri (öneri: `hardening_files` genişlemesi, varsayılan AÇIK, risk düşük)
Yalnızca **var olan** dosyalara, **yalnızca fazla izni kaldırarak** (mevcut mantık). Maddeler: `docker.service` ve `docker.socket` sahibi/izni (3.1-3.4), `/etc/docker` (3.5-3.6),
`daemon.json` (3.17-3.18, L2), `/etc/default/docker` (3.19-3.20), `docker.sock` `root:docker` ve en çok `660` (3.15-3.16), containerd soketi (3.23-3.24). Sertifika/TLS dosyaları (3.7-3.14) yalnızca TLS
kullanılıyorsa vardır; yolları sabit olmadığı için **kapsam dışı** (rapor yeterli). Dikkat: `docker.sock` izni Docker'ın kendisi yeniden başlatılınca sıfırlanabilir; bir sonraki koşuda yeniden sıkılaşır.

## Bölüm 1: denetim (auditd) kuralları (öneri: `hardening_auditd` içinde, Docker kuruluysa)
Eklenecek izleme kuralları: `dockerd` ikilisi, `/etc/docker`, `docker.service`/`docker.socket`, `docker.sock`, `containerd.sock`, `/etc/docker/daemon.json`, `/etc/default/docker` (1.1.3, 1.1.6-1.1.11).
**Önerilmeyen:** `/var/lib/docker` izlemesi (1.1.5, CIS "manuel"): konteyner çalışırken çok gürültülü ve disk doldurur. Kural yüklenirken `auditd` yoksa (konteyner/LXC) atlanır. Mevcut `test_auditd_rules_order.py` deseni kullanılır.
Madde 1.1.2 (docker grubunun üyeleri kök eşdeğeridir): **salt okunur rapor**: hangi kullanıcılar `docker` grubunda, uyarı olarak yazılır, hiçbir şey değiştirilmez.

## Bölüm 2: daemon ayarları (öneri: `daemon.json` BİRLEŞTİRME, varsayılan KAPALI)
| Ayar | CIS | Etki / risk | Öneri |
|---|---|---|---|
| `live-restore: true` | 2.16 | Etki yok; daemon yeniden başlayınca konteynerler çalışmaya devam eder | **Önerilir**; `SIGHUP` (`systemctl reload docker`) ile konteynerler **durmadan** açılır (mini labda gerçek Docker'la doğrulandı); `daemon.json`'da olup yüklenmemişken yeniden başlatma konteynerleri DURDURUR |
| `no-new-privileges: true` | 2.15 | Konteyner içinde `setuid` ikili kullanan süreçler (örn. konteyner içinde `sudo`) bozulur | Seçenek, varsayılan kapalı |
| `userland-proxy: false` | 2.17 | Yeni çekirdeklerde sorun yok; bazı ağ düzenlerinde ("hairpin NAT") fark eder | Seçenek, varsayılan kapalı, **test gerekir** |
| `icc: false` | 2.2 | Varsayılan köprüdeki konteynerler birbirine ulaşamaz; compose projeleri kendi ağını kullandığından çoğunlukla sorun olmaz, eski `--link` bozulur | Seçenek, varsayılan kapalı |
| `log-driver: json-file` + `log-opts: max-size, max-file` | 2.14 benzeri | Günlük sınırı yok → home lab'da disk dolar (CIS bunu doğrudan istemez, ama gerçek risk) | **Önerilir** (örn. `10m` x `3`) |
| `experimental: false`, `log-level: info` | 2.3, 2.19 | Zaten varsayılan | Yalnızca **rapor** |
| `iptables: true` | 2.4 | `false` Docker ağını bozar | **Dokunma**, `false` bulunursa uyar |
| TCP API (`tcp://...:2375`) | 2.8 | TLS'siz uzak API kök eşdeğeridir | Salt okunur rapor: dinleyen `2375`/`2376` var mı |
| `userns-remap` | 2.10 (L2) | Birimler/izinler karışır, çok etkili | **Kapsam dışı** |
| Kök olmayan daemon (rootless) | 2.1 | Kurulum modeli tamamen değişir | **Kapsam dışı** |

**Mekanizma:** `daemon.json` zaten başka ayarlar içerebilir; üzerine yazmak kullanıcının ayarlarını siler. Bu yüzden mevcut `files/stale_ssh_rules.py` desenindeki gibi küçük, birim testli bir Python betiği
(`docker_daemon_merge.py`): mevcut JSON'u okur, istenen anahtarları **ekler/günceller**, diğerlerini korur; geçersiz JSON'da hiçbir şey yazmaz, değişirse önce `daemon.json.hardening.bak` yedeğini alır.
Docker'ı yeniden başlatmak konteynerleri etkileyebilir: yeniden başlatma ayrı bir değişkenle (`hardening_docker_restart`, varsayılan **false**) ve `live-restore` açıksa daha güvenli; kapalıysa rol "yeniden başlatma gerekli" uyarısı yazar.

## ufw ve Docker (senaryodaki asıl risk)
Docker, yayınladığı portu `DOCKER-USER`/`DOCKER-FORWARD` zincirinde ufw'den **önce** açar; ufw'de izin olmasa bile yayınlanan port dışarıdan erişilebilir (`docs/known-issues.md`).
| Yol | Not |
|---|---|
| **Yayınlamayı küçük tut** (önerilen) | Yalnızca ters vekil `80/443` yayınlar; diğer konteynerler iç ağda. Compose'ta yayınlanan portu belirli bir adrese bağla (`127.0.0.1:8080:80`) |
| Salt okunur rapor | `docker ps` ile `0.0.0.0`'a yayınlanan portları listele, izinli listede (`hardening_docker_allowed_published`, örn. `80`, `443`) olmayanları uyar |
| `DOCKER-USER` kuralları (ufw-docker benzeri) | Etkili ama karmaşık ve yanlış kural ağı keser; bu projede **önerilmiyor**, belge olarak anlatılır |
| `"iptables": false` | CIS 2.4 yasaklar; Docker ağını (NAT) bozar. **Yapma** |

## Diğer rollerle etkileşim
- `hardening_ufw_routed_deny: false` (yönlendirme ufw'ye takılmasın); `ip_forward`'a **dokunmuyoruz**, Docker kendisi açar.
- SSH `DisableForwarding yes` (varsayılan) konteyner için sorun değil; `DOCKER_HOST=ssh://` stdio kullanır. Unix soket yönlendirmesi (`ssh -L sock:sock`) bozulur.
- `route_localnet=0` bazı `localhost` DNAT düzenlerini bozar (zaten belgeli).
- AppArmor: Docker'ın varsayılan profili kalır; kapatılırsa bu rolün kapsamı dışı.

## Önerilen değişkenler (henüz yok)
| Değişken | Varsayılan | Anlam |
|---|---|---|
| `hardening_docker_enabled` | `false` | Docker rolünü çalıştır (kurulu değilse zaten atlanır) |
| `hardening_docker_daemon_settings` | `{live-restore: true, log-driver: json-file, log-opts: {max-size: 10m, max-file: "3"}}` | `daemon.json`'a **eklenecek** anahtarlar; kullanıcı genişletebilir (`no-new-privileges`, `userland-proxy`, `icc`) |
| `hardening_docker_restart` | `false` | Değişiklikten sonra Docker'ı yeniden başlat |
| `hardening_docker_allowed_published` | `[80, 443]` | Raporda "beklenen" sayılan yayınlanmış portlar |

Eklenirse `component.yml` `vars`'ına tür/varsayılan/açıklama zorunlu (`check-consistency.py` denetler); davranışı değiştirenler README "Dikkat" tablosuna girer.

## Test planı
1. **Birim:** `docker_daemon_merge.py` (mevcut anahtarları koruma, geçersiz JSON, idempotens, ekleme/güncelleme, boş dosya); dosya izinleri için `test_files_role.py` deseni; auditd şablonu golden.
2. **Mini lab (Colima):** `hl-server2` konteynerine Docker kurmak **indirme gerektirir** (`docker.io` paketi; iç içe Docker için `vfs` sürücüsü, bkz. LAB notları): yayınlanan portun ufw'yi atladığını ve raporun bunu yakaladığını, `live-restore`ın daemon yeniden başlatmada
   konteyneri koruduğunu doğrulamak için gerekli. Kurulum öncesi boyut ve kaynak sorulur.
3. **Gerçek VM (snapshot şart):** `daemon.json` birleştirme ve yeniden başlatma etkisi.
4. **Mutasyon:** her ayar için eski davranışa dönünce test düşmeli.

## Açık sorular (cevaplanmadan kod yazılmaz)
1. Docker'ı hangi yöntemle kuruyorsunuz (`docker.io` Ubuntu paketi mi, Docker'ın kendi deposu mu)? Dosya yolları ve `docker.socket` ayrıntıları farklıdır.
2. Ters vekil hangisi (Traefik, nginx, Caddy) ve `docker.sock`'a bağlanıyor mu (Traefik sık yapar; CIS bunu riskli sayar)?
3. `daemon.json` zaten var mı, içinde neler var (`registry-mirrors`, `data-root`...)?
4. Docker'ı yeniden başlatmak kabul edilebilir mi, hangi konteynerler kesintiye dayanamaz?
5. `icc: false` ve `userland-proxy: false` için compose projelerinizde eski `links:`/hairpin kullanımı var mı?
6. Yayınlanan portların izinli listesi (`80`, `443`) başka neleri içermeli?

## Kapsam dışı
İmaj üretimi ve tarama, konteyner çalıştırma bayrakları (CIS 4-5), Swarm, rootless Docker, `userns-remap`, TLS sertifika yönetimi, kayıt defteri (registry) kurulumu.
