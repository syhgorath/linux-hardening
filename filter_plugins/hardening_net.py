# Ağ yardımcıları. Çağıran görev hata olursa bilgi satırını atlar (yalnız gösterim).
from __future__ import annotations

import ipaddress
import re

LOOPBACK = ["127.0.0.1/8", "::1"]


def hardening_ip_in_list(address, entries):
    """address, boşlukla ayrılmış entries içindeki bir adres ya da CIDR'ye uyuyorsa True. Çözülemeyen girdi (ad, aralık, dosya) yok sayılır."""
    try:
        ip = ipaddress.ip_address(str(address).strip().split("%")[0])
    except ValueError:
        return False
    for entry in str(entries or "").split():
        try:
            if ip in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def hardening_ignoreip_effective(extra):
    """fail2ban ignoreip: yerel adresler HER ZAMAN başta, ardından kullanıcının adresleri (boşluk ya da virgülle ayrılmış, tekrarsız)."""
    out = list(LOOPBACK)
    for token in re.split(r"[\s,]+", str(extra or "")):
        if token and token not in out:
            out.append(token)
    return " ".join(out)


class FilterModule:
    def filters(self):
        return {"hardening_ip_in_list": hardening_ip_in_list, "hardening_ignoreip_effective": hardening_ignoreip_effective}
