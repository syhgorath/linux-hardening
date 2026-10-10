## Ne/neden?

<!-- Değişikliğin amacı. Mümkünse tek konu, küçük PR. -->

## Etki
- [ ] **BREAKING** (mevcut davranışı/varsayılanı kırıyor) → PR başlığında/açıklamasında belirttim ve `docs/decisions.md`'ye yazdım
- [ ] Erişim kaybı riski var (SSH/ufw/kimlik doğrulama) → korumalar ve geri alma yolu etkilenmedi/test edildi

## Nasıl test ettiniz?
- [ ] `test/run-all.sh` yerelde geçiyor (CI de koşar)
- [ ] Yeni davranış için test eklendi (`test/`); bilerek değişen golden dosyaları PR'da açıkladım
- [ ] `--check --diff` temiz, ikinci çalıştırmada `changed=0` (idempotent) — **gerçek bir hedefte denendi**: evet / hayır (aşağıya yazın)
- [ ] Etiketli çalıştırma (`--tags ...`) korumaları atlamıyor (yeni `include_role` varsa `apply: tags:`)

**Canlı VM testi:** <!-- yapıldı (çıktıyı ekleyin) | BEKLİYOR | gerekmiyor (yalnızca belge) -->

## Gizlilik
- [ ] Gizli bilgi (anahtar, parola, gerçek IP/hostname, tarama çıktısı) içermiyor (örnek aralık: `192.0.2.x`)
- [ ] `CHANGELOG.md` *Yayımlanmamış* bölümüne eklendi (kullanıcıyı etkiliyorsa)
