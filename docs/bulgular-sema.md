# `bulgular.tsv` şeması

`audit` eylemi, Lynis bulgularını tablo olarak gösterebilmek için `summary.json`'ın yanına (`<host>/<tarih>/`, 0600) `bulgular.tsv` yazar. Manifestte `actions.audit.outputs.findings: "bulgular.tsv"` yalnız dosya adını bildirir (düz ad, `.tsv`, en çok 64 karakter). Bulgular yalnız **gösterim** içindir: dosya yoksa ya da bozuksa denetim ve sertleştirme eskisi gibi çalışır.

Dosya tek (son) audit koşusunu içerir; her audit dosyayı baştan yazar. Bulgu yoksa yalnızca başlık satırı yazılır. UTF-8, sekmeyle ayrılmış, ilk satır başlık; **başlık satırı şemadır** (ayrı sürüm alanı yok). İleride sona sütun eklenebilir, mevcut sütunların adı, sırası ve anlamı değişmez.

| # | sütun | değerler |
|---|---|---|
| 1 | `kimlik` | Lynis test kimliği (örn. `SSH-7408`); kimliksiz madde için `GENEL-<n>`. Tek başına benzersiz DEĞİL |
| 2 | `risk` | `yuksek`, `orta`, `dusuk`, `bilgi`, `bilinmiyor`. Lynis önem vermez; yalnız eşleme tablosunda karşılığı olan bulguya yazılır, yoksa `bilinmiyor` |
| 3 | `tur` | `uyari` (Lynis `warning[]`) ya da `oneri` (`suggestion[]`) |
| 4 | `aciklama` | Lynis açıklaması, tek satır |
| 5 | `ayrinti` | Lynis ayrıntı alanı; aynı kimlik birden çok satırda gelirse ayırt edici (örn. `MaxSessions (set 4 to 2)`) |
| 6 | `oneri` | Lynis çözüm alanı, yoksa boş |
| 7 | `alan` | sertleştirme alanı kimliği (`ssh`, `base`, `files` …) ya da boş |
| 8 | `deger` | `ad=değer` (ilgili değişken ve önerilen değer) ya da boş |
| 9 | `kapanir_varsayilan` | `evet`/`hayir`: `alan`/`deger` doluyken bu değer paketin varsayılanıyla zaten uygulanıyor mu; yoksa boş |
| 10 | `platform` | `ubuntu`, `proxmox` ya da `hepsi` |

Lynis'in `-` ve boş alanları boş yazılır; sekme ve satır sonu boşluğa çevrilir. `alan`, `deger`, `kapanir_varsayilan`, `platform` ve bilinen `risk` pakette sabit bir eşleme tablosundan gelir; tabloda olmayan bulgu bu sütunlar boş olarak yine listelenir.

## Nasıl üretilir

`playbooks/audit.yml`, Lynis raporunu çektikten sonra `playbooks/tasks/bulgular.yml` görevini çalıştırır. Görev `filter_plugins/hardening_bulgular.py` süzgeciyle `lynis-report.dat` içindeki `warning[]` ve `suggestion[]` satırlarını bu tabloya çevirir ve `vars/bulgular-eslesme.tsv` ile birleştirir. Süzgeç `ansible.cfg` içindeki `filter_plugins` yoluyla bulunur.

Eşleme tablosu elle bakılan, yalnızca **kodda doğrulanmış** bulguları içeren küçük bir listedir; olmayan bulgu eşlemesiz listelenir. `test/test_bulgular.py` her satırı `component.yml` ile çapraz denetler: `alan` geçerli olmalı, `deger` içindeki değişken var olmalı ve `kapanir_varsayilan=evet` ancak önerilen değer değişkenin varsayılanıyla aynıysa yazılabilir. Yeni bulgu eklerken önce ilgili seçeneğin kodda gerçekten o Lynis kimliğini hedeflediğini doğrulayın.

Üretim hata verirse (bozuk rapor, eksik eşleme dosyası ya da süzgeç hatası) `bulgular.tsv` yazılmaz ya da eşleme sütunları boş kalır; denetim ve rapor etkilenmez. `--check` modunda audit zaten tarama yapmaz, dosya üretilmez.
