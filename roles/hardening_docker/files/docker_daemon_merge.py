#!/usr/bin/env python3
"""daemon.json'u BİRLEŞTİRİR (üzerine yazmaz): mevcut anahtarlar korunur, istenen anahtarlar eklenir/güncellenir (yazmaz, yalnızca karar verir).

Girdi (argv[1], JSON): existing (daemon.json metni; boş olabilir), settings (eklenecek anahtarlar). Çıktı (stdout, JSON): changed, text (yeni dosya içeriği; değişmediyse eski), error.
Kurallar: geçersiz JSON ya da nesne olmayan üst düzey -> error (HİÇBİR ŞEY yazılmaz, çünkü kullanıcının ayarını silmek yanlış olur); sözlük değerleri (örn. log-opts)
birleştirilir (mevcut alt anahtarlar korunur, istenenler üzerine yazılır); diğer değerler değiştirilir; değişiklik yoksa changed=false (idempotent).
Python 3.9+ (yalnızca stdlib).
"""
import json
import sys


def merge(existing_text, settings):
    res = {"changed": False, "text": existing_text, "error": ""}
    if not isinstance(settings, dict):
        res["error"] = "settings nesne olmalı"
        return res
    text = (existing_text or "").strip()
    if text:
        try:
            current = json.loads(text)
        except ValueError as exc:
            res["error"] = "mevcut daemon.json geçerli JSON değil (%s); dokunulmadı" % exc
            return res
        if not isinstance(current, dict):
            res["error"] = "mevcut daemon.json bir JSON nesnesi değil; dokunulmadı"
            return res
    else:
        current = {}
    new = json.loads(json.dumps(current))  # derin kopya
    for key, val in settings.items():
        if isinstance(val, dict) and isinstance(new.get(key), dict):
            merged = dict(new[key])
            merged.update(val)
            new[key] = merged
        else:
            new[key] = val
    if new != current:
        res["changed"] = True
        res["text"] = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
    return res


def main(argv):
    try:
        cfg = json.loads(argv[1])
        out = merge(cfg.get("existing", ""), cfg.get("settings"))
    except (IndexError, ValueError, AttributeError) as exc:
        out = {"changed": False, "text": "", "error": "girdi okunamadı: %s" % exc}
    print(json.dumps(out, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
