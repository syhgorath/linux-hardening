# Ek seçenekler: aday listeleri

**Durum:** TASARIM / ADAY LİSTESİ. Aşağıdaki belgelerde hiçbir şey **kodlanmadı**. Bu bir söz değil, karar için bir menü: her madde işaretlenir (`[x]` yap, `[-]` yapma, `[?]` konuşalım), işaretlenenler ayrı PR'larla eklenir.

## Neden

Hedef: Ubuntu, Proxmox, Debian ve Raspberry Pi için her ayar kullanıcı tarafından açılıp kapatılabilsin ve değeri değiştirilebilsin. Varsayılanlar bugünkü davranışı korur; yeni seçenekler **varsayılan pasif** gelir. Seçeneklerin hepsi bir değişkene bağlanırsa, bir tarama aracının (Lynis, ileride OpenSCAP) bulgusu `bulgular.tsv` ile doğrudan bir değişkene eşlenebilir.

## Platform sırası

1. [Ubuntu](ubuntu.md) (26.04, ana hedef)
2. [Proxmox VE](proxmox.md) (tek düğüm)
3. [Debian](debian.md) (13)
4. [Raspberry Pi](raspberry-pi.md) (en sonda; elde cihaz var ama sıra sonda)

Ubuntu ve Proxmox'ta sistemi oturtmak önceliklidir. Debian ve Pi listeleri kısadır; Ubuntu listesinin büyük kısmı Debian'a da uyar.

## Her seçenek için kurallar

- Varsayılan **pasif** (ya da bugünkü değer). Riskli olanlar `warn_if: true` (sshpocket onayı ister).
- `component.yml`'de `group`, gerekiyorsa `platforms`; `docs/known-issues.md`'ye satır; README "Dikkat" tablosuna TR/EN eşit satır.
- Birim/betik testi, **mutasyonla düştüğü doğrulanmış** (bir testi hep geçen hâle getiren imza hatasına karşı).
- **Denenmeyen seçenek açıklamasında ve belgede açıkça "DENENMEDİ" yazar.** Gerçek sunucuda denenince `docs/verification-log.md`'ye eklenir ve yazı güncellenir. Denenmemiş bir değeri güvenilir düğme gibi sunmayız.
- Erişim kaybı riski olan her şey (SSH, güvenlik duvarı, PAM) geri alma güvenlik ağının içinde çalışır; önyükleyici ve diğer ağın kapsamadığı yerler için açıkça uyarılır.
- Tek PR'da tek tema. Her PR için tam test paketi.

## Madde türleri

| Tür | Anlamı | Risk |
|---|---|---|
| **A** | Kodda sabit yazılı bir değeri değişkene çevir; varsayılan aynı, davranış değişmez | çok düşük |
| **B** | Yeni pasif seçenek | seçeneğe göre |
| **C** | Salt okunur rapor / ölçüm | yok |
| **D** | Tarama aracı entegrasyonu | araç içeriğine bağlı |

## Tarama aracı notu (OpenSCAP)

OpenSCAP'ın Ubuntu 26.04 için resmi CIS/hardening içeriği (datastream) bulunmuyor (bu belge yazılırken; araştırma yapıldı, kesin değil, yeniden bakılmalı). Paket depolarından kurulan OpenSCAP ile Canonical'ın CVE tanımları (OVAL) taranabilir, bu uyumluluk taraması değildir. Bu yüzden OpenSCAP burada **bulguları değişkene eşleyen salt okunur bir tarayıcı** olarak düşünülür, düzeltici olarak değil: kendi düzeltme betikleri bizim ayarlarımızla çakışır.
