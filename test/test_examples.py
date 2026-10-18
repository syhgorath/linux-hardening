#!/usr/bin/env python3
"""examples/: üç sunucu örneği tutarlı kalmalı.

Denetlenenler: (1) gerçek `ansible-inventory` her sunucu için group_vars'ı yükleyip birleştirir ve sonuç, sshpocket'e verilen `examples/sshpocket/<sunucu>.yml`
ile AYNI olur (iki kopya birbirinden kaymaz); (2) kullanılan her değişken gerçekten var; (3) ek ufw kuralları rolün doğrulama kalıbına uyar;
(4) sshpocket dosyalarında yalnızca component.yml'in gördüğü değişkenler var (yoksa sshpocket onları geçirmez).
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"
fails = 0


def check(name, want, got):
    global fails
    if want == got:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}: beklenen={want!r} gercek={got!r}")


r = subprocess.run(["ansible-inventory", "-i", str(EX / "inventory.example.yml"), "--list"], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                   env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
check("ansible-inventory ornegi okur", 0, r.returncode)
inv = json.loads(r.stdout)
hostvars = inv["_meta"]["hostvars"]
check("uc sunucu da 'hardening' ust grubunda (harden.yml secer)", {"server1", "server2", "server3"}, set(inv["hardening"].get("hosts", [])) | {h for g in inv["hardening"].get("children", []) for h in inv[g].get("hosts", [])})

pairs = {"server1": "server1-web.yml", "server2": "server2-docker.yml", "server3": "server3-infra.yml"}
roles_defaults = {}
for p in (ROOT / "roles").glob("*/defaults/main.yml"):
    roles_defaults.update(yaml.safe_load(p.read_text(encoding="utf-8")) or {})
comp = yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))
comp_vars = {v["name"] for v in comp["vars"] if isinstance(v, dict)}
pattern = re.compile(roles_defaults["hardening_ufw_extra_allow_pattern"])

for host, fname in pairs.items():
    hv = {k: v for k, v in hostvars[host].items() if k.startswith("hardening_")}
    sp = yaml.safe_load((EX / "sshpocket" / fname).read_text(encoding="utf-8"))
    check(f"{host}: group_vars birlesimi (ansible-inventory) == sshpocket/{fname}", sp, hv)
    check(f"{host}: kullanilan tum degiskenler var olan hardening_* degiskenleri", [], [k for k in hv if k not in roles_defaults])
    check(f"{host}: sshpocket dosyasinda yalniz component.yml'in gordugu degiskenler", [], [k for k in sp if k not in comp_vars])
    bad = [x for x in hv.get("hardening_ufw_extra_allow", []) if not pattern.match(x)]
    check(f"{host}: ek ufw kurallari dogrulama kalibina uyar", [], bad)
    check(f"{host}: hardening_ssh_allow_from dolu (yoksa ufw/ssh durur)", True, bool(hv.get("hardening_ssh_allow_from")))

# anlamsal: tasarım kararları örnekte korunuyor
s1, s2, s3 = (hostvars[h] for h in ("server1", "server2", "server3"))
check("server1: veritabani portu (3306/5432) HICBIR kuralda yok", True, not any(re.search(r"port (3306|5432)\b|^(3306|5432)", x) for x in s1.get("hardening_ufw_extra_allow", [])))
check("server1: 80 yalniz ters vekilin adresinden (kaynak kisitli)", True, all(x.startswith("from ") for x in s1["hardening_ufw_extra_allow"]))
check("server2: routed deny KAPALI (Docker yonlendirmesi)", False, s2["hardening_ufw_routed_deny"])
check("server3: Redis yalniz server1 ve server2'den (kaynak kisitli, 'any' yok)", True, all(x.startswith("from 192.168.1.") for x in s3["hardening_ufw_extra_allow"]) and not any(" any port" in x.replace("to any port", "") for x in s3["hardening_ufw_extra_allow"]))
check("hicbir ornekte SSH portu (22) extra_allow ile acilmaz (SSH allow_from'dan gelir)", True, not any(re.search(r"\b22\b", x) for h in (s1, s2, s3) for x in h.get("hardening_ufw_extra_allow", [])))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
