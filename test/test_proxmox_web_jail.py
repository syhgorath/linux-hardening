#!/usr/bin/env python3
"""hardening_fail2ban_pve_web: Proxmox VE web arayüzü için fail2ban jail'i (varsayılan KAPALI, yalnızca proxmox-host). Filtre regex'i örnek günlük satırlarında denenir
(gerçek fail2ban-regex konteynerde ayrıca denendi), kapı koşulları ve kaldırma gerçek Ansible ile."""
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


def load(p):
    return yaml.safe_load((ROOT / p).read_text(encoding="utf-8"))


def play(tasks, extra=None):
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "tasks": tasks}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)] + (["-e", json.dumps(extra)] if extra else []), capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


def w(t):
    x = t.get("when")
    return " ".join(x) if isinstance(x, list) else str(x)


check("varsayilan KAPALI", load("roles/hardening_fail2ban/defaults/main.yml")["hardening_fail2ban_pve_web"] is False)
flt = (ROOT / "roles/hardening_fail2ban/templates/proxmox-web.filter.j2").read_text(encoding="utf-8")
jail = (ROOT / "roles/hardening_fail2ban/templates/proxmox-web.local.j2").read_text(encoding="utf-8")
rx = re.search(r"^failregex = (.+)$", flt, re.M).group(1).replace("<HOST>", r"(?P<host>\S+)")
cases = [("Oct 25 10:00:01 pve1 pvedaemon[1234]: authentication failure; rhost=203.0.113.5 user=root@pam msg=Authentication failure", "203.0.113.5"),
         ("Oct 25 10:00:05 pve1 pvedaemon[77]: authentication failure; rhost=::ffff:198.51.100.7 user=admin@pve msg=Authentication failure", "::ffff:198.51.100.7"),
         ("Oct 25 10:01:00 pve1 pvedaemon[1234]: successful auth for user 'root@pam'", None),
         ("Oct 25 10:02:00 pve1 sshd[1]: authentication failure; rhost=203.0.113.9 user=root", None),
         ("Oct 25 10:03:00 pve1 pveproxy[9]: authentication failure; rhost=203.0.113.9 user=root@pam msg=x", None)]
for line, want in cases:
    m = re.search(rx, line)
    check(f"filtre: {'eslesir -> ' + want if want else 'ESLESMEZ'} ({line[22:60]}...)", (m.group("host") if m else None) == want, rx)
check("jail: 8006, systemd arka ucu, pvedaemon gunluk eslemesi, proxmox-web filtresi", all(x in jail for x in ("[proxmox-web]", "enabled = true", "filter = proxmox-web", "port = 8006", "backend = systemd", "SYSLOG_IDENTIFIER=pvedaemon")))
jail_kod = "\n".join(l for l in jail.splitlines() if not l.strip().startswith("#"))
check("jail [DEFAULT] icermez (ignoreip/bantime sshd.local'den gelir, ezilmez)", "[DEFAULT]" not in jail_kod and "ignoreip" not in jail_kod and "bantime" not in jail_kod)

tasks = load("roles/hardening_fail2ban/tasks/main.yml")
by = {t["name"]: t for t in tasks if isinstance(t, dict) and "name" in t}
blk = by["Proxmox VE web login jail (pvedaemon authentication failures)"]
check("blok yalniz secenek acik VE platform proxmox-host iken", "hardening_fail2ban_pve_web" in w(blk) and "== 'proxmox-host'" in w(blk))
inner = {t["name"]: t for t in blk["block"]}
check("filtre 0644 root, jail.d altina jail, ikisi de yeniden baslatmayi bildirir", inner["Write the Proxmox web filter"]["ansible.builtin.template"]["dest"] == "/etc/fail2ban/filter.d/proxmox-web.conf" and inner["Write the Proxmox web jail"]["ansible.builtin.template"]["dest"] == "/etc/fail2ban/jail.d/proxmox-web.local" and all(t.get("notify") == "Restart fail2ban" for t in (inner["Write the Proxmox web filter"], inner["Write the Proxmox web jail"])))
ck = inner["Check the whole fail2ban configuration"]
check("yapilandirma `fail2ban-client -t` ile dogrulanir, --check'te atlanir, degisiklik saymaz", ck["ansible.builtin.command"] == "fail2ban-client -t" and ck.get("changed_when") is False and "ansible_check_mode" in w(ck))
resc = {t["name"]: t for t in blk["rescue"]}
check("dogrulama basarisizsa iki dosya silinir ve rol DURUR (sshd jail'i bozulmasin)", resc["Remove the Proxmox web jail files after a failed configuration check"]["loop"] == ["/etc/fail2ban/jail.d/proxmox-web.local", "/etc/fail2ban/filter.d/proxmox-web.conf"] and "ansible.builtin.fail" in resc["Stop after the failed fail2ban configuration check"])
note = by["Say that the Proxmox web jail needs a Proxmox VE host"]
for plat, opt, want_note, want_blk in (("generic", True, True, False), ("proxmox-host", True, False, True), ("proxmox-host", False, False, False), ("raspberry-pi", True, True, False)):
    rc, out = play([{"ansible.builtin.debug": {"msg": "NOTE={{ " + w(note) + " }} BLK={{ " + w(blk) + " }}"}}], {"hardening_platform": plat, "hardening_fail2ban_pve_web": opt})
    got = re.search(r"NOTE=(\w+) BLK=(\w+)", out)
    check(f"platform={plat} secenek={opt}: not={want_note} jail={want_blk}", got is not None and (got.group(1) == "True", got.group(2) == "True") == (want_note, want_blk), out[-200:])
rm = by["Remove the Proxmox web jail (option off)"]
check("kapaliyken iki dosya silinir (yeniden baslatma bildirimiyle)", rm["ansible.builtin.file"]["state"] == "absent" and rm["loop"] == ["/etc/fail2ban/jail.d/proxmox-web.local", "/etc/fail2ban/filter.d/proxmox-web.conf"] and rm.get("notify") == "Restart fail2ban" and "not (hardening_fail2ban_pve_web" in w(rm))
with tempfile.TemporaryDirectory() as d:
    f1, f2 = Path(d) / "a", Path(d) / "b"; f1.write_text("x"); f2.write_text("y")
    t = dict(rm); t.pop("notify", None); t["loop"] = [str(f1), str(f2)]
    rc, out = play([t], {"hardening_fail2ban_pve_web": False})
    check("gercek kosu: dosyalar silinir", not f1.exists() and not f2.exists(), out[-150:])
    rc, out = play([t], {"hardening_fail2ban_pve_web": False})
    check("ikinci kosu changed=0", "changed=0" in out, out[-150:])
    f1.write_text("x"); rc, out = play([t], {"hardening_fail2ban_pve_web": True})
    check("secenek aciksa kaldirma gorevi ATLANIR (dosya kalir)", f1.exists(), out[-150:])
cv = {v["name"]: v for v in load("component.yml")["vars"] if isinstance(v, dict)}
check("component.yml: bool, varsayilan false, warn_if true", cv["hardening_fail2ban_pve_web"]["default"] is False and cv["hardening_fail2ban_pve_web"].get("warn_if") is True)
check("docs/component-vars.md icerir", "`hardening_fail2ban_pve_web`" in (ROOT / "docs/component-vars.md").read_text(encoding="utf-8"))
print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
