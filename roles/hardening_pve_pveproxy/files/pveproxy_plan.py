#!/usr/bin/env python3
"""Proxmox VE web arayüzü (pveproxy) erişim sınırı planı: YALNIZCA karar verir, hiçbir şeyi yazmaz.

Girdi (argv[1], JSON): allow_from (liste: IP/CIDR), client_ip (kontrol makinesinin sunucuya görünen adresi), existing (str ya da null: /etc/default/pveproxy içeriği),
remove (bool, varsayılan false: true ise bu rolün bloğu kaldırılır, diğer girdiler yok sayılır).
Çıktı (stdout, JSON): status (apply|noop|refuse), reasons (liste), allow_value ("a,b,..." ALLOW_FROM değeri), content (dosyanın TAMAM yeni içeriği), error.

Güvenlik: boş/geçersiz allow_from, kontrol makinesini kapsamayan allow_from ve bu rolün işareti dışında kullanıcının kendi ALLOW_FROM/DENY_FROM/POLICY satırları
durumunda HİÇBİR ŞEY yazılmaz (status refuse). Yerel döngü (127.0.0.0/8, ::1) her zaman eklenir. Python 3.9+ (yalnızca stdlib). Tasarım: docs/design/proxmox-host.md."""
import ipaddress
import json
import re
import sys

BEGIN = "# BEGIN linux-hardening pveproxy (elle degistirmeyin)"
END = "# END linux-hardening pveproxy"
KEY_RE = re.compile(r"^\s*(ALLOW_FROM|DENY_FROM|POLICY)\s*=", re.M)
LOOPBACK = ["127.0.0.0/8", "::1/128"]


def managed_block(allow_value):
    return "\n".join([BEGIN, 'DENY_FROM="all"', 'ALLOW_FROM="%s"' % allow_value, 'POLICY="allow"', END]) + "\n"


def strip_block(text):
    """Bu rolün bloğunu çıkarır; kalan (kullanıcının) içeriği döndürür."""
    return re.sub(r"(?s)%s.*?%s\n?" % (re.escape(BEGIN), re.escape(END)), "", text)


def decide(cfg):
    res = {"status": "apply", "reasons": [], "allow_value": "", "content": "", "error": ""}
    if cfg.get("remove"):
        existing = cfg.get("existing")
        if existing is None or BEGIN not in existing:
            res["status"] = "noop"
            res["reasons"].append("Bu rolün bloğu yok: kaldırılacak bir şey yok.")
        else:
            res["content"] = strip_block(existing)
        return res

    def refuse(why):
        res["status"] = "refuse"
        res["reasons"].append(why)

    allow = cfg.get("allow_from")
    nets = []
    if not isinstance(allow, list) or not allow:
        refuse("hardening_pve_pveproxy_allow_from boş: pveproxy erişim sınırı ağ listesi olmadan açılırsa web arayüzü kilitlenir.")
        allow = []
    for a in allow:
        s = str(a).strip()
        if s.lower() == "all" or "," in s or " " in s:
            refuse("hardening_pve_pveproxy_allow_from içinde geçersiz girdi: %r (yalnızca tek tek IP ya da CIDR)." % (s[:60],))
            continue
        try:
            nets.append(ipaddress.ip_network(s, strict=False))
        except ValueError:
            refuse("hardening_pve_pveproxy_allow_from içinde geçersiz ağ: %r." % (s[:60],))
    try:
        client = ipaddress.ip_address(str(cfg.get("client_ip", "")))
        if nets and not any(client in n for n in nets if n.version == client.version):
            refuse("Kontrol makinesinin adresi (%s) hardening_pve_pveproxy_allow_from içinde değil: web arayüzü bu bağlantıya kapanırdı." % client)
    except ValueError:
        refuse("Kontrol makinesinin adresi okunamadı (SSH dışı bağlantı?): erişimin korunduğu doğrulanamadı.")
    existing = cfg.get("existing")
    if existing is not None:
        outside = strip_block(existing)
        if KEY_RE.search(outside):
            refuse("/etc/default/pveproxy bu rolün bloğu dışında ALLOW_FROM/DENY_FROM/POLICY satırları içeriyor: DOKUNULMADI. Önce bunları kaldırın ya da elle birleştirin.")
    if res["status"] == "refuse":
        return res
    values = [str(n) for n in nets] + [n for n in LOOPBACK if n not in {str(x) for x in nets}]
    res["allow_value"] = ",".join(values)
    block = managed_block(res["allow_value"])
    base = strip_block(existing) if existing is not None else ""
    if base and not base.endswith("\n"):
        base += "\n"
    res["content"] = base + block
    if existing is not None and res["content"] == existing:
        res["status"] = "noop"
        res["reasons"].append("/etc/default/pveproxy zaten istenen içerikte.")
    return res


def main(argv):
    try:
        cfg = json.loads(argv[1])
        if not isinstance(cfg, dict):
            raise ValueError("nesne değil")
    except (IndexError, ValueError) as exc:
        print(json.dumps({"status": "refuse", "reasons": [], "allow_value": "", "content": "", "error": "girdi okunamadı: %s" % exc}))
        return 0
    print(json.dumps(decide(cfg), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
