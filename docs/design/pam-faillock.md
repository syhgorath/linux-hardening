# Tasarım notu: `pam_faillock` ve `pam_pwhistory` (kod YOK)

**Durum:** yalnızca tasarım. Kilitlenme riski olduğu için kod yazılmadan önce aşağıdaki açık sorular cevaplanmalı. İlgili CIS maddeleri `docs/cis-esleme.md`'nin "PAM" (5.3) satırlarında: `pam_faillock` (kilitleme eşiği, açılma süresi),
`pam_pwhistory` (parola geçmişi) ve `pam_unix` (`nullok`, `remember`, güçlü hash).

## Test VM'inde görülen (Ubuntu 26.04, `libpam-modules 1.7.0`, 2026-10-18, salt okunur)
- `/usr/share/pam-configs/` içinde yalnızca `capability`, `mkhomedir`, `pwquality`, `systemd`, `unix` var: **faillock ve pwhistory için hazır profil yok**.
- `/etc/pam.d/common-auth`: `pam_unix.so nullok`, `pam_faillock` yok. `common-password`: `pam_pwquality.so retry=3` ve `pam_unix.so ... yescrypt` var, `pam_pwhistory` yok.
- `/etc/security/faillock.conf` var ama etkin satır yok; `/etc/security/pwhistory.conf` var.
- Sonuç: bu modülleri açmak `pam-auth-update` ile **bizim yazacağımız bir profil** (`/usr/share/pam-configs/hardening-faillock`) ya da `/etc/pam.d/common-*` dosyalarını doğrudan düzenlemek demektir.

## Taban çizgisi ölçümü (faillock YOKKEN, gerçek VM, Ubuntu 26.04, sudo-rs 0.2.13, 2026-10-20)
Parola isteyen `sudo` kuralı olan ayrı bir test hesabıyla ölçüldü (verification-log madde 34):
- Doğru parola çalışır; **yanlış parola sınırsızca denenebilir, hiçbir kilit yok** (7 art arda yanlış deneme sonrası doğru parola yine geçti).
- Yanlış parolalı her `sudo -S` çağrısı günlükte **1** `pam_unix(sudo:auth): authentication failure` bırakır; bir çağrıda en çok 3 yanlış satır denenir (`maximum 3 incorrect authentication attempts`).
- `sudo -n` (parolasız deneme) hata **SAYILMAZ** (`interactive authentication is required`, günlükte kayıt yok).
- Ansible: yanlış `become` parolası koşu başına **1** başarısız deneme sayar (ilk görevde durur), görev sayısına bağlı değildir. Bu, `deny=5` ile 5 başarısız koşunun hesabı kilitleyeceği anlamına gelir.
- **Engel:** sudo-rs ile Ansible'ın parolalı `become`'ı hiç çalışmıyor (istem sarmalanıyor); `ansible_become_exe=/usr/bin/sudo.ws` ile çalışıyor. Bu `faillock` öncesinde çözülmesi gereken bir önkoşul: aksi hâlde parolalı sudo'yla `faillock` denenemez.
- `/run/faillock` yok (tmpfs; `faillock` açılınca oluşur, yeniden başlatmada temizlenir).

## `pam_pwhistory` YAPILDI (varsayılan kapalı), ölçülen davranış (gerçek VM, 2026-10-20)
Rol: `hardening_auth` (`hardening_pam_pwhistory_remember`, `hardening_pam_pwhistory_enforce_for_root`). Yalnızca `common-password`'a girer; `auth` yığınına dokunmadığı için kilitlenme riski yoktur. Ölçümler (verification-log 35):
- `remember=N`: mevcut parola ve önceki **N-1** parola engellenir (opasswd'de N eski hash tutulur ama denetim mevcut + N-1'i kapsar).
- Normal kullanıcının `passwd`'si: önceki parola reddedilir (`already used`, `password unchanged`); daha eski olan kabul edilir.
- Root'un `chpasswd`'si: `enforce_for_root` KAPALIYKEN yalnızca mesaj, parola değişir; AÇIKKEN `password not changed`. Yani otomasyon (kök olarak çalışan) ancak `enforce_for_root=true` ile kırılır.
- `PASS_MIN_DAYS=1` (bu paketin ayarı) normal kullanıcının parolayı 1 günden önce değiştirmesini engeller; test hesabında `chage -m 0` gerekti.

