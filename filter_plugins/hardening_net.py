# Ağ yardımcıları. Çağıran görev hata olursa bilgi satırını atlar (yalnız gösterim).
from __future__ import annotations

import ipaddress


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


class FilterModule:
    def filters(self):
        return {"hardening_ip_in_list": hardening_ip_in_list}
