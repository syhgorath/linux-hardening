#!/usr/bin/env python3
"""hardening_pve_keep_banner: pvebanner.service /etc/issue'yu ezer; drop-in yasal uyariyi geri yazar (yalnizca proxmox-host). Gercek Ansible ile."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail[-600:]}")


def run(extra):
    tasks = yaml.safe_load((ROOT / "roles/hardening_base/tasks/main.yml").read_text(encoding="utf-8"))
    keep = [t for t in tasks if "pvebanner" in t.get("name", "")]
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False,
                                       "vars": yaml.safe_load((ROOT / "roles/hardening_base/defaults/main.yml").read_text(encoding="utf-8")), "tasks": [t for t in keep if "ansible.builtin.systemd" not in t]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb), "-e", json.dumps(extra)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


check("varsayilan AcIK", yaml.safe_load((ROOT / "roles/hardening_base/defaults/main.yml").read_text(encoding="utf-8"))["hardening_pve_keep_banner"] is True)
with tempfile.TemporaryDirectory() as d:
    unit = Path(d) / "pvebanner.service"
    unit.write_text("[Service]\n")
    drop = Path(d) / "x.d" / "10.conf"
    base = {"hardening_pve_banner_owner": str(os.getuid()), "hardening_pve_banner_group": str(os.getgid()), "hardening_pve_banner_unit": str(unit), "hardening_pve_banner_dropin": str(drop)}
    rc, out = run({**base, "hardening_platform": "generic"})
    check("generic: yazilmaz", rc == 0 and not drop.exists(), out[-1500:])
    rc, out = run({**base, "hardening_platform": "proxmox-host", "hardening_pve_banner_unit": str(Path(d) / "yok.service")})
    check("birim yoksa yazilmaz", rc == 0 and not drop.exists(), out[-1500:])
    rc, out = run({**base, "hardening_platform": "proxmox-host"})
    txt = drop.read_text() if drop.exists() else ""
    check("proxmox-host: drop-in yazilir", rc == 0 and "ExecStartPost=/usr/bin/install -m 0644 /etc/issue.net /etc/issue" in txt and "[Service]" in txt, out[-1500:])
    rc, out = run({**base, "hardening_platform": "proxmox-host"})
    check("2. kosu changed=0", rc == 0 and "changed=0" in out, out[-1500:])
    rc, out = run({**base, "hardening_platform": "proxmox-host", "hardening_pve_keep_banner": False})
    check("false: drop-in silinir", rc == 0 and not drop.exists(), out[-1500:])
sys.exit(1 if fails else 0)
