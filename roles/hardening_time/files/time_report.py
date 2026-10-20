#!/usr/bin/env python3
"""Zaman senkronizasyonu raporu (SALT OKUNUR; hiçbir şeyi değiştirmez, yalnızca karar verir).

Girdi (argv[1], JSON): service (`systemctl is-active chrony` çıktısı), sources (`chronyc -c sources` satırları), ntp_synchronized
(`timedatectl show -p NTPSynchronized --value`), max_offset (saniye); isteğe bağlı target_epoch / controller_epoch (sunucunun ve kontrol makinesinin
`date +%s` değeri; ikisi de sayıysa çapraz kontrol yapılır). Çıktı (stdout, JSON): status (ok|warn|unknown), messages, summary,
max_offset, sources, reachable, selected, fix, error. `fix`: raporun önerdiği düzeltme ("makestep" | "restart" | ""); YALNIZCA bilgidir, bu betik hiçbir şey çalıştırmaz
(isteğe bağlı hardening_time_makestep açıksa rol bunu uygular).

Neden yalnızca `timedatectl` değil: snapshot dönüşünde "System clock synchronized: yes" derken saat günlerce kayık olabiliyor ve `chronyc tracking` bayat bir
"0,016 s yavaş" gösteriyor. Güvenilir işaret kaynakların ÖLÇTÜĞÜ ofsettir (`chronyc -c sources`, alanlar: mod,durum,ad,katman,poll,reach,lastrx,ayarlı_ofset,
ölçülen_ofset,hata; durum `*` seçili, `+` birleşik, `-` birleşmeyen, `?` seçilemez). Kaynak seçilmemişse (`*` yok; durumlar `~` çok değişken, `?` seçilemez) ölçülen ofset GÜVENİLİR sayılmaz: test VM'inde snapshot dönüşünde saat ~8 gün geride
iken kaynaklar `~` ve ofset yalnızca -9,2 sn gösterdi. Bu yüzden büyüklük o durumda "kesin" diye yazılmaz ve sunucu saati kontrol makinesinin saatiyle ayrıca
karşılaştırılır (kontrol makinesinin saati de yanlış olabilir; mesaj bunu söyler). Python 3.9+ (yalnızca stdlib).
"""
import json
import sys


def human(seconds):
    s = abs(float(seconds))
    if s < 1:
        return "%.0f ms" % (s * 1000)
    if s < 60:
        return "%.1f sn" % s
    parts = []
    for name, size in (("gün", 86400), ("sa", 3600), ("dk", 60)):
        n = int(s // size)
        if n:
            parts.append("%d %s" % (n, name))
            s -= n * size
    if s >= 1 and len(parts) < 2:
        parts.append("%d sn" % round(s))
    return " ".join(parts[:2])


def parse_sources(lines):
    out = []
    for line in lines or []:
        f = [x.strip() for x in str(line).split(",")]
        if len(f) < 9:
            continue
        try:
            out.append({"state": f[1], "name": f[2], "reach": f[5], "offset": float(f[7])})
        except ValueError:
            continue
    return out


def epoch_skew(cfg, limit):
    """Sunucu - kontrol makinesi saat farkı (sn) ya da None; eşik en az 30 sn (komut/ağ gecikmesi yanlış alarm vermesin)."""
    try:
        diff = float(cfg["target_epoch"]) - float(cfg["controller_epoch"])
    except (KeyError, TypeError, ValueError):
        return None
    return diff if abs(diff) > max(limit, 30.0) else None


def skew_message(diff):
    return ("Sunucu saati, kontrol makinesinin saatine göre ~%s %s (kontrol makinesinin saati de yanlış olabilir; `date -u` ile ikisini kıyaslayın)."
            % (human(diff), "geride" if diff < 0 else "ileride"))


def decide(cfg):
    res = {"status": "ok", "messages": [], "summary": "", "max_offset": None, "sources": 0, "reachable": 0, "selected": False, "fix": "", "error": ""}
    try:
        limit = float(cfg.get("max_offset", 5))
    except (TypeError, ValueError):
        res.update(status="unknown", error="max_offset sayı olmalı")
        return res
    service = str(cfg.get("service", "")).strip()
    if service != "active":
        res["status"] = "warn"
        res["messages"].append("Zaman servisi (chrony) çalışmıyor (durum: %s). Saat kayabilir; `systemctl status chrony` ile bakın." % (service or "bilinmiyor"))
        skew = epoch_skew(cfg, limit)
        if skew is not None:
            res["messages"].append(skew_message(skew))
        return res
    srcs = parse_sources(cfg.get("sources"))
    res["sources"] = len(srcs)
    if not srcs:
        res["status"] = "warn"
        res["messages"].append("chrony'nin hiç zaman kaynağı yok ya da okunamadı (`chronyc sources`).")
        skew = epoch_skew(cfg, limit)
        if skew is not None:
            res["messages"].append(skew_message(skew))
        return res
    reach = [s for s in srcs if s["reach"] not in ("0", "")]
    res["reachable"] = len(reach)
    if not reach:
        res["status"] = "warn"
        res["messages"].append("Hiçbir zaman kaynağına ulaşılamıyor (reach=0): ağ/NTP erişimini (UDP 123, NTS için TCP 4460) kontrol edin.")
        skew = epoch_skew(cfg, limit)
        if skew is not None:
            res["messages"].append(skew_message(skew))
        return res
    res["selected"] = any(s["state"] == "*" for s in reach)
    worst = max(abs(s["offset"]) for s in reach)
    res["max_offset"] = worst
    problems = []
    skew = epoch_skew(cfg, limit)
    if worst > limit:
        if res["selected"]:
            problems.append("Saat kaynaklara göre ~%s kayık (eşik %s sn)." % (human(worst), "%g" % limit))
        else:
            problems.append("Kaynakların ölçtüğü ofset ~%s ama hiçbir kaynak seçilmediği için bu değere GÜVENİLMEZ (gerçek kayma çok daha büyük olabilir; eşik %s sn)."
                            % (human(worst), "%g" % limit))
    if skew is not None:
        problems.append(skew_message(skew))
    if worst > limit or skew is not None:
        if str(cfg.get("ntp_synchronized", "")).strip() == "yes":
            problems.append("`timedatectl` \"synchronized: yes\" diyor ama bu yanıltıcı olabilir (snapshot dönüşünde görüldü): `date -u` ile kontrol edin.")
        problems.append("Düzeltme: `sudo chronyc makestep`; kaynaklar `?` ise etkisizdir, `sudo systemctl restart chrony` kullanın.")
        res["fix"] = "makestep" if res["selected"] else "restart"
    if not res["selected"]:
        problems.append("Hiçbir kaynak seçilmedi (senkron değil); chrony henüz kaynak seçemedi.")
    if problems:
        res["status"] = "warn"
        res["messages"] = problems
    else:
        res["summary"] = "chrony senkron: %d kaynak (%d ulaşılabilir), seçili kaynak var, en büyük ofset %s." % (len(srcs), len(reach), human(worst))
    return res


def main(argv):
    try:
        cfg = json.loads(argv[1])
        if not isinstance(cfg, dict):
            raise ValueError("nesne değil")
    except (IndexError, ValueError) as exc:
        print(json.dumps({"status": "unknown", "messages": [], "summary": "", "max_offset": None, "sources": 0, "reachable": 0, "selected": False,
                          "fix": "", "error": "girdi okunamadı: %s" % exc}))
        return 0
    print(json.dumps(decide(cfg), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
