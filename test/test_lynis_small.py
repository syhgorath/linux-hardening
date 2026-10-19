#!/usr/bin/env python3
"""Lynis'ten çıkan küçük maddeler: libpam-tmpdir (DEB-0280) ve üç ek sysctl (KRNL-6000).

Şablon çıktısı test_templates.py'de (golden); burada: varsayılanlar AÇIK ama kendi değişkenleriyle kapanır, libpam-tmpdir görevi gerçek `when` ifadesiyle denenir,
component.yml'de değişkenler var ve `warn_if` YOK (varsayılan zaten true; #74 hatasının tekrarı olmasın).
"""
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


kd = load("roles/hardening_kernel/defaults/main.yml")
ad = load("roles/hardening_auth/defaults/main.yml")
check("varsayilan: ek sysctl ACIK", True, kd["hardening_kernel_extra_sysctl"])
check("varsayilan: libpam-tmpdir ACIK", True, ad["hardening_pam_tmpdir"])
tpl = (ROOT / "roles/hardening_kernel/templates/sysctl.conf.j2").read_text(encoding="utf-8")
check("sysctl: üç satir yalniz hardening_kernel_extra_sysctl blogunda", True, "{% if hardening_kernel_extra_sysctl %}" in tpl and tpl.index("fs.protected_fifos") > tpl.index("{% if hardening_kernel_extra_sysctl %}"))
check("sysctl: ip_forward ve kernel.modules_disabled'a DOKUNULMAZ (modules_disabled yeniden baslatmaya dek geri alinamaz)", True, "modules_disabled" not in tpl and "ip_forward =" not in tpl)

tasks = load("roles/hardening_auth/tasks/main.yml")
t = next(x for x in tasks if x.get("name") == "Install libpam-tmpdir")
check("libpam-tmpdir: apt, state present (kaldirma yok), paket adi dogru", ("libpam-tmpdir", "present"), (t["ansible.builtin.apt"]["name"], t["ansible.builtin.apt"]["state"]))


def probe(value):
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_pam_tmpdir": value},
                                       "tasks": [{"name": "probe", "ansible.builtin.debug": {"msg": "calisti"}, "when": t["when"]}]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return "calisti" in r.stdout


check("libpam-tmpdir: hardening_pam_tmpdir=true iken calisir", True, probe(True))
check("libpam-tmpdir: hardening_pam_tmpdir=false iken ATLANIR", False, probe(False))

comp = load("component.yml")
byname = {v["name"]: v for v in comp["vars"] if isinstance(v, dict)}
for n in ("hardening_kernel_extra_sysctl", "hardening_pam_tmpdir"):
    v = byname.get(n)
    check(f"component.yml: {n} bool, varsayilan true", True, bool(v) and v["type"] == "bool" and v["default"] is True)
    check(f"component.yml: {n} warn_if YOK (varsayilan true; #74)", False, bool(v) and "warn_if" in v)

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
