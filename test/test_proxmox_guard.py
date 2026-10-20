#!/usr/bin/env python3
"""hardening_preflight: Proxmox VE hostu korumasi. /etc/pve (ya da /usr/bin/pveversion) varsa rol HER DURUMDA durur: `hardening_allow_unsupported=true` bile atlatamaz,
`--check`'te de calisir. Proxmox icin ayri bir bayrak YOKTUR. Gercek `stat` + `fail` gorevleri yerel Ansible ile calistirilir."""
import os
import subprocess
import sys
import tempfile
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


tasks = yaml.safe_load((ROOT / "roles/hardening_preflight/tasks/main.yml").read_text(encoding="utf-8"))
defaults = yaml.safe_load((ROOT / "roles/hardening_preflight/defaults/main.yml").read_text(encoding="utf-8"))
names = [t.get("name") for t in tasks]
stat_t = next(t for t in tasks if t.get("name") == "Look for Proxmox VE markers")
fail_t = next(t for t in tasks if t.get("name") == "Refuse to run on a Proxmox VE host")
os_t = next(t for t in tasks if "ansible.builtin.assert" in t)

check("sira: Proxmox denetimi, OS/surum denetiminden ONCE", names.index("Refuse to run on a Proxmox VE host") < tasks.index(os_t))
check("Proxmox denetimi allow_unsupported'a BAGLI DEGIL (atlatilamaz)", "allow_unsupported" not in str(fail_t.get("when")) and "allow_unsupported" not in str(stat_t.get("when", "")))
check("denetim --check'te de calisir (check_mode: false)", stat_t.get("check_mode") is False)
check("varsayilan isaretler: /etc/pve ve /usr/bin/pveversion", defaults["hardening_proxmox_markers"] == ["/etc/pve", "/usr/bin/pveversion"])
check("Proxmox icin ayri bayrak YOK (hardening_allow_proxmox benzeri)", not any("proxmox" in k.lower() and k != "hardening_proxmox_markers" for k in defaults))
check("OS denetimi hala allow_unsupported ile atlanir (Proxmox disinda davranis degismedi)", "hardening_allow_unsupported" in str(os_t.get("when")))


def play(markers, allow):
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_proxmox_markers": markers, "hardening_allow_unsupported": allow},
                                       "tasks": [stat_t, fail_t, {"ansible.builtin.debug": {"msg": "DEVAM-EDILDI"}}]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


with tempfile.TemporaryDirectory() as t:
    pve = Path(t) / "pve"
    pve.mkdir()
    rc, out = play([str(Path(t) / "yok"), str(Path(t) / "yok2")], False)
    check("Proxmox isareti YOK: devam eder", rc == 0 and "DEVAM-EDILDI" in out)
    rc, out = play([str(pve)], False)
    check("isaret VAR: rol DURUR ve hangi isaretin bulundugunu soyler", rc != 0 and "Proxmox VE hostu" in out and str(pve) in out and "DEVAM-EDILDI" not in out)
    rc, out = play([str(pve)], True)
    check("hardening_allow_unsupported=true ILE BILE DURUR", rc != 0 and "Proxmox VE hostu" in out and "DEVAM-EDILDI" not in out)
    f = Path(t) / "pveversion"
    f.write_text("x")
    rc, out = play([str(Path(t) / "yok"), str(f)], False)
    check("ikinci isaret (pveversion dosyasi) de yeterli", rc != 0 and "Proxmox VE hostu" in out)
sys.exit(1 if fails else 0)
