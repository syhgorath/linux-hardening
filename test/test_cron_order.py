#!/usr/bin/env python3
"""cron kurulumu hardening_files'tan ÖNCE: minimal imajda (cron yok) AIDE onu sonradan getirdiği için cron izinleri (CIS bölüm 2.4) ilk koşuda sıkılaşmıyor, ikinci koşuda sıkılaşıyordu
(verification-log 45). Yapısal: kurulum hardening_base'te, base harden.yml'de files'tan önce, files hedefleri cron yollarını içerir."""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
fails = 0


def check(name, ok):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}")


base = yaml.safe_load((ROOT / "roles/hardening_base/tasks/main.yml").read_text(encoding="utf-8"))
t = next((x for x in base if str(x.get("name", "")).startswith("Install cron")), None)
check("hardening_base cron kurar (apt, state: present)", bool(t) and t["ansible.builtin.apt"] == {"name": "cron", "state": "present"})
check("kurulum kosulsuz (Proxmox dahil: cron zaten kurulu, degisiklik yok)", bool(t) and "when" not in t)
pb = yaml.safe_load((ROOT / "playbooks/harden.yml").read_text(encoding="utf-8"))[0]
roles = [r if isinstance(r, str) else r["role"] for r in pb["roles"]]
check("sira: hardening_base, hardening_files'tan ONCE", roles.index("hardening_base") < roles.index("hardening_files"))
check("sira: hardening_files, hardening_aide'den ONCE (aide cron'u zaten getiriyordu)", roles.index("hardening_files") < roles.index("hardening_aide"))
fd = yaml.safe_load((ROOT / "roles/hardening_files/defaults/main.yml").read_text(encoding="utf-8"))
paths = {x["path"] for x in fd["hardening_files_targets"]}
check("files hedefleri cron yollarini icerir", {"/etc/crontab", "/etc/cron.d", "/etc/cron.hourly"} <= paths)
print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
