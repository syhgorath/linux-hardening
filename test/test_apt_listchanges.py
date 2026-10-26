#!/usr/bin/env python3
"""apt-listchanges: kurulum + yükseltmeyi ASLA bloklamayan ayar. apt-listbugs Ubuntu'da YOK (eklenmez).

Asıl risk: etkileşimli onay isteyen bir ayarın unattended-upgrades / Ansible `apt` çalışmasını kilitlemesi. Bu yüzden `confirm=false`, e-posta yok ve `frontend`
bloklayan bir arayüz (pager/browser/gtk/xterm-pager) OLMAMALI. Ayar dosyasının içeriği gerçek `copy` modülüyle geçici bir dosyaya yazılıp ayrıştırılır.
"""
import configparser
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
fails = 0


def check(name, want, got):
    global fails
    if want == got:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}: beklenen={want!r} gercek={got!r}")


def load(p):
    return yaml.safe_load((ROOT / p).read_text(encoding="utf-8"))


tasks = load("roles/hardening_base/tasks/main.yml")
by = {t.get("name"): t for t in tasks}
inst = by["Install apt-listchanges"]
conf = by["Configure apt-listchanges (never prompts, no mail)"]
check("varsayilan: apt-listchanges ACIK", True, load("roles/hardening_base/defaults/main.yml")["hardening_apt_listchanges"])
check("kurulum: apt, present (kaldirma yok), paket adi dogru", ("apt-listchanges", "present"), (inst["ansible.builtin.apt"]["name"], inst["ansible.builtin.apt"]["state"]))
check("iki gorev de kendi degiskeniyle kapanir", True, "hardening_apt_listchanges" in str(inst["when"]) and "hardening_apt_listchanges" in str(conf["when"]))
_tasks = yaml.safe_load((ROOT / "roles/hardening_base/tasks/main.yml").read_text(encoding="utf-8"))
_lb = next((t for t in _tasks if isinstance(t, dict) and t.get("name") == "Install apt-listbugs (never blocks apt)"), {})
_outside = [t for t in _tasks if isinstance(t, dict) and t is not _lb and "apt-listbugs" in str(t.get("ansible.builtin.apt", ""))]
check("apt-listbugs yalniz Debian'a ozgu opt-in blokta (Ubuntu depolarinda yok); baska hicbir apt gorevinde YOK", True, bool(_lb) and "== 'Debian'" in str(_lb.get("when")) and "hardening_apt_listbugs" in str(_lb.get("when")) and not _outside)

with tempfile.TemporaryDirectory() as d:
    cp = dict(conf["ansible.builtin.copy"]); cp["dest"] = f"{d}/listchanges.conf"; cp.pop("owner"); cp.pop("group")
    pb = Path(d) / "p.yml"
    pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_apt_listchanges": True},
                                   "tasks": [{"ansible.builtin.copy": cp, "when": conf["when"]}]}]), encoding="utf-8")
    r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    check("ayar dosyasi yazildi", 0, r.returncode)
    c = configparser.ConfigParser()
    c.read(f"{d}/listchanges.conf", encoding="utf-8")
    a = c["apt"]
    check("confirm=false: ONAY ISTEMEZ (unattended-upgrades/Ansible kilitlenmez)", "false", a.get("confirm"))
    check("frontend bloklamayan 'text' (pager/browser/gtk/xterm-pager DEGIL)", "text", a.get("frontend"))
    check("e-posta/mail frontend'i YOK", False, "email_address" in a or a.get("frontend") == "mail")
    check("which=both (haber ve changelog)", "both", a.get("which"))
    r2 = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                        env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    check("ikinci kosu changed=0 (idempotent)", True, "changed=0" in r2.stdout)

comp = load("component.yml")
v = next((x for x in comp["vars"] if isinstance(x, dict) and x["name"] == "hardening_apt_listchanges"), None)
check("component.yml: bool, varsayilan true, warn_if YOK (#74)", True, bool(v) and v["type"] == "bool" and v["default"] is True and "warn_if" not in v)

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
