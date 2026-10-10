# Katkı rehberi / Contributing

Proje genç ve gelişmeye açık; hata raporu, test, belge, çeviri ve kod katkıları makbule geçer.
*The project is young and open to bugs, tests, docs, translations and code.*

## Başlamadan / Before you start

- Büyük bir değişiklik düşünüyorsanız önce bir issue açıp konuşalım.
- **Gizli bilgi paylaşmayın:** issue/PR'a gerçek IP, anahtar, parola, hostname veya tarama çıktısı yapıştırmayın.
  Gerekirse `192.0.2.x` (örnek aralık) kullanın.
- Güvenlik açıkları için herkese açık issue **açmayın**: [SECURITY.md](SECURITY.md).

## İlkeler

1. **Erişim kaybı birinci öncelik.** Bu araç sunucularda kök yetkisiyle çalışır ve SSH/firewall'ı değiştirir.
   Yeni davranış korumaları (`hardening_ssh_allow_from`, kaynak IP/root kontrolü, bağlantı doğrulaması) zayıflatmamalı.
2. **Güvenli varsayılan.** Yeni değişkenin varsayılanı mevcut davranışı korumalı ya da daha güvenli olmalı.
3. **Küçük, tek konulu PR.** Mevcut davranışı kıran değişiklik PR açıklamasında **BREAKING** diye belirtilir ve
   `docs/decisions.md`'ye gerekçesiyle yazılır.
4. **Kararlar kayıtlı.** Bilerek yapılmayanlar ve istisnalar `docs/decisions.md` içindedir.

## Geliştirme ortamı

```bash
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements-dev.txt     # Python >= 3.12
export PATH="$PWD/.venv/bin:$PATH"
test/run-all.sh                  # tüm testler (CI aynısını çalıştırır)
test/run-all.sh summary          # adında "summary" geçen testler
```

PR açmadan önce `test/run-all.sh` temiz olmalı. Testler gerçek sunucuya dokunmaz (yerel bağlantı, sahte `SSH_CONNECTION`,
sahte `id`, geçici dizinler). Test listesi için [README.md](README.md) "Testler" bölümüne bakın.

### Sık karşılaşılanlar
- **Golden dosyalar** (`test/golden/`) varsayılan şablon çıktılarıdır. Bilerek değiştirdiyseniz:
  `UPDATE_GOLDEN=1 python3 -I test/test_templates.py` ve farkı PR'da açıklayın.
- **`include_role`'a etiket verirken** `apply: tags:` ekleyin; yoksa `--tags` ile içteki görevler atlanır
  (`test_tags_and_hosts.sh` bunu yakalar).
- **Handler yeniden adlandırırsanız** `notify:` değerini de güncelleyin (`test_handlers.py` yakalar).
- **Bağımlılık eklerken** `requirements.in` / `requirements-dev.in` güncelleyip hash'li dosyayı yeniden üretin:
  `pip-compile --generate-hashes --strip-extras -o requirements.txt requirements.in`.
  Python'un **en düşük** desteklenen sürümünde (3.12) kurulumun da çalıştığını CI'daki `runtime-install` doğrular.

## Gerçek hedef testi

Sunucu davranışını değiştiren her PR için bir Ubuntu test VM'inde (snapshot alın) şu sırayla deneyin:

1. `ansible-playbook playbooks/harden.yml --check --diff` temiz,
2. uygulayın,
3. ikinci çalıştırmada `changed=0` (idempotent),
4. **yeni bir oturumla** bağlantının korunduğunu doğrulayın.

Bunu yapamadıysanız PR açıklamasında "canlı test **bekliyor**" diye açıkça yazın; bu kabul edilebilir, gizlenmesi değil.

## Yeni sürüm / dağıtım eklemek

[docs/SUPPORT.md](docs/SUPPORT.md) içindeki adımları izleyin (`vars/<dagitim>-<surum>.yml`, `hardening_supported_os`,
`component.yml` profilleri, destek tablosu). `test_consistency.sh` bunların tutarlılığını denetler.

## Sürüm çıkarma

Yalnızca bakımcı: [docs/RELEASING.md](docs/RELEASING.md).

## PR süreci

1. Fork → dal açın (`fix/...`, `feat/...`).
2. Değişikliği, testi ve belgeyi ekleyin; `CHANGELOG.md`'nin *Yayımlanmamış* bölümüne bir satır yazın.
3. PR şablonunu doldurun (etki, test, canlı test durumu, gizlilik).
4. CI'daki yedi kontrolün (tests ×3, runtime-install ×3, linux-smoke) yeşil olması birleştirme için zorunludur.

Yapay zekâ yardımıyla yazılmış katkılar kabul edilir; gönderdiğiniz kodu okuyup anladığınızdan ve test ettiğinizden emin olun.
