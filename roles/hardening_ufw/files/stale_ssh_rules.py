#!/usr/bin/env python3
"""allow_from'da OLMAYAN, bu rolün yazdığı biçimdeki ufw SSH kurallarını bulur (silmez; yalnızca karar verir).

Girdi (argv[1], JSON): allow_from, ssh_ports, extra_allow, controller (kontrol makinesinin sunucudan görünen adresi), added
(`ufw show added` satırları). Çıktı (stdout, JSON): stale, blocked, skipped, missing, error.
`missing`: allow_from'daki her ağ x SSH portu için ufw'de kural YOKSA listelenir (silmeden sonra doğrulama: boş değilse rol ufw enable'dan önce durur).

Güvenlik (yanlış silmek erişim kaybıdır): yalnızca tam olarak `ufw allow from <ağ> to any port <ssh portu> proto tcp [comment '...']` biçimi
değerlendirilir; ağlar `ipaddress` ile normalleştirilerek karşılaştırılır (192.0.2.1 == 192.0.2.1/32); allow_from boş/çözülemez ya da kontrol makinesinin
adresi bilinmiyorsa HİÇBİR ŞEY önerilmez; kontrol makinesinin adresini kapsayan kural silinmez; extra_allow ile aynı olan kural silinmez.
Python 3.9+ (yalnızca stdlib).
"""
import ipaddress
import json
import re
import sys

RULE = re.compile(r"^ufw allow from (\S+) to any port (\d+) proto tcp(?: comment '.*')?$")


def net(text):
    try:
        return ipaddress.ip_network(str(text).strip(), strict=False)
    except ValueError:
        return None


def covers(outer, inner):
    return outer.version == inner.version and inner.subnet_of(outer)


def decide(cfg):
    out = {"stale": [], "blocked": [], "skipped": [], "missing": [], "error": ""}
    keep = []
    for a in cfg.get("allow_from") or []:
        n = net(a)
        if n is None:
            out["error"] = "allow_from içinde çözülemeyen değer: %r (silme yapılmadı)" % (a,)
            return out
        keep.append(n)
    if not keep:
        out["error"] = "allow_from boş (silme yapılmadı)"
        return out
    ctrl = net(cfg.get("controller") or "")
    if ctrl is None:
        out["error"] = "kontrol makinesinin adresi bilinmiyor (silme yapılmadı)"
        return out
    ports = set(str(p) for p in cfg.get("ssh_ports") or [])
    extra = set(str(e).strip() for e in cfg.get("extra_allow") or [])
    seen = set()
    for line in cfg.get("added") or []:
        m = RULE.match(line.strip())
        if not m:
            continue
        src, port = m.groups()
        if port not in ports:
            continue
        n = net(src)
        if n is None:
            out["skipped"].append({"src": src, "port": port, "reason": "kaynak çözülemedi"})
            continue
        if n in keep:
            continue
        if ("from %s to any port %s proto tcp" % (src, port)) in extra:
            continue
        key = (str(n), port)
        if key in seen:
            continue
        seen.add(key)
        item = {"src": src, "port": port}
        if covers(n, ctrl):
            out["blocked"].append(dict(item, reason="kontrol makinesinin adresini kapsıyor"))
        else:
            out["stale"].append(item)
    have = set()
    for line in cfg.get("added") or []:
        m = RULE.match(line.strip())
        if m and net(m.group(1)) is not None:
            have.add((str(net(m.group(1))), m.group(2)))
    for n in keep:
        for p in sorted(ports, key=int):
            if (str(n), p) not in have:
                out["missing"].append({"src": str(n), "port": p})
    out["stale"].sort(key=lambda r: (int(r["port"]), r["src"]))
    out["blocked"].sort(key=lambda r: (int(r["port"]), r["src"]))
    return out


def main(argv):
    try:
        cfg = json.loads(argv[1])
    except (IndexError, ValueError) as exc:
        print(json.dumps({"stale": [], "blocked": [], "skipped": [], "missing": [], "error": "girdi okunamadı: %s" % exc}))
        return 0
    print(json.dumps(decide(cfg), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
