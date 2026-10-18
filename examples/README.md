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

## Uygulama sırası (öneri)
Her sunucu için: snapshot → `--check --diff` → uygula → ikinci koşu `changed=0` mı. Sıra: önce **server3** (en az hizmet), sonra **server1**, en son **server2** (Docker).

## Dikkat
- Bu proje Redis/nginx/Docker'ın kendi ayarlarını yönetmez (Redis parolası ve bağlama adresi, vekil yapılandırması sizin işiniz).
- Kullanıcı ve SSH anahtarı (yedek kullanıcısı dahil) yönetilmez.
- Davranışı değiştiren seçenekler için README'deki "Dikkat" bölümüne bakın.
