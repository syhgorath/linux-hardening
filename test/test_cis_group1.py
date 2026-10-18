#!/usr/bin/env python3
"""CIS grup 1 (sessiz/güvenli parçalar): apport ve update-notifier-motd kapatma, SUID/SGID özeti (hardening_base).

Görevlerin kendi lineinfile parametreleri ve `when` ifadeleri gerçek `ansible-playbook` ile denenir. Dikkat edilenler: olmayan birime dokunulmaması,
`--check`'te servis değişmemesi, SUID özetinin SALT OKUNUR kalması, her parçanın kendi değişkeniyle kapanabilmesi.
"""
import os
import re
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


def task(name):
    for t in yaml.safe_load((ROOT / "roles/hardening_base/tasks/main.yml").read_text(encoding="utf-8")):
        if t.get("name") == name:
            return t
    raise SystemExit(f"görev yok: {name}")


def play(tasks, vars_=None):
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": vars_ or {}, "tasks": tasks}], allow_unicode=True), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


defaults = yaml.safe_load((ROOT / "roles/hardening_base/defaults/main.yml").read_text(encoding="utf-8"))
check("varsayilanlar: apport, motd zamanlayicisi, SUID ozeti ACIK", {"hardening_disable_apport": True, "hardening_disable_update_notifier_motd": True, "hardening_suid_report": True}, defaults)

# 1) apport: lineinfile'in kendi parametreleri, geçici dosyada
li = task("Disable apport in its defaults file")["ansible.builtin.lineinfile"]


def run_li(text):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "apport"
        f.write_text(text, encoding="utf-8")
        rc, out = play([{"ansible.builtin.lineinfile": {"path": str(f), "regexp": li["regexp"], "line": li["line"]}}])
        return f.read_text(encoding="utf-8"), "changed=1" in out


txt, ch = run_li("# set this to 0 to disable apport\nenabled=1\n")
check("apport: enabled=1 -> enabled=0, yorum satirlari bozulmaz", ("# set this to 0 to disable apport\nenabled=0\n", True), (txt, ch))
txt2, ch2 = run_li(txt)
check("apport: ikinci kosu degisiklik YOK (idempotent)", (txt, False), (txt2, ch2))
txt, ch = run_li("# enabled=1\nenabled=1\n")
check("apport: yorumlanmis '# enabled=1' satirina dokunulmaz", ("# enabled=1\nenabled=0\n", True), (txt, ch))
check("apport: dosya yoksa (stat) atlanir ve olusturulmaz", True, "exists" in str(task("Disable apport in its defaults file")["when"]) and li.get("create") is not True)

# 2) birim durumu: get-state görevleri salt okunur, maskeleme yalnız birim VARSA
for n, unit in (("Read apport.service state (read-only)", "apport.service"), ("Read update-notifier-motd.timer state (read-only)", "update-notifier-motd.timer")):
    t = task(n)
    sd = t["ansible.builtin.systemd"]
    check(f"{unit}: durum okuma salt okunur (state/enabled/masked yok), --check'te de calisir, durmaz", True,
          sd == {"name": unit} and t.get("check_mode") is False and t.get("failed_when") is False)
for n, unit, var, reg in (("Stop and mask apport.service", "apport.service", "hardening_disable_apport", "hardening_base_apport_unit"),
                          ("Stop and mask update-notifier-motd.timer", "update-notifier-motd.timer", "hardening_disable_update_notifier_motd", "hardening_base_motd_unit")):
    t = task(n)
    sd = t["ansible.builtin.systemd"]
    check(f"{unit}: durdurulur ve maskelenir", True, sd == {"name": unit, "state": "stopped", "masked": True})
    when = str(t["when"])
    check(f"{unit}: kendi degiskeniyle kapanir ({var})", True, var in when)
    for state, want in (("loaded", True), ("not-found", False), (None, False)):
        status = {} if state is None else {"LoadState": state}
        rc, out = play([{"ansible.builtin.set_fact": {reg: {"status": status}}},
                        {"name": "probe", "ansible.builtin.debug": {"msg": "calisti"}, "when": t["when"]}], {var: True})
        check(f"{unit}: LoadState={state!r} iken " + ("calisir" if want else "ATLANIR"), want, "calisti" in out)
    rc, out = play([{"ansible.builtin.set_fact": {reg: {"status": {"LoadState": "loaded"}}}},
                    {"name": "probe", "ansible.builtin.debug": {"msg": "calisti"}, "when": t["when"]}], {var: False})
    check(f"{unit}: {var}=false iken atlanir", False, "calisti" in out)

# 3) SUID/SGID özeti: salt okunur
sh = task("List SUID/SGID files (read-only)")
cmd = sh["ansible.builtin.shell"]["cmd"]
check("SUID: yalnizca find listeler (chmod/chown/-delete/-exec yok), zaman asimi var", True, all(x not in cmd for x in ("chmod", "chown", "-delete", "-exec")) and not re.search(r"\brm\s", cmd) and "timeout" in cmd and "find /" in cmd)
check("SUID: -xdev (ag/ek bolumlere inmez), pipefail", True, "-xdev" in cmd and "pipefail" in cmd)
check("SUID: degisiklik saymaz, --check'te de calisir, kendi degiskeniyle kapanir", True, sh.get("changed_when") is False and sh.get("check_mode") is False and "hardening_suid_report" in str(sh["when"]))
check("SUID: ozet yalniz debug (ilk 40 dosya)", True, "[:40]" in str(task("Show SUID/SGID summary")))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
