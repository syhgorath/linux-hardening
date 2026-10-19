#!/usr/bin/env python3
"""hardening_files: /tmp ve /dev/shm raporu görevleri SALT OKUNUR kalmalı (statik) ve gerçek görev zinciri (betik çağrısı + gösterim) doğru çalışmalı.
Rapor hiçbir şeyi değiştirmez, başarısız kılmaz, `--check`'te de çalışır, kapatılabilir (hardening_tmp_report) ve hardening_files_enabled'dan bağımsızdır."""
import base64
import json
import os
import re
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


def eq(name, want, got):
    if want == got:
        check(name, True)
    else:
        check(f"{name}: beklenen={want!r} gercek={got!r}", False)


def walk(ts):
    for t in ts or []:
        yield t
        yield from walk(t.get("block"))


def mod(t):
    return next((k for k in t if k.startswith("ansible.builtin.")), None)


tasks = yaml.safe_load((ROOT / "roles/hardening_files/tasks/main.yml").read_text(encoding="utf-8"))
defaults = yaml.safe_load((ROOT / "roles/hardening_files/defaults/main.yml").read_text(encoding="utf-8"))
blk = next(t for t in tasks if t.get("name") == "Temporary directory mount report (read-only)")
leaf = [t for t in walk(blk["block"]) if mod(t)]
by = {t["name"]: t for t in leaf}

check("varsayilan ACIK", defaults["hardening_tmp_report"] is True)
check("blok kendi degiskeniyle kapanir ve hardening_files_enabled'a BAGLI DEGIL", "hardening_tmp_report" in str(blk["when"]) and "hardening_files_enabled" not in str(blk["when"]))
check("yalniz salt okunur moduller (shell, script, set_fact, debug)", all(mod(t) in {"ansible.builtin.shell", "ansible.builtin.script", "ansible.builtin.set_fact", "ansible.builtin.debug"} for t in leaf))
reads = [t for t in leaf if mod(t) in ("ansible.builtin.shell", "ansible.builtin.script")]
check("okuma/degerlendirme gorevleri --check'te de calisir (check_mode: false)", all(t.get("check_mode") is False for t in reads))
check("degisiklik saymaz (changed_when: false)", all(t.get("changed_when") is False for t in reads))
check("okuma basarisiz olursa rol durmaz (failed_when: false)", by["Read the mounts behind /tmp and /dev/shm"].get("failed_when") is False)
check("fail/assert/handler yok", all(mod(t) not in ("ansible.builtin.fail", "ansible.builtin.assert") and "notify" not in t for t in leaf))
cmd = by["Read the mounts behind /tmp and /dev/shm"]["ansible.builtin.shell"]["cmd"]
check("yalniz findmnt okur; mount/remount/umount/fstab/systemctl yok", "findmnt" in cmd and not any(x in cmd for x in ("remount", "mount -o", "umount", "fstab", "systemctl", " > ", ">>", "tee ")))

NOEXEC_LESS = ["/tmp: /tmp tmpfs rw,nosuid,nodev,size=1k", "/dev/shm: /dev/shm tmpfs rw,nosuid,nodev,inode64"]


def chain(mounts, remote_tmp=None):
    ev = dict(by["Evaluate the temporary directory mounts"]["ansible.builtin.script"])
    ev["cmd"] = re.sub(r"^tmp_report\.py", str(ROOT / "roles/hardening_files/files/tmp_report.py"), ev["cmd"].strip())
    facts = {"hardening_tmp_mounts": {"stdout_lines": mounts}}
    if remote_tmp is not None:
        facts["ansible_remote_tmp"] = remote_tmp
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "tasks": [
            {"ansible.builtin.set_fact": facts},
            {"ansible.builtin.script": ev, "register": "hardening_tmp_raw"},
            {"ansible.builtin.set_fact": {"hardening_tmp_result": by["Parse the temporary directory report"]["ansible.builtin.set_fact"]["hardening_tmp_result"]}},
            {"ansible.builtin.debug": {"msg": "R={{ hardening_tmp_result | to_json | b64encode }}"}}]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    m = re.search(r"R=(\S+?)\"?\s*$", r.stdout, re.M)
    return json.loads(base64.b64decode(m.group(1))) if m else {"_ham": r.stdout[-300:]}


o = chain(NOEXEC_LESS)
eq("zincir: Ubuntu varsayilani -> ok, 2 not", ("ok", 3), (o.get("status"), len(o.get("notes", []))))
o = chain(NOEXEC_LESS, "/tmp/.ansible")
eq("zincir: ansible_remote_tmp=/tmp/.ansible -> warn", ("warn", True), (o.get("status"), any("uzak geçici dizini" in w for w in o.get("warnings", []))))
o = chain(NOEXEC_LESS, "~/.ansible/tmp")
eq("zincir: ansible_remote_tmp=~/.ansible/tmp -> ok", "ok", o.get("status"))
o = chain(["/tmp: / ext4 rw", NOEXEC_LESS[1]])
eq("zincir: /tmp ayri baglama degil -> warn", "warn", o.get("status"))

shown = by["Show the temporary directory report"]
check("not gosterimi yalniz not/ozet varken ve unknown degilken", "notes" in str(shown["when"]) and "unknown" in str(shown["when"]))
v = next((x for x in yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))["vars"] if isinstance(x, dict) and x["name"] == "hardening_tmp_report"), None)
check("component.yml: bool, varsayilan true, warn_if YOK (#74)", bool(v) and v["type"] == "bool" and v["default"] is True and "warn_if" not in v)
sys.exit(1 if fails else 0)
