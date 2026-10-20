# Tasarım notu: Grup 3 (`/tmp` ve `/dev/shm` noexec, `su` kısıtı, root ortamı) (kod YOK)

**Durum:** yalnızca tasarım. Üçü de varsayılan davranışı değiştirir; önce aşağıdaki açık sorular cevaplanmalı, sonra her biri ayrı bir "lego" değişkeni (varsayılan KAPALI, `warn_if: true`) ve ayrı PR olur.
Kapsanan CIS Ubuntu 26.04 Level 1 Server maddeleri (hepsi `docs/cis-esleme.md`'de ❌): **1.1.2.1.4** (`/tmp` `noexec`), **1.1.2.2.4** (`/dev/shm` `noexec`),
**5.2.7** (`su` erişimi kısıtlı), **5.4.2.5** (root `PATH` bütünlüğü), **5.4.2.6** (root `umask`).

## Test VM'inde görülen (Ubuntu 26.04, 2026-10-19, salt okunur)
- `/tmp`: `tmpfs`, seçenekler `rw,nosuid,nodev,...` (**`noexec` yok**); `tmp.mount` birimi `static`. `/dev/shm`: `tmpfs`, `rw,nosuid,nodev,...` (**`noexec` yok**).
- `/var/tmp` ayrı bir bağlama değil (kök dosya sisteminde); CIS bunu istemez, dokunulmaz.
- `/etc/pam.d/su`: yalnızca `pam_rootok` ve `common-*`; `pam_wheel` **yok**, yani parolasını bilen her kullanıcı `su` yapabilir.
- Kullanıcı dosyaları (örnek hesap): `.bashrc` `0644`, `.profile` `0644`, `.ssh` `0700`, `.bash_history` `0600` (grup/diğer yazma yok).

## 1) `/tmp` ve `/dev/shm` için `noexec`
**Durum:** salt okunur RAPOR (`hardening_tmp_report`) ve UYGULAMA yapıldı: `hardening_tmp_noexec` / `hardening_shm_noexec` (varsayılan AÇIK, kullanıcı kararı; gerçek VM'de PHP/nginx/composer ile ve reboot sonrası denendi: verification-log 33). Açık sorular 1 ve 2 çoğunlukla çözüldü (PHP sorunu tekrarlanamadı), 5 hâlâ açık (LXC/RPi: `/tmp` ayrı bağlama değilse uygulanmaz ve uyarılır).

Etki: bu dizinlerden doğrudan çalıştırma kapanır (indirilen ikili, kabuk betiği `./x`, `ld.so` ile de yüklenen kütüphane). Saldırganın `/tmp`'ye bırakıp çalıştırdığı klasik yolu keser, ama **tam koruma değildir** (`sh /tmp/x.sh` yorumlayıcı üzerinden çalışmaya devam eder).

| Risk | Açıklama |
|---|---|
| Paket betikleri | Bazı `postinst`/`preinst` betikleri ve derleme araçları (`pip`, `npm`, `cargo` yapıları, Java JIT/JNA, `snap` yardımcıları) `/tmp`'den çalıştırır; kurulum sessizce başarısız olabilir |
| Ansible | Varsayılan `remote_tmp` `~/.ansible/tmp` (etkilenmez); ama `ansible.cfg`/`ANSIBLE_REMOTE_TMP` ile `/tmp` seçilmişse **bu depo dahil modüller çalışmaz** |
| Docker | Konteyner içi `/tmp` ayrı; ama `docker build` ve bazı ana makine yardımcıları ana makine `/tmp`'sini kullanabilir |
| Anında uygulama | `mount -o remount,noexec /tmp` çalışan süreçleri bozabilir; kalıcı yol `tmp.mount` drop-in'i (`/etc/systemd/system/tmp.mount.d/`) ve yeniden başlatma/`daemon-reload` + `remount` |
| `/dev/shm` | Systemd'nin kendi bağlaması; kalıcı yolun Ubuntu 26.04'te `/etc/fstab` satırı mı yoksa drop-in mi olduğu **VM'de denenmeden yazılmaz** |

Öneri: `hardening_tmp_noexec` (varsayılan `false`) ve ayrı `hardening_shm_noexec` (`false`); salt okunur **rapor** önce: "şu an noexec mi, `ansible_remote_tmp` `/tmp` mi, `dpkg`/`apt` hook'ları `/tmp` kullanıyor mu". Değişiklik **yeniden başlatma gerektirmeden** `remount` ile uygulanmaz; yalnızca kalıcı drop-in yazılır ve "yeniden başlatınca/`remount` ile etkinleşir" uyarısı verilir.

## 2) `su` kısıtı (5.2.7)
CIS: `/etc/pam.d/su` içine `auth required pam_wheel.so use_uid group=<boş grup>`; grup boş olduğu için `root` dışında kimse `su` yapamaz (kök zaten `pam_rootok` ile geçer). `sudo` etkilenmez.
- Risk düşük: SSH, `sudo`, `login` bu dosyayı kullanmaz. Bozulanlar: parola ile `su - kullanıcı` yapan insanlar ve **kök olmayan** hesapla `su` çağıran betikler (kök hesabıyla `su kullanıcı -c ...` çalışmaya devam eder).
- Yazılacak yer `/etc/pam.d/su` (dağıtım paketi `login` ezebilir; `pam-auth-update` profili değil). Dosya elle düzenleneceği için **kilitlenme riski yok** (konsol/ssh/sudo ayrı yığın), yine de ikinci bir oturum açık tutulur.
- Öneri: `hardening_su_restrict` (varsayılan `false`), `hardening_su_group` (varsayılan `sugroup`); grup yoksa **boş** olarak oluşturulur, üye eklenmez (üye yönetimi proje kapsamı dışı). Üyelik isteyen `hardening_su_group` değerini mevcut bir gruba (örn. `sudo`) çevirir.

## 3) Root ortamı (5.4.2.5, 5.4.2.6)
- **5.4.2.5 root `PATH` bütünlüğü (YAPILDI: `hardening_root_env_report`, salt okunur):** `PATH`'te boş giriş, `.`, var olmayan dizin veya grup/diğer yazılabilir dizin olmamalı. Karar verici **salt okunur rapor**: `sudo -i printenv PATH` (ya da `env -i`) çıktısını ayrıştıran, hiçbir şeyi değiştirmeyen bir betik (`time_report.py` deseni). Otomatik düzeltme önerilmez (dağıtımın `PATH`'i `/etc/environment` ve `login.defs`'te).
- **5.4.2.6 root `umask` (rapor YAPILDI, değişiklik seçeneği yapılmadı):** `0027` ya da daha kısıtlı. Yazılacak yer `/root/.bashrc`/`/root/.profile` (kullanıcı dosyasına yazmak "kullanıcı dot dosyası" sorusunu açar) ya da `login.defs` `UMASK` (tüm kullanıcıları etkiler, zaten Lynis/CIS'te başka madde). Öneri: önce **rapor**, değişiklik opt-in.

## 4) Kullanıcı dot dosyaları (7.2.9, ⚪ ölçüldü)
Örnek hesapta grup/diğer yazma yok. Yeni davranış önerilmez; yalnızca `hardening_files` desenindeki gibi **fazla izni kaldıran** bir seçenek ve salt okunur rapor düşünülebilir. `.netrc`, `.forward`, `.rhosts` varlığı rapor olur, silinmez.

## Önerilen sıra
1. `su` kısıtı (küçük, düşük risk, kolay geri alınır).
2. Root ortamı **raporu** (5.4.2.5/5.4.2.6; değiştirmez).
3. `/tmp` noexec **raporu**, sonra seçenek (VM'de paket kurma ve Ansible koşusuyla denenmeli; `/dev/shm` en son).

## Test planı (her biri için)
1. **Statik/birim:** değişken varsayılan KAPALI, `warn_if: true`, tanımlı yazım (`test_consistency`), `--check` yazmaz.
2. **Docker LAB:** `/etc/pam.d/su` içeriği (golden), grup oluşturma, `su` reddi ve root'un geçişi; `noexec` için tmpfs bağlayıp çalıştırma reddi.
3. **Gerçek VM (snapshot şart):** `su` için ikinci oturum açıkken uygula, `sudo`/ssh girişi dene; `noexec` için `apt install`, `pip install`, Ansible tam koşusu ve ikinci koşu `changed=0`.
4. **Mutasyon:** her ayar eski davranışa dönünce test düşmeli.

## Açık sorular (cevaplanmadan kod yazılmaz)
1. `/tmp`'den çalıştıran bir uygulamanız var mı (derleme sunucusu, CI koşucusu, Java/Node uygulaması)? Yoksa `noexec` makul; varsa istisna yolu (ayrı `TMPDIR`) gerekir.
2. `ansible.cfg`/sshpocket tarafında `remote_tmp` `/tmp` olarak ayarlandı mı?
3. `su` için boş grup (kimse `su` yapamaz) kabul mü, yoksa belli bir grup (`sudo`) mu istenir?
4. Root `umask` değişikliği `/root` dosyalarına mı, `login.defs`'e mi yazılsın (ikincisi tüm kullanıcıları etkiler)?
5. Raspberry Pi/LXC/bulut imajlarında `/tmp` `tmpfs` olmayabilir (dizin kök dosya sisteminde); bu durumda `noexec` ayrı bağlama gerektirir. Bu sunucu türleri var mı?

## Kapsam dışı
Ayrı disk bölümleri (`/var`, `/home`, `/var/log`, `/var/log/audit`), `/var/tmp` bağlaması, parola kalitesi ve kilitleme (bkz. `pam-faillock.md`), `sudo` yapılandırması (`hardening_sudo`).
