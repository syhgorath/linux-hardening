# İlerleme satırları (`SSHPOCKET_PROGRESS`)

Sertleştirme koşusu, her **alan** için canlı akışa tek satırlık ilerleme bilgisi yazar. Satırları `callback_plugins/sshpocket_progress.py` üretir; `ansible.cfg` eklentiyi (`callbacks_enabled`, `callback_plugins = ./callback_plugins`) kendisi etkinleştirir, yani `ansible-playbook` elle çalıştırılınca da aynı davranır. Eklenti bir **bildirim** eklentisidir: mevcut çıktıyı değiştirmez, yalnız satır ekler.

## Biçim

Tek satır, `anahtar=değer`, boşluksuz ve yalnız ASCII. Satır `SSHPOCKET_RESULT` sözcüğünü içermez. Ayrıştırıcı bilinmeyen anahtarları yok saymalıdır; mevcut anahtarların adı ve anlamı değişmez.

```
SSHPOCKET_PROGRESS alan=aide sira=9/14 durum=basladi
SSHPOCKET_PROGRESS alan=aide sira=9/14 durum=basladi bekle_tahmin=300
SSHPOCKET_PROGRESS alan=aide sira=9/14 durum=bitti degisen=2 atlanan=0 kesin=1
SSHPOCKET_PROGRESS alan=ufw sira=13/14 durum=bitti degisen=0 atlanan=3 kesin=0 uyari=1
```

| anahtar | anlamı |
|---|---|
| `alan` | sabit kimlik: `base`, `auth`, `kernel`, `apparmor`, `files`, `docker`, `auditd`, `fail2ban`, `aide`, `time`, `report`, `pve_pveproxy`, `pam_faillock`, `ufw`, `ssh`, `sudo` |
| `sira` | `n/toplam`. `toplam` bir koşu boyunca sabittir ve yalnız **açık** alanları sayar (önizlemede de aynı sayı) |
| `durum` | `basladi` ya da `bitti`. Hata veren alan için `bitti` **yazılmaz** |
| `bekle_tahmin` | yalnız ikinci `basladi` satırında: uzun görev gerçekten beklemeye başlayınca tahmini saniye (şimdilik yalnız `aide`, 300) |
| `degisen` | yalnız `bitti`: değişen görev sayısı. Önizlemede "uygulanırsa değişecek" anlamındadır |
| `atlanan` | yalnız `bitti`: atlanan görev sayısı (koşul yanlış ya da önizlemede atlanan) |
| `kesin` | yalnız `bitti`: `0` ise sayı **tahminidir**: önizlemede bazı görevler (komut/shell) çalıştırılmadığı için sonucu bilinmiyor. Uygulamada hep `1` |
| `uyari` | yalnız `bitti` ve yalnız n>0 iken: `UYARI` ile başlayan ve gösterilen ileti sayısı |

"Açık alan", `playbooks/harden.yml` içindeki **İlerleme planı** görevinin hesapladığı listedir: alan anahtarı ya da koşulu açık olan alanlar (ufw Proxmox'ta listede yoktur). Rolün iç atlamaları alanı kapatmaz. Liste `roles:` ile aynı sırada ve adlarda olmalıdır; `test/test_ilerleme.py` bunu denetler. `--tags` ile tek alan çalıştırıldığında yalnız o alanın satırları gelir, `toplam` yine tam açık-alan sayısıdır.

## Eklenti yoksa ya da bozulursa

Eklenti yüklenmezse (ya da çalışırken bir istisna olursa) hiçbir `SSHPOCKET_PROGRESS` satırı yazılmaz ve sertleştirme **aynen sürer**: eklenti hatası koşuyu durdurmaz ve uyarı bile basmaz. Satırın yokluğu "ilerleme bilinmiyor" demektir.

## Bilinen davranışlar

- Son alanın `bitti` satırı, alanın kendisinden sonra başka bir rol çalışmadığında `PLAY RECAP` bloğundan **sonra** gelir. Tam kurulumda `sudo` alanından sonra erişim doğrulaması rolü çalıştığı için normalde bundan önce yazılır.
- Çoklu sunucuda sayılar sunucular üzerinden toplanır.
