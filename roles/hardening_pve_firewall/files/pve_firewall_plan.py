#!/usr/bin/env python3
"""Proxmox VE güvenlik duvarı (datacenter `cluster.fw`) planı: YALNIZCA karar verir, hiçbir şeyi yazmaz.

Girdi (argv[1], JSON): clustered (bool), allow_from (liste: ağ/CIDR), client_ip (kontrol makinesinin sunucuya görünen adresi), existing (str ya da null:
mevcut cluster.fw içeriği; dosya yoksa null), extra_ports (liste: "443/tcp", "8000:8010/udp"), ssh_port (int, varsayılan 22), web_port (int, varsayılan 8006).
Çıktı (stdout, JSON): status (apply|noop|refuse), reasons (liste), content (enable: 1 ile tam dosya), content_disabled (aynı dosya, enable: 0), error.

Güvenlik: küme, boş/geçersiz allow_from, kontrol makinesini kapsamayan allow_from ve kullanıcının kendi cluster.fw dosyası (işaretimiz yok) durumlarında HİÇBİR ŞEY yazılmaz
(status refuse). Python 3.9+ (yalnızca stdlib). Tasarım: docs/design/proxmox-firewall.md."""
import ipaddress
import json
import re
import sys

MARKER = "# hardening-managed: linux-hardening pve_firewall (elle degistirmeyin)"
PORT_RE = re.compile(r"^([0-9]{1,5})(?::([0-9]{1,5}))?/(tcp|udp)$")


def valid_port(p):
    return 1 <= p <= 65535


def build(allow_nets, extra, ssh_port, web_port, enable):
    # Proxmox, `management` kümesine düğümün otomatik algıladığı yerel ağı (alias local_network) HER ZAMAN ekler; alias'ı biz tanımlarsak yalnızca bizim ağımız kalır
    # (iç içe Proxmox 9.2'de görüldü). Alias tek bir CIDR alır: IPv4 ağlar öne alınır.
    alias_net = sorted(allow_nets, key=lambda n: (n.version, str(n)))[0]
    lines = [MARKER, "[OPTIONS]", "enable: %d" % enable, "policy_in: DROP", "policy_out: ACCEPT", "", "[ALIASES]", "local_network %s" % alias_net, "", "[IPSET management]"]
    lines += [str(n) for n in allow_nets]
    lines += ["", "[RULES]",
              "IN ACCEPT -p tcp -dport %d -source +management" % ssh_port,
              "IN ACCEPT -p tcp -dport %d -source +management" % web_port,
              "IN ACCEPT -p icmp -source +management"]
    for proto_port in extra:
        port, proto = proto_port.split("/")
        lines.append("IN ACCEPT -p %s -dport %s -source +management" % (proto, port))
    return "\n".join(lines) + "\n"


def user_owned(existing):
    """Kendi işaretimiz yoksa ve yorum/boş satır dışında içerik varsa dosya kullanıcıya aittir."""
    if existing is None or MARKER in existing:
        return False
    return any(l.strip() and not l.strip().startswith("#") for l in existing.splitlines())


def decide(cfg):
    res = {"status": "apply", "reasons": [], "content": "", "content_disabled": "", "error": ""}

    def refuse(why):
        res["status"] = "refuse"
        res["reasons"].append(why)

    if cfg.get("clustered"):
        refuse("Küme düğümü: bu rol yalnızca TEK düğümde çalışır (datacenter kuralları tüm düğümleri etkiler).")
    allow = cfg.get("allow_from")
    if not isinstance(allow, list) or not allow:
        refuse("hardening_ssh_allow_from boş: güvenlik duvarı yönetim ağı olmadan açılırsa sunucu kilitlenir.")
        allow = []
    nets = []
    for a in allow:
        try:
            nets.append(ipaddress.ip_network(str(a), strict=False))
        except ValueError:
            refuse("hardening_ssh_allow_from içinde geçersiz ağ: %r." % (str(a)[:60],))
    try:
        client = ipaddress.ip_address(str(cfg.get("client_ip", "")))
        if nets and not any(client in n for n in nets if n.version == client.version):
            refuse("Kontrol makinesinin adresi (%s) hardening_ssh_allow_from içinde değil: güvenlik duvarı bu bağlantıyı keserdi." % client)
    except ValueError:
        refuse("Kontrol makinesinin adresi okunamadı (SSH dışı bağlantı?): erişimin korunduğu doğrulanamadı.")
    extra = []
    for e in cfg.get("extra_ports") or []:
        m = PORT_RE.match(str(e))
        if not m or not valid_port(int(m.group(1))) or (m.group(2) and (not valid_port(int(m.group(2))) or int(m.group(2)) < int(m.group(1)))):
            refuse("Geçersiz ek port: %r (biçim: 443/tcp ya da 8000:8010/udp)." % (str(e)[:40],))
        else:
            extra.append(str(e))
    try:
        ssh_port, web_port = int(cfg.get("ssh_port", 22)), int(cfg.get("web_port", 8006))
        if not (valid_port(ssh_port) and valid_port(web_port)):
            raise ValueError
    except (TypeError, ValueError):
        refuse("ssh_port/web_port geçersiz.")
        ssh_port, web_port = 22, 8006
    existing = cfg.get("existing")
    if user_owned(existing):
        refuse("/etc/pve/firewall/cluster.fw kullanıcıya ait kurallar içeriyor (bu rolün işareti yok): DOKUNULMADI. Kendi kurallarınıza yönetim ağı kuralını elle ekleyin.")
    if res["status"] == "refuse":
        return res
    res["content"] = build(nets, extra, ssh_port, web_port, 1)
    res["content_disabled"] = build(nets, extra, ssh_port, web_port, 0)
    if existing is not None and existing.rstrip("\n") == res["content"].rstrip("\n"):
        res["status"] = "noop"
        res["reasons"].append("cluster.fw zaten istenen içerikte.")
    return res


def main(argv):
    try:
        cfg = json.loads(argv[1])
        if not isinstance(cfg, dict):
            raise ValueError("nesne değil")
    except (IndexError, ValueError) as exc:
        print(json.dumps({"status": "refuse", "reasons": [], "content": "", "content_disabled": "", "error": "girdi okunamadı: %s" % exc}))
        return 0
    print(json.dumps(decide(cfg), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
