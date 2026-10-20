# Örnekler: birden fazla sunucu

Üç sunucu örneği: **server1** web + veritabanı + php, **server2** Docker (+ ters vekil), **server3** Redis + günlük + yedek. Adresler yer tutucudur.

## Katmanlar
Ansible değişkenleri şu sırayla ezer (sağdaki kazanır):

```
rol varsayılanı  <  group_vars/all.yml  <  group_vars/<grup>.yml  <  host_vars/<sunucu>.yml  <  -e
```

| Dosya | Ne yazılır |
|---|---|
| `group_vars/all.yml` | Üç sunucuda aynı olan (SSH'a izinli ağlar) |
| `group_vars/<grup>.yml` | O **türün** ihtiyacı: açılacak portlar, açık/kapalı sertleştirmeler |
| `host_vars/<sunucu>.yml` | Yalnızca o **tek** sunucuya özel olan |

**Tuzak:** Ansible liste değişkenlerini birleştirmez, **ezer**. `host_vars`'a `hardening_ufw_extra_allow` yazarsanız grubunki silinir. Sunucuya özel portlar için `hardening_ufw_extra_allow_host` kullanın; rol ikisini birleştirir:

```yaml
# host_vars/server3.yml
hardening_ufw_extra_allow_host:
  - "from 192.168.1.20 to any port 9100 proto tcp"   # yalnızca bu sunucuda, izleme
```

## İki kullanım
1. **Düz Ansible:** `inventory.example.yml` ve `group_vars/` dizinini yan yana koyun, `ansible-playbook -i inventory.example.yml playbooks/harden.yml --check --diff` ile önizleyin. Tek sunucu: `--limit server3`.
2. **sshpocket:** sshpocket `group_vars` görmez; sunucu başına bir değişken dosyası verilir: `sshpocket/server1-web.yml` vb. (group_vars birleşiminin kopyasıdır; `test/test_examples.py` ikisinin tutarlı kaldığını denetler).

## Ayarlarım nerede? Güncellemede ne olur?
Üç ayrı şey var; karıştırmak en sık yapılan hata:

| Ne | Nerede durur | Yeni sürümde |
|---|---|---|
| **Kod** (roller, varsayılanlar, bu `examples/` örnekleri) | `linux-hardening/` klasörü | Klasör yeni sürümle **değişir** |
| **Sizin ayarlarınız** (hangi sunucuda ne açık/kapalı) | `linux-hardening/` **dışında**: kendi `group_vars/`, `host_vars/` dosyalarınız ya da (sshpocket) sunucu başına değişken dosyası | **Dokunulmaz** |
| **Sunucunun kendisi** | Gerçek sunucu | Rol çalışınca değişir |

Yani klasörü güncellemek ayarlarınızı silmez, çünkü ayarlar klasörde durmaz. `examples/` yalnızca **kopyalayıp başlangıç yapmanız** içindir; onu doğrudan düzenlemeyin.

**Düz Ansible için öneri:** kendi ayarlarınızı klasörün dışında tutun ve envanteri oradan verin. `group_vars/`, envanter dosyasının yanındaysa Ansible onu kendiliğinden yükler:
```
~/lh-ayarlar/
  inventory.yml
  group_vars/all.yml  web.yml  docker.yml  ...
```
```bash
ansible-playbook -i ~/lh-ayarlar/inventory.yml /yol/linux-hardening/playbooks/harden.yml --check --diff
```
`group_vars/`'ı `linux-hardening/playbooks/` içine koyarsanız sürüm değişiminde klasörle birlikte kaybolur.

**sshpocket ile:** her sunucuya kendi değişken dosyası verilir (`sshpocket/server1-web.yml` gibi); "grup" kavramı yoktur, grup birleşimini siz dosyaya yazarsınız (bu klasördeki dosyalar böyle üretilmiş ve `test/test_examples.py` ile kaymaları denetlenir). Bu dosyaların sshpocket tarafında nerede saklandığı bu deponun kapsamı **dışındadır**; oradaki belgeye bakın.

### Bir ayarı "hepsinde aç, bir grupta kapat"
Katman sırası (sağdaki kazanır) bunu kendiliğinden yapar. Örnek: `hardening_pam_tmpdir` varsayılan olarak **açık**tır (`$TMPDIR` oturum başına özel dizin olur). `/tmp`'i sabit varsayan bir uygulamanız `web` sunucusundadır ve bozulmasını istemiyorsunuz:
```yaml
# group_vars/web.yml   (all.yml'ye ve diğer gruplara dokunmaz)
hardening_pam_tmpdir: false
```
Diğer sunucular varsayılanı alır, `web` grubu kapatır. Aynı yöntemi ileride eklenecek benzer seçenekler (örneğin `/tmp` için `noexec`) için de kullanırsınız: önce hepsinde aç, PHP'li sunucu grubunda kapat.

### Yeni sürüme geçerken
1. Yeni `linux-hardening` klasörünü alın; **kendi ayarlarınıza dokunmayın**.
2. `CHANGELOG.md`'de sürümün **"Dikkat"** bölümüne bakın: yeni sürüm bazı seçenekleri **varsayılan açık** getirebilir. Ayarlarınız o seçeneği hiç anmıyorsa varsayılan geçerli olur.
3. Her sunucuda önce `--check --diff` çalıştırın, sonra uygulayın, ikinci koşuda `changed=0` olmalı.
4. Beğenmediğiniz yeni varsayılanı kendi `group_vars` dosyanızda `false` yapın.

## Uygulama sırası (öneri)
Her sunucu için: snapshot → `--check --diff` → uygula → ikinci koşu `changed=0` mı. Sıra: önce **server3** (en az hizmet), sonra **server1**, en son **server2** (Docker).

## Dikkat
- Bu proje Redis/nginx/Docker'ın kendi ayarlarını yönetmez (Redis parolası ve bağlama adresi, vekil yapılandırması sizin işiniz).
- Kullanıcı ve SSH anahtarı (yedek kullanıcısı dahil) yönetilmez.
- Davranışı değiştiren seçenekler için README'deki "Dikkat" bölümüne bakın.