## Neden riskli
- **Kilitlenme:** `deny=5` aşılınca hesap kilitlenir; SSH **anahtar** girişi `pam auth` yığınına girmez (kilitlemeden etkilenmez), ama `sudo` parola denemeleri ve konsol/`su` girişi etkilenir. Otomasyon kullanıcısı parola gerektiren bir akışta kilitlenirse `harden` ya da kurtarma durur.
- **Yanlış PAM yığını erişimi tamamen keser** (SSH `UsePAM yes` iken `account`/`session` aşamaları da PAM'den geçer). Geri alma güvenlik ağı artık PAM dosyalarını da kapsar (arm ile disarm ARASINDA yapılan değişiklikler için; docs/design/rollback-timer.md §4.6, verification-log 36). `faillock` rolü bu pencerenin İÇİNDE çalışmalıdır.
- **fail2ban ile örtüşme:** fail2ban IP bazlı yasaklar (ağ), faillock hesap bazlıdır (yerel). Biri ötekinin yerine geçmez (CIS yalnızca faillock'u sayar).
- **Kök hesabı:** `even_deny_root` kök için de kilit demektir; kök yalnızca konsoldan kurtarılabilir.

## Seçenekler
| | Ne | Not |
|---|---|---|
| A | Hiçbir şey yapma, `docs/cis-esleme.md`'de ❌ bırak | Bugünkü durum |
| B | Yalnızca `faillock.conf` değerlerini yaz (`deny`, `unlock_time`, `fail_interval`) | Modül PAM'de etkin değilse **hiçbir etkisi yok**; yanıltıcı olabilir |
| C (öneri, sınanacak) | `pam-auth-update` profili: `auth` yığınına `pam_faillock preauth` / `authfail` / `authsucc`, `account`'a `pam_faillock`; **varsayılan KAPALI** değişken (`hardening_pam_faillock`) | Kilitlenme riski açıkça uyarılır; `deny`≤5, `unlock_time` 900+ (CIS) |
| D | `common-*` dosyalarını doğrudan düzenle | Dağıtım güncellemesi/`pam-auth-update` ezer; önerilmez |

`pam_pwhistory` (`remember=24`) için aynı yol: profil + `pwhistory.conf`. `pam_unix` `nullok` kaldırma boş parolalı hesabı kilitler; önce `awk -F: '$2==""' /etc/shadow` ile tarama gerekir.

## Önerilen değişkenler (henüz yok)
| Değişken | Varsayılan | Anlam |
|---|---|---|
| `hardening_pam_faillock` | `false` | `true`: faillock profilini kur ve etkinleştir |
| `hardening_pam_faillock_deny` | `5` | Kilit eşiği (CIS: ≤5) |
| `hardening_pam_faillock_unlock_time` | `900` | Saniye (CIS: 0 ya da ≥900) |
| `hardening_pam_pwhistory_remember` | `0` | `>0`: parola geçmişi (CIS: 24); `0` = kapalı |

Eklenirse `component.yml` `vars`'ına tür/varsayılan/açıklama zorunlu (`check-consistency.py` denetler); varsayılanlar KAPALI olmalı (`warn_if: true`).

## Test planı
1. **Birim/statik:** profil dosyasının içeriği (golden), `pam-auth-update --enable`'in idempotent olması, varsayılan KAPALI.
2. **Docker LAB:** kullanıcı ekle, yanlış parolayla 6 deneme, kilidi `faillock --user x` ile gör ve `--reset`; **anahtarla SSH girişinin kilitlenmediğini** doğrula (LAB'da `su`/`sudo` parola akışı ayrıca).
3. **Gerçek VM (snapshot şart):** `harden` sonrası **ikinci bir oturum açık tutarak** uygula; yeni bağlantı + `sudo -k; sudo -v` dene; kök konsol erişimi olduğundan emin ol.
4. **Mutasyon:** `deny` değeri, `even_deny_root`, `unlock_time` değişince test düşmeli.

## Açık sorular (cevaplanmadan kod yazılmaz)
1. Otomasyon kullanıcısı (`ansible_user`) parola ile `sudo` kullanıyor mu? Evetse kilit eşiği ve istisna (`audit`/`silent`) nasıl olmalı?
2. `even_deny_root` varsayılan olmalı mı (CIS istiyor, konsol erişimi olmayan bulut sunucusunda tehlikeli)?
3. `pam-auth-update` profili `Priority`/`Auth-Type` değerleri Ubuntu 26.04'te `unix` profiliyle doğru sıralanıyor mu? (VM'de `--enable` sonrası `common-auth` çıktısı incelenmeli.)
4. Geri alma: **CEVAPLANDI**, PAM `hardening_rollback` kapsamına alındı (zamanlı geri alma; gerçek VM'de bilerek bozuk `common-auth` ile denendi).
5. Raspberry Pi / LXC / bulut imajları için PAM yığını farklı olabilir mi?

## Kapsam dışı
Parola karması (`ENCRYPT_METHOD`), `pam_unix` `remember`, kök parolası, MFA/PAM modülleri (`pam_google_authenticator` vb.).
