#!/usr/bin/env python3
"""hardening_pve_apt_hold: Proxmox'ta `apt-get upgrade` pve paketlerini de yukseltir; hold (varsayilan KAPALI) bunlari yukseltmeden ONCE tutar.
`dpkg_selections` Mac/CI'da gercek dpkg olmadan calismaz: gorevin gercek `when`/`loop` ifadeleri debug gorevine tasinip gercek Ansible ile degerlendirilir."""
import json
import os
import subprocess
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
        print(f"  FAIL {name} {detail[-500:]}")


tasks = yaml.safe_load((ROOT / "roles/hardening_base/tasks/main.yml").read_text(encoding="utf-8"))
names = [t.get("name", "") for t in tasks]
by = {t.get("name"): t for t in tasks}
defaults = yaml.safe_load((ROOT / "roles/hardening_base/defaults/main.yml").read_text(encoding="utf-8"))
find, hold, note = by["Find the installed Proxmox packages to hold"], by["Hold the Proxmox packages (apt-mark hold)"], by["Note that apt upgrade also upgrades the Proxmox packages"]

check("varsayilan KAPALI ve liste cekirdek pve bilesenlerini icerir", defaults["hardening_pve_apt_hold"] is False and {"proxmox-ve", "pve-manager", "qemu-server", "pve-container"} <= set(defaults["hardening_pve_apt_hold_packages"]))
check("cekirdek paketleri (proxmox-kernel-*) varsayilan listede YOK", not any("kernel" in p for p in defaults["hardening_pve_apt_hold_packages"]))
up = [i for i, n in enumerate(names) if n.startswith("Upgrade the installed packages")]
check("hold gorevleri yukseltme gorevlerinden ONCE", up and names.index(hold["name"]) < min(up) and names.index(find["name"]) < names.index(hold["name"]), str(names))
check("dpkg-query gorevi --check'te de calisir ve degisiklik saymaz", find.get("check_mode") is False and find.get("changed_when") is False and find.get("failed_when") is False)
check("dpkg-query kurulu olmayan paketten dusmez ve listeyi komuta verir", "hardening_pve_apt_hold_packages" in str(find["ansible.builtin.command"]["argv"]) and find["failed_when"] is False)


def play(extra, installed=None):
    """hold gorevinin loop/when'i + not gorevinin when'i debug olarak degerlendirilir; cikti: (tutulacaklar, not var mi)"""
    dbg = [{"ansible.builtin.debug": {"msg": "HOLD={{ item }}"}, "loop": hold["loop"], "when": hold["when"]},
           {"ansible.builtin.debug": {"msg": "NOTE_VAR"}, "when": note["when"]}]
    v = {**defaults, "hardening_pve_apt_hold_installed": {"stdout_lines": installed or []}, **extra}
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": v, "tasks": dbg}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    return sorted(x.split("HOLD=")[1].split('"')[0] for x in out.split("\n") if "HOLD=" in x), "NOTE_VAR" in out


DPKG = ["install ok installed|pve-manager", "install ok installed|proxmox-ve", "deinstall ok config-files|pve-ha-manager", "unknown ok not-installed|qemu-server", "install ok installed|pve-cluster"]
PVE = {"hardening_platform": "proxmox-host"}
held, n = play({**PVE, "hardening_pve_apt_hold": True}, DPKG)
check("proxmox-host + hold: yalniz KURULU ('install ok installed') paketler tutulur", held == ["proxmox-ve", "pve-cluster", "pve-manager"], str(held))
held, n = play({**PVE, "hardening_pve_apt_hold": False}, DPKG)
check("hold KAPALI: hicbir sey tutulmaz", held == [])
held, n = play({"hardening_platform": "generic", "hardening_pve_apt_hold": True}, DPKG)
check("generic platform: hold istense bile tutulmaz", held == [])
held, n = play({"hardening_pve_apt_hold": True}, DPKG)
check("platform tanimsiz: tutulmaz", held == [])
_, n1 = play({**PVE, "hardening_apt_upgrade": True, "hardening_pve_apt_hold": False})
_, n2 = play({**PVE, "hardening_apt_upgrade": True, "hardening_pve_apt_hold": True})
_, n3 = play({**PVE, "hardening_apt_upgrade": False})
_, n4 = play({"hardening_platform": "generic", "hardening_apt_upgrade": True})
check("NOT: yalniz proxmox-host + apt_upgrade acik + hold kapali", n1 and not n2 and not n3 and not n4, f"{n1} {n2} {n3} {n4}")
cv = {v["name"]: v for v in yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))["vars"]}
check("component.yml: hold KAPALI, yalniz proxmox-host", cv["hardening_pve_apt_hold"]["default"] is False and cv["hardening_pve_apt_hold"]["platforms"] == ["proxmox-host"] and cv["hardening_pve_apt_hold_packages"]["platforms"] == ["proxmox-host"])

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
raise SystemExit(1 if fails else 0)
