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
> **Ön koşul:** betik `scripts/check-consistency.py`'yi çalıştırır, bunun için PyYAML'lı bir Python gerekir. En kolayı:
> `python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.txt` (betik `.venv`'i kendiliğinden
> kullanır; `.venv/` git'te ignore'dadır). Başka bir Python için `LH_PYTHON=/yol/python3`.

4. **Paketi üret, imzala ve doğrula** (tek komut; etiketten üretir, `.gitattributes` `export-ignore` dosyaları pakete girmez):
   ```bash
   LH_SIGNING_KEY=~/.ssh/<ozel_anahtar> scripts/release.sh
   ```
   Betik şunları denetler ve **herhangi biri tutmazsa durur**: çalışma alanı temiz mi, etiket HEAD'i gösteriyor mu,
   `CHANGELOG.md` başlığı var mı, `scripts/check-consistency.py` OK mi, paket içindeki `VERSION` etiketle aynı mı,
   tek kök dizin (`linux-hardening-<sürüm>/`), geliştirme dosyaları pakette yok mu. Sonra `ssh-keygen -Y sign -n sshpocket-component`
   ile imzalar, **yayından önce** aynı principal/ad alanıyla kendisi doğrular ve doğrulayıcının kullanacağı
   `allowed_signers` satırını yazdırır. Çıktı: `dist/linux-hardening-<sürüm>.tar.gz` ve `.tar.gz.sig`.

   `LH_SIGNER_ID` (varsayılan `sshpocket-component`) allowed_signers satırındaki principal'dır; **doğrulayıcının
   `-I` değeriyle aynı olmalıdır**, yoksa doğrulama anahtar doğru olsa bile genel bir "Could not verify signature."
   ile başarısız olur.

   <details><summary>Elle (betiği kullanmadan)</summary>

   ```bash
   V=0.1.0
   git archive --format=tar.gz --prefix=linux-hardening-$V/ -o linux-hardening-$V.tar.gz v$V
   ssh-keygen -Y sign -f ~/.ssh/<ozel_anahtar> -n sshpocket-component linux-hardening-$V.tar.gz
   # allowed_signers satırı: sshpocket-component namespaces="sshpocket-component" ssh-ed25519 AAAA...
   ssh-keygen -Y verify -f allowed_signers -I sshpocket-component -n sshpocket-component \
     -s linux-hardening-$V.tar.gz.sig < linux-hardening-$V.tar.gz
   ```
   </details>
5. **Yerelde doğrulanır:** betik bunu zaten yapar (yukarıda).
6. (Betik kullanılmıyorsa) paket içeriğini `tar -tzf linux-hardening-<sürüm>.tar.gz | head` ile kontrol edin.
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
