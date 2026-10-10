# Sürüm paketi üretimi

Bu belge bakımcının makinesinde yapılacak adımları anlatır. **İmza için kullanılan özel anahtar repoda ve CI'da
bulunmaz**; yalnızca bakımcının makinesindedir.

## Adlandırma
- Paket: `linux-hardening-<sürüm>.tar.gz`
- İmza: `linux-hardening-<sürüm>.tar.gz.sig`
- Paket içindeki kök dizin: `linux-hardening-<sürüm>/`
- Git etiketi: `v<sürüm>` (etiketi bakımcı atar)

## Adımlar
1. **Sürümü yükselt:** `VERSION`, `component.yml` içindeki `version` ve `CHANGELOG.md`'ye yeni başlık
   (`## [x.y.z] - YYYY-AA-GG`). Üçü aynı olmalı.
2. **Tutarlılığı denetle** (PyYAML'ın kurulu olduğu ortamda, örn. `.venv`):
   ```bash
   python3 -I scripts/check-consistency.py     # "OK: ..." görmelisin
   ```
   Bu betik VERSION/CHANGELOG/component.yml, profiller ↔ `hardening_supported_os` ↔ `docs/SUPPORT.md` ve `vars`
   tutarlılığını kontrol eder.
3. **Etiketle** (bakımcı): `git tag -s v<sürüm> -m "linux-hardening <sürüm>"` ve `git push origin v<sürüm>`.
4. **Paketi üret** (etiketten; `.gitattributes` içindeki `export-ignore` dosyaları pakete girmez):
   ```bash
   V=0.1.0
   git archive --format=tar.gz --prefix=linux-hardening-$V/ -o linux-hardening-$V.tar.gz v$V
   tar -tzf linux-hardening-$V.tar.gz | head       # kök dizin adını kontrol et
   ```
5. **İmzala** (ad alanı `sshpocket-component`):
   ```bash
   ssh-keygen -Y sign -f ~/.ssh/<ozel_anahtar> -n sshpocket-component linux-hardening-$V.tar.gz
   # -> linux-hardening-$V.tar.gz.sig
   ```
6. **Yerelde doğrula:**
   ```bash
   # allowed_signers satırı: sshpocket-component namespaces="sshpocket-component" ssh-ed25519 AAAA...
   ssh-keygen -Y verify -f allowed_signers -I sshpocket-component -n sshpocket-component \
     -s linux-hardening-$V.tar.gz.sig < linux-hardening-$V.tar.gz
   ```
7. **Yayımla:** GitHub Release'e `.tar.gz` ve `.tar.gz.sig` dosyalarını ekle.

## sshpocket tarafında gerekenler (bu repoda YAPILMAZ)
İmza ad alanı bilerek **`sshpocket-component`**'tir; sshpocket çekirdeğinin `sshpocket-release` ad alanından ayrıdır
(bileşen anahtarı ele geçirilse çekirdek güncellemesi imzalanamasın). Bunun için sshpocket'te ayrı bir değişiklik gerekir:
bileşen imzalayıcıları için ayrı bir `allowed_signers` dosyası ve doğrulayıcının `-n sshpocket-component` ile
çağrılması. Bu repo yalnızca paketi ve imzayı üretir.

## Bağımlılıkları güncelleme
`requirements.in` değiştiğinde hash'li dosyayı yeniden üretin ve temiz bir ortamda deneyin:
```bash
pip-compile --generate-hashes --strip-extras -o requirements.txt requirements.in
python3 -m venv /tmp/denemevenv && /tmp/denemevenv/bin/pip install --require-hashes -r requirements.txt
```
