#!/usr/bin/env python3
"""hardening_auth: root ortamı raporu görevleri SALT OKUNUR kalmalı (statik) ve gerçek görev zinciri (hazırlık + betik çağrısı) sahte okuma çıktılarıyla doğru girdiyi üretmeli.
Raporun kendisi hiçbir şeyi değiştirmez, başarısız kılmaz, `--check`'te de çalışır ve kapatılabilir (hardening_root_env_report)."""
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


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail}")


def eq(name, want, got):
    check(name, want == got, f"beklenen={want!r} gercek={got!r}")


def walk(ts):
    for t in ts or []:
        yield t
        yield from walk(t.get("block"))


def mod(t):
    return next((k for k in t if k.startswith("ansible.builtin.")), None)


tasks = yaml.safe_load((ROOT / "roles/hardening_auth/tasks/main.yml").read_text(encoding="utf-8"))
defaults = yaml.safe_load((ROOT / "roles/hardening_auth/defaults/main.yml").read_text(encoding="utf-8"))
blk = next(t for t in tasks if t.get("name") == "Root environment report (read-only)")
leaf = [t for t in walk(blk["block"]) if mod(t)]
by = {t["name"]: t for t in leaf}

check("varsayilan ACIK (salt okunur)", defaults["hardening_root_env_report"] is True)
check("blok kendi degiskeniyle kapanir", "hardening_root_env_report" in str(blk["when"]))
check("yalniz salt okunur moduller (command, shell, script, set_fact, debug)", all(mod(t) in {"ansible.builtin.command", "ansible.builtin.shell", "ansible.builtin.script", "ansible.builtin.set_fact", "ansible.builtin.debug"} for t in leaf),
      str(sorted({mod(t) for t in leaf})))
reads = [t for t in leaf if mod(t) in ("ansible.builtin.command", "ansible.builtin.shell", "ansible.builtin.script")]
check("okuma/degerlendirme gorevleri --check'te de calisir (check_mode: false)", all(t.get("check_mode") is False for t in reads))
check("degisiklik saymaz (changed_when: false)", all(t.get("changed_when") is False for t in reads))
check("okumalar basarisiz olursa rol durmaz (failed_when: false)", all(t.get("failed_when") is False for t in reads if mod(t) in ("ansible.builtin.command", "ansible.builtin.shell")))
check("hicbir gorev fail/assert/handler kullanmaz", all(mod(t) not in ("ansible.builtin.fail", "ansible.builtin.assert") and "notify" not in t for t in leaf))
pathtask = by["Read root's login PATH"]
check("root PATH `shell` ile okunur ($PATH'i command modulu acip sudo'nun PATH'ini verirdi, VM'de gorulmus gibi yanlis sonuc)", "ansible.builtin.shell" in pathtask and "ansible.builtin.command" not in pathtask and "'echo \"$PATH\"'" in pathtask["ansible.builtin.shell"]["cmd"])
cmds = " ".join(str(t.get("ansible.builtin.command", "")) + str(t.get("ansible.builtin.shell", {}).get("cmd", "")) for t in leaf)
check("yazan/degistiren komut yok (chmod, chown, sed -i, tee, >, umask ayari, export)", not any(x in cmds for x in ("chmod", "chown", "sed -i", "tee ", " > ", ">>", "rm ", "mv ", "cp ")), cmds[:200])

insp = by["Inspect the directories in root's PATH"]["ansible.builtin.shell"]["cmd"]
check("dizin denetimi `stat -L` kullanir (/bin, /sbin sembolik baglari 777 gorunup yanlis alarm vermesin)", "stat -L" in insp)

# gerçek zincir: sahte okuma çıktıları -> betik girdisi -> sonuç
PATH_OUT = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin"
DIRS = ["755 root /usr/local/sbin", "755 root /usr/local/bin", "755 root /usr/sbin", "755 root /usr/bin", "755 root /sbin", "755 root /bin", "755 root /snap/bin"]
UM = ["LOGINDEFS:027", "PAMUMASK:yes"]


def chain(path_out, dirs, umask_lines):
    ev = dict(by["Evaluate the root environment"]["ansible.builtin.script"])
    ev["cmd"] = re.sub(r"^root_env_report\.py", str(ROOT / "roles/hardening_auth/files/root_env_report.py"), ev["cmd"].strip())
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "tasks": [
            {"ansible.builtin.set_fact": {"hardening_root_env_path": {"stdout": path_out}, "hardening_root_env_dirs": {"stdout_lines": dirs}, "hardening_root_env_umask": {"stdout_lines": umask_lines}}},
            {"ansible.builtin.script": ev, "register": "hardening_root_env_raw"},
            {"ansible.builtin.set_fact": {"hardening_root_env_result": by["Parse the root environment report"]["ansible.builtin.set_fact"]["hardening_root_env_result"]}},
            {"ansible.builtin.debug": {"msg": "R={{ hardening_root_env_result | to_json | b64encode }}"}}]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    m = re.search(r"R=(\S+?)\"?\s*$", r.stdout, re.M)
    return json.loads(base64.b64decode(m.group(1))) if m else {"_ham": r.stdout[-400:]}


o = chain(PATH_OUT, DIRS, UM)
eq("zincir: temiz sunucu -> ok", "ok", o.get("status"))
o = chain(PATH_OUT + ":.", DIRS, UM)
eq("zincir: PATH'te '.' -> warn", ("warn", True), (o.get("status"), "`.`" in " ".join(o.get("messages", []))))
o = chain(PATH_OUT, DIRS, ["LOGINDEFS:022", "PAMUMASK:yes", "/root/.bashrc:umask 022"])
eq("zincir: login.defs 022 ve /root/.bashrc umask 022 -> ikisi de raporlanir", (True, True), ("login.defs" in " ".join(o.get("messages", [])), "/root/.bashrc" in " ".join(o.get("messages", []))))
o = chain(PATH_OUT, DIRS, ["LOGINDEFS:027"])
check("zincir: PAMUMASK satiri yoksa pam_umask uyarisi", "pam_umask" in " ".join(o.get("messages", [])))
o = chain(PATH_OUT, DIRS, ["PAMUMASK:yes"])
check("zincir: login.defs UMASK satiri yoksa 'umask bulunamadi' uyarisi", "umask" in " ".join(o.get("messages", [])).lower() and o.get("status") == "warn")

v = next((x for x in yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))["vars"] if isinstance(x, dict) and x["name"] == "hardening_root_env_report"), None)
check("component.yml: bool, varsayilan true, warn_if YOK (#74)", bool(v) and v["type"] == "bool" and v["default"] is True and "warn_if" not in v)
sys.exit(1 if fails else 0)
