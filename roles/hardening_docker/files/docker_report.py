#!/usr/bin/env python3
"""Docker sunucusu raporu (SALT OKUNUR; hiçbir şeyi değiştirmez, yalnızca karar verir).

Girdi (argv[1], JSON): group_members (docker grubunun üyeleri), ports (`docker ps --format '{{.Names}}|{{.Ports}}'` satırları), listening (`ss -lnt` yerel adresleri,
örn. "0.0.0.0:2375"), daemon_text (daemon.json METNİ; boş olabilir) ya da daemon (çözülmüş nesne), daemon_error (okunamadıysa metin), allowed_published (izinli yayınlanan portlar).
Çıktı (stdout, JSON): status (ok|warn|unknown), warnings, notes, published (kontrolsüz yayınlanan "konteyner:port" listesi), error.

Neden: Docker yayınladığı portu ufw'den ÖNCE açar (docs/known-issues.md); ufw'de izin yokken bile dışarıdan erişilebilir. docker grubunun üyeleri kök eşdeğeridir.
Python 3.9+ (yalnızca stdlib).
"""
import json
import sys

LOOPBACK = ("127.0.0.1", "::1", "[::1]", "localhost")


def parse_ports(text):
    """'0.0.0.0:80->80/tcp, :::80->80/tcp, 127.0.0.1:8080->80/tcp, 443/tcp' -> [(ip, [portlar], proto)] (yalnızca yayınlananlar)."""
    out = []
    for item in [p.strip() for p in str(text).split(",") if p.strip()]:
        if "->" not in item:
            continue  # yayınlanmamış (yalnızca EXPOSE)
        left, right = item.split("->", 1)
        proto = right.rsplit("/", 1)[-1]
        if left.startswith("["):
            ip, _, hp = left.rpartition("]:")
            ip = ip + "]"
        elif left.startswith(":::"):
            ip, hp = "::", left[3:]
        elif ":" in left:
            ip, _, hp = left.rpartition(":")
        else:
            ip, hp = "", left
        if "-" in hp:
            a, b = hp.split("-", 1)
            ports = list(range(int(a), int(b) + 1)) if a.isdigit() and b.isdigit() and int(b) - int(a) < 1000 else []
        else:
            ports = [int(hp)] if hp.isdigit() else []
        out.append((ip, ports, proto))
    return out


def is_public(ip):
    return ip in ("", "0.0.0.0", "::", ":::", "[::]")


def decide(cfg):
    res = {"status": "ok", "warnings": [], "notes": [], "published": [], "error": ""}
    try:
        allowed = set(int(p) for p in cfg.get("allowed_published") or [])
    except (TypeError, ValueError):
        res.update(status="unknown", error="allowed_published sayı listesi olmalı")
        return res
    members = [m for m in (cfg.get("group_members") or []) if m]
    if members:
        res["warnings"].append("docker grubunun üyeleri (%s) kök eşdeğeridir: bu hesaplar sunucuda sınırsız yetkiye sahiptir (CIS Docker 1.1.2)." % ", ".join(members))
    seen = set()
    for line in cfg.get("ports") or []:
        name, _, ports = str(line).partition("|")
        for ip, plist, proto in parse_ports(ports):
            if not is_public(ip):
                continue
            for p in plist:
                if p in allowed or (name, p, proto) in seen:
                    continue
                seen.add((name, p, proto))
                res["published"].append("%s:%d/%s" % (name or "?", p, proto))
    if res["published"]:
        res["warnings"].append("Her arayüze yayınlanan ve izinli listede olmayan portlar var: %s. Docker bunları ufw'yi ATLAYARAK açar; yalnızca gerekli olanı yayınlayın "
                               "ya da belirli bir adrese bağlayın (örn. 127.0.0.1:8080:80)." % ", ".join(sorted(res["published"])))
    for addr in cfg.get("listening") or []:
        host, _, port = str(addr).rpartition(":")
        if port == "2375" and host not in LOOPBACK:
            res["warnings"].append("Docker TCP API 2375 (TLS'siz) %s adresinde dinliyor: bu kök eşdeğeri uzak erişimdir (CIS Docker 2.8)." % host)
        elif port == "2376" and host not in LOOPBACK:
            res["notes"].append("Docker TCP API 2376 (TLS) %s adresinde dinliyor; istemci sertifikası zorunlu olmalı." % host)
    daemon = cfg.get("daemon")
    if "daemon_text" in cfg:
        text = str(cfg.get("daemon_text") or "").strip()
        if text:
            try:
                daemon = json.loads(text)
            except ValueError as exc:
                res["warnings"].append("daemon.json geçerli JSON değil (%s): Docker bu dosyayla BAŞLAMAZ." % exc)
                daemon = None
            else:
                if not isinstance(daemon, dict):
                    res["warnings"].append("daemon.json bir JSON nesnesi değil: Docker bu dosyayla BAŞLAMAZ.")
                    daemon = None
    if cfg.get("daemon_error"):
        res["notes"].append("daemon.json okunamadı: %s" % cfg["daemon_error"])
    elif isinstance(daemon, dict):
        if daemon.get("iptables") is False:
            res["warnings"].append("daemon.json 'iptables': false: Docker ağı (NAT) bozulur; CIS Docker 2.4 buna karşıdır.")
        if daemon.get("experimental") is True:
            res["warnings"].append("daemon.json 'experimental': true: üretimde önerilmez (CIS Docker 2.19).")
        if daemon.get("insecure-registries"):
            res["warnings"].append("daemon.json 'insecure-registries' dolu (%s): TLS'siz kayıt defteri (CIS Docker 2.5)." % ", ".join(map(str, daemon["insecure-registries"])))
        if any(str(h).startswith("tcp://") for h in daemon.get("hosts") or []):
            res["warnings"].append("daemon.json 'hosts' içinde tcp:// var: uzak API açık (CIS Docker 2.8).")
        if not daemon.get("live-restore"):
            res["notes"].append("'live-restore' kapalı: Docker yeniden başlayınca konteynerler durur (CIS Docker 2.16).")
        if not (daemon.get("log-opts") or {}).get("max-size"):
            res["notes"].append("Günlük boyutu sınırı (log-opts max-size) yok: konteyner günlükleri diski doldurabilir.")
    else:
        res["notes"].append("daemon.json yok ya da boş: Docker varsayılanları kullanılıyor.")
    if res["warnings"]:
        res["status"] = "warn"
    return res


def main(argv):
    try:
        cfg = json.loads(argv[1])
        if not isinstance(cfg, dict):
            raise ValueError("nesne değil")
    except (IndexError, ValueError) as exc:
        print(json.dumps({"status": "unknown", "warnings": [], "notes": [], "published": [], "error": "girdi okunamadı: %s" % exc}))
        return 0
    print(json.dumps(decide(cfg), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
