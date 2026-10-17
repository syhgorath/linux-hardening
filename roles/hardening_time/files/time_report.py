#!/usr/bin/env python3
"""Zaman senkronizasyonu raporu (SALT OKUNUR; hiçbir şeyi değiştirmez, yalnızca karar verir).

Girdi (argv[1], JSON): service (`systemctl is-active chrony` çıktısı), sources (`chronyc -c sources` satırları), ntp_synchronized
(`timedatectl show -p NTPSynchronized --value`), max_offset (saniye). Çıktı (stdout, JSON): status (ok|warn|unknown), messages, summary,
max_offset, sources, reachable, selected, error.

Neden yalnızca `timedatectl` değil: snapshot dönüşünde "System clock synchronized: yes" derken saat günlerce kayık olabiliyor ve `chronyc tracking` bayat bir
"0,016 s yavaş" gösteriyor. Güvenilir işaret kaynakların ÖLÇTÜĞÜ ofsettir (`chronyc -c sources`, alanlar: mod,durum,ad,katman,poll,reach,lastrx,ayarlı_ofset,
ölçülen_ofset,hata; durum `*` seçili, `+` birleşik, `-` birleşmeyen, `?` seçilemez). Python 3.9+ (yalnızca stdlib).
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


def decide(cfg):
    res = {"status": "ok", "messages": [], "summary": "", "max_offset": None, "sources": 0, "reachable": 0, "selected": False, "error": ""}
    try:
        limit = float(cfg.get("max_offset", 5))
    except (TypeError, ValueError):
        res.update(status="unknown", error="max_offset sayı olmalı")
        return res
    service = str(cfg.get("service", "")).strip()
    if service != "active":
        res["status"] = "warn"
        res["messages"].append("Zaman servisi (chrony) çalışmıyor (durum: %s). Saat kayabilir; `systemctl status chrony` ile bakın." % (service or "bilinmiyor"))
        return res
    srcs = parse_sources(cfg.get("sources"))
    res["sources"] = len(srcs)
    if not srcs:
        res["status"] = "warn"
        res["messages"].append("chrony'nin hiç zaman kaynağı yok ya da okunamadı (`chronyc sources`).")
        return res
    reach = [s for s in srcs if s["reach"] not in ("0", "")]
    res["reachable"] = len(reach)
    if not reach:
        res["status"] = "warn"
        res["messages"].append("Hiçbir zaman kaynağına ulaşılamıyor (reach=0): ağ/NTP erişimini (UDP 123, NTS için TCP 4460) kontrol edin.")
        return res
    res["selected"] = any(s["state"] == "*" for s in reach)
    worst = max(abs(s["offset"]) for s in reach)
    res["max_offset"] = worst
    problems = []
    if worst > limit:
        problems.append("Saat kaynaklara göre ~%s kayık (eşik %s sn)." % (human(worst), "%g" % limit))
        if str(cfg.get("ntp_synchronized", "")).strip() == "yes":
            problems.append("`timedatectl` \"synchronized: yes\" diyor ama bu yanıltıcı olabilir (snapshot dönüşünde görüldü): `date -u` ile kontrol edin.")
        problems.append("Düzeltme: `sudo chronyc makestep`; kaynaklar `?` ise etkisizdir, `sudo systemctl restart chrony` kullanın.")
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
                          "error": "girdi okunamadı: %s" % exc}))
        return 0
    print(json.dumps(decide(cfg), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
