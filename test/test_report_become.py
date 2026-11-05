#!/usr/bin/env python3
"""hardening_report: ayricalikli okumalar (become/sudo) basarisiz olunca rapor ANLASILMAZ bir sablon hatasiyla dusmez; atlanir ve nedeni soylenir.
Gercekte (SSH, sudo parola ister) `failed_when: false` kayitlarinda `stdout_lines` OLMAZ (yalniz module_stdout); bu, yerel baglantida uretilemez, bu yuzden kayit bicimi
SIMULE edilir ve rolun gercek koruma gorevleri gercek Ansible ile calistirilir. Sonra degerlendirme/ayristirma/uyari gorevlerinin hepsinin ayni kosula bagli oldugu denetlenir."""
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
        print(f"  FAIL {name} {detail}")


inner = yaml.safe_load((ROOT / "roles/hardening_report/tasks/main.yml").read_text(encoding="utf-8"))[0]["block"]
by = {t["name"]: t for t in inner}
guard = [by["Check that the privileged report reads worked"], by["Skip the system report when the privileged reads failed"]]
FAILED = {"changed": False, "module_stdout": "sudo: interactive authentication is required", "module_stderr": "", "msg": "MODULE FAILURE"}
OK = {"stdout_lines": [], "stdout": "", "changed": False}


def run(sd, sm, sn):
    """sd/sm/sn: dotdirs / nullok / sudomount kayitlari; donus: (cikis kodu, cikti, reads_ok)"""
    with tempfile.TemporaryDirectory() as t:
        pb = Path(t) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False,
                                       "vars": {"hardening_report_dotdirs": sd, "hardening_report_nullok": sm, "hardening_report_sudomount": sn},
                                       "tasks": guard + [{"ansible.builtin.debug": {"msg": "READS_OK={{ hardening_report_reads_ok }}"}}]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    return r.returncode, r.stdout + r.stderr


rc, out = run(OK, OK, OK)
check("okumalar basarili: reads_ok=True, atlama uyarisi YOK", rc == 0 and "READS_OK=True" in out and "ATLANDI" not in out, out[-300:])
for ad, args in (("dotdirs", (FAILED, OK, OK)), ("nullok", (OK, FAILED, OK)), ("sudomount", (OK, OK, FAILED))):
    rc, out = run(*args)
    check(f"{ad} okumasi basarisiz: playbook dusmez, reads_ok=False, rapor ATLANDI uyarisi nedeniyle yazilir", rc == 0 and "READS_OK=False" in out and "ATLANDI" in out and "become/sudo" in out, out[-300:])

# Degerlendirme, ayristirma ve iki uyari gorevi AYNI kosula bagli olmali (biri unutulursa kayitsiz bicim yine sablon hatasi verir)
gated = ["Evaluate the system report", "Parse the system report", "Warn from the system report", "Notes from the system report"]
for g in gated:
    check(f"'{g}' reads_ok kosuluna bagli", "hardening_report_reads_ok" in str(by[g].get("when", "")), str(by[g].get("when")))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
raise SystemExit(1 if fails else 0)
