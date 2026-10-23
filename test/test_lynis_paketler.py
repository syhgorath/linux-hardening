#!/usr/bin/env python3
"""Lynis paket seçenekleri: debsums (+CRON_CHECK), apt-show-versions, acct, boş jail.local (varsayılan AÇIK) ve apt upgrade (varsayılan KAPALI, warn_if).
Her seçenek kendi değişkeniyle kapanır; component.yml varsayılanı rol varsayılanına EŞİT; apt upgrade `dist-upgrade` değildir."""
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
        print(f"  FAIL {name} {detail}")


def load(p):
    return yaml.safe_load((ROOT / p).read_text(encoding="utf-8"))


bd = load("roles/hardening_base/defaults/main.yml")
fd = load("roles/hardening_fail2ban/defaults/main.yml")
check("varsayilanlar: debsums/show-versions/acct/jail.local ACIK, cron weekly", (bd["hardening_debsums"], bd["hardening_apt_show_versions"], bd["hardening_process_accounting"], fd["hardening_fail2ban_jail_local"], bd["hardening_debsums_cron_check"]) == (True, True, True, True, "weekly"))
check("apt upgrade varsayilan KAPALI", bd["hardening_apt_upgrade"] is False)

tasks = load("roles/hardening_base/tasks/main.yml")
by = {t["name"]: t for t in tasks if isinstance(t, dict) and "name" in t}


def need(name):
    t = by.get(name)
    check(f"gorev var: {name}", t is not None)
    return t or {}


def when_has(t, var):
    w = t.get("when")
    return var in (" ".join(w) if isinstance(w, list) else str(w))


t = need("Install debsums")
check("debsums: apt present (kaldirma yok), kendi degiskeniyle kapanir", t.get("ansible.builtin.apt", {}).get("state") == "present" and t["ansible.builtin.apt"]["name"] == "debsums" and when_has(t, "hardening_debsums"))
t = need("Check the debsums cron setting")
check("CRON_CHECK degeri dogrulanir (daily/weekly/monthly/never)", all(v in str(t.get("ansible.builtin.assert", {}).get("that")) for v in ("daily", "weekly", "monthly", "never")))
t = need("Schedule the debsums check (CRON_CHECK)")
lf = t.get("ansible.builtin.lineinfile", {})
check("CRON_CHECK: /etc/default/debsums, create YOK (paketin dosyasi; --check'te paket yoksa atlanir)", lf.get("path") == "/etc/default/debsums" and not lf.get("create") and "CRON_CHECK={{ hardening_debsums_cron_check }}" == lf.get("line"))
check("CRON_CHECK: --check + yeni kurulum iken atlanir, degiskenle kapanir", when_has(t, "ansible_check_mode") and when_has(t, "hardening_debsums_install") and when_has(t, "hardening_debsums"))
t = need("Install apt-show-versions")
check("apt-show-versions: present, kendi degiskeniyle kapanir", t.get("ansible.builtin.apt", {}).get("state") == "present" and when_has(t, "hardening_apt_show_versions"))
t = need("Install acct (process accounting)")
check("acct: present, kendi degiskeniyle kapanir", t.get("ansible.builtin.apt", {}).get("state") == "present" and when_has(t, "hardening_process_accounting"))
t = need("Enable process accounting")
sd = t.get("ansible.builtin.systemd", {})
check("acct.service etkin+baslat, --check'te atlanir, degiskenle kapanir", sd.get("name") == "acct" and sd.get("enabled") is True and when_has(t, "ansible_check_mode") and when_has(t, "hardening_process_accounting"))
t = need("Upgrade the installed packages (apt-get upgrade)")
ap = t.get("ansible.builtin.apt", {})
check("apt upgrade: `dist-upgrade` DEGIL (paket kaldirmaz), degiskenle kapanir", str(ap.get("upgrade")).lower() in ("yes", "true", "safe") and "dist" not in str(ap.get("upgrade")) and when_has(t, "hardening_apt_upgrade"))
check("apt upgrade: yeniden baslatma gerekirse UYARI, sunucu yeniden BASLATILMAZ", "Warn that a reboot is required" in by and "ansible.builtin.reboot" not in (ROOT / "roles/hardening_base/tasks/main.yml").read_text(encoding="utf-8"))

f2 = load("roles/hardening_fail2ban/tasks/main.yml")
jl = next((x for x in f2 if x.get("name") == "Create an empty jail.local (user overrides go here)"), {})
cp = jl.get("ansible.builtin.copy", {})
check("jail.local: force=false (kullanicinin dosyasina dokunulmaz), 0644, kendi degiskeniyle kapanir", cp.get("dest") == "/etc/fail2ban/jail.local" and cp.get("force") is False and cp.get("mode") == "0644" and "hardening_fail2ban_jail_local" in str(jl.get("when")))
check("jail.local icerigi yalnizca aciklama (davranis degistirmez)", all(l.strip().startswith("#") or not l.strip() for l in cp.get("content", "").splitlines()))

# CRON_CHECK: gercek lineinfile, idempotent, paketin 'never' satirini degistirir
with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "debsums"
    f.write_text("# a\nCRON_CHECK=never\n", encoding="utf-8")
    lf2 = dict(lf); lf2["path"] = str(f)
    pb = Path(d) / "p.yml"
    pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_debsums_cron_check": "weekly"}, "tasks": [{"ansible.builtin.lineinfile": lf2}]}]), encoding="utf-8")
    run = lambda: subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL, env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    r1 = run()
    check("CRON_CHECK=never -> weekly olur", f.read_text(encoding="utf-8") == "# a\nCRON_CHECK=weekly\n", f.read_text(encoding="utf-8"))
    r2 = run()
    check("ikinci kosu changed=0", "changed=0" in r2.stdout, r2.stdout[-200:])

comp = load("component.yml")
cv = {v["name"]: v for v in comp["vars"] if isinstance(v, dict)}
exp = {"hardening_debsums": (bd["hardening_debsums"], False), "hardening_debsums_cron_check": (bd["hardening_debsums_cron_check"], False), "hardening_apt_show_versions": (bd["hardening_apt_show_versions"], False),
       "hardening_process_accounting": (bd["hardening_process_accounting"], False), "hardening_fail2ban_jail_local": (fd["hardening_fail2ban_jail_local"], False), "hardening_apt_upgrade": (bd["hardening_apt_upgrade"], True)}
for name, (dflt, warn) in exp.items():
    v = cv.get(name)
    check(f"component.yml: {name} var, varsayilan rol ile AYNI, warn_if={warn}", v is not None and v["default"] == dflt and bool(v.get("warn_if")) == warn, str(v))
doc = (ROOT / "docs/component-vars.md").read_text(encoding="utf-8")
check("docs/component-vars.md bu degiskenleri icerir", all(f"`{n}`" in doc for n in exp))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
