# Yedek alma: yedek sunucusu çeker (pull), örnek

> **Bu bir ÖRNEKTİR ve DENENMEDİ.** Elimizde bir yedek sunucusu yok; adımlar ve komutlar yazıldığı gibi sınanmadı. Yalnızca şu doğrulandı: Ubuntu 26.04'te `rsync` 3.4.1 ve onunla gelen `/usr/bin/rrsync` mevcut.
> Kendi ortamınızda önce **ölü bir deneme verisiyle** deneyin, geri yüklemeyi de sınayın.
> Kullanıcı ve SSH anahtarı yönetimi bu paketin kapsamı **dışındadır** (`hardening_ssh_allow_from` dışında bu paket hesap oluşturmaz); aşağıdakiler sizin elle yapacağınız adımlardır.

## Neden "çeken" yedek (pull)?
Yedeği hedef sunucu yedek sunucusuna **göndermez**; yedek sunucusu hedefe bağlanıp **okur**. Hedef sunucu ele geçirilirse saldırgan yedek sunucusuna giriş anahtarı bulamaz, yani yedekleri silemez ya da bozamaz. Bu yüzden anahtar **yalnızca okuma** yapacak şekilde kısıtlanır.

```
yedek sunucusu  ---(SSH, kısıtlı anahtar, yalnız okuma)--->  hedef sunucu (örn. server3)
```

## 1) Hedef sunucuda: yedek kullanıcısı
Kabuk girişi olmayan, yalnız bu iş için bir kullanıcı:
```bash
sudo adduser --disabled-password --gecos "" yedekci
```
Yedeklenecek dizin bu kullanıcı tarafından **okunabilir** olmalı (örn. `/srv/veri`). Kök sahibi dosyaları (`/etc`, veritabanı dizinleri) okumak daha zordur: bunlar için dosyaları önce okunabilir bir yere döken bir betik (örn. `redis-cli --rdb`, `pg_dump`) daha güvenlidir. `sudo` ile `rsync` çalıştırmak mümkündür ama yetki genişletir ve burada **örneklenmedi**.

## 2) Yedek sunucusunda: anahtar
```bash
ssh-keygen -t ed25519 -f ~/.ssh/yedek_server3 -N '' -C "yedek@yedek-sunucu"
cat ~/.ssh/yedek_server3.pub
```
Parolasız anahtar otomasyon içindir; korunması aşağıdaki kısıtlamaya dayanır.

## 3) Hedef sunucuda: anahtarı KISITLA
`/home/yedekci/.ssh/authorized_keys` içine tek satır (kullanıcı ve dizin sahipliği `yedekci`, izinler `700`/`600`):
```
restrict,from="192.168.1.50",command="/usr/bin/rrsync -ro /srv/veri" ssh-ed25519 AAAA... yedek@yedek-sunucu
```
- `restrict`: port yönlendirme, terminal, X11 ve ajan yönlendirmesini kapatır.
- `from="..."`: anahtar yalnızca yedek sunucusunun adresinden çalışır (`192.168.1.50` yer tutucudur).
- `command="/usr/bin/rrsync -ro /srv/veri"`: bu anahtarla **yalnızca** `/srv/veri` altını **salt okunur** `rsync` ile okuyabilirsiniz; başka komut çalışmaz.

## 4) Hedef sunucuda: bu paketin SSH/güvenlik duvarı
- `hardening_ssh_allow_from` listesine **yedek sunucusunun ağını/adresini ekleyin**; yoksa ufw SSH'ı yedek sunucusuna kapatır (bkz. `README.md`, `examples/group_vars/infra.yml`).
- Paket SSH'ta kök girişini kapatır (`PermitRootLogin no`); bu örnekte kök kullanılmıyor, sorun olmaz.
- `hardening_ssh_allow_from` değişince bağlanabilen ağlar değişir: önce `--check --diff`.

## 5) Yedek sunucusunda: çekme
```bash
rsync -a -e "ssh -i ~/.ssh/yedek_server3" yedekci@server3:/ /yedekler/server3/
```
Uzak yol `/`, `rrsync`'in kökü olan `/srv/veri`'ye karşılık gelir. **Dikkat:** `--delete` eklerseniz hedefte silinen dosya yedekten de silinir; hedef boşalırsa yedek de boşalır. Sürümlü yedek için `--link-dest` ile günlük klasörler (sabit bağlarla yer tasarrufu) daha güvenlidir:
```bash
D=/yedekler/server3; T=$(date +%F)
rsync -a -e "ssh -i ~/.ssh/yedek_server3" --link-dest="$D/son" yedekci@server3:/ "$D/$T/" && ln -sfn "$D/$T" "$D/son"
```
Düzenli çalıştırmak için yedek sunucusunda bir `systemd` zamanlayıcı ya da `cron` kullanın.

## 6) Doğrulama (önce yapın)
- Kısıtlama çalışıyor mu: `ssh -i ~/.ssh/yedek_server3 yedekci@server3 id` **komutu çalıştırmamalı** (kısıtlı komut `id` yerine `rrsync`'e gider ve hata verir).
- Yazma kapalı mı: `rsync -a deneme.txt -e "ssh -i ~/.ssh/yedek_server3" yedekci@server3:/` **reddedilmeli**.
- Geri yükleme: yedekten bir dosyayı gerçekten başka bir yere geri koyup içeriğini karşılaştırın. Geri yüklenmemiş yedek yedek sayılmaz.

## Bu örneğin söylemedikleri
Veritabanı tutarlılığı (canlı veritabanı dosyasını doğrudan kopyalamak bozuk yedek verir), şifreli yedek, yedeğin kendi sunucusunun sertleştirilmesi ve izleme (yedek çalıştı mı?). Bunlar sizin ortamınıza bağlıdır ve bu paketin işi değildir.
