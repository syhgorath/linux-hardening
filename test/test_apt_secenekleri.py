#!/usr/bin/env python3
"""apt seçenekleri (varsayılan KAPALI): hardening_apt_upgrade_phased (Ubuntu kademeli güncellemeleri de yükselt, `dist-upgrade` değil) ve hardening_apt_listbugs (yalnızca Debian ailesi,
kanca `-y` ile yazılır, apt'yi ASLA bloklamaz). Görevlerin GERÇEK `when`/`changed_when` ifadeleri ve `lineinfile` gerçek Ansible ile denenir."""
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
        print(f"  FAIL {name} {detail}")


def load(p):
    return yaml.safe_load((ROOT / p).read_text(encoding="utf-8"))


def play(tasks, vars_=None, extra=None):
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": vars_ or {}, "tasks": tasks}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)] + (["-e", json.dumps(extra)] if extra else []), capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


def ran(when, vars_):
    rc_, out = play([{"ansible.builtin.debug": {"msg": "RAN_MARKER"}, "when": when}], vars_=vars_)
    return "RAN_MARKER" in out and "skipping" not in out.split("RAN_MARKER")[0].split("TASK")[-1], out


bd = load("roles/hardening_base/defaults/main.yml")
check("varsayilanlar: apt_upgrade, apt_upgrade_phased, apt_listbugs hepsi KAPALI", (bd["hardening_apt_upgrade"], bd["hardening_apt_upgrade_phased"], bd["hardening_apt_listbugs"]) == (False, False, False))
tasks = load("roles/hardening_base/tasks/main.yml")
by = {t["name"]: t for t in tasks if isinstance(t, dict) and "name" in t}

# ---- phased ----
plain = by["Upgrade the installed packages (apt-get upgrade)"]
refresh = by["Refresh the apt package lists (phased upgrade)"]
ph = by["Upgrade the installed packages including phased updates (apt-get upgrade)"]
argv = ph["ansible.builtin.command"]["argv"]
check("phased: `upgrade` (dist-upgrade DEGIL), Always-Include-Phased-Updates=true, onaysiz (-y)", "upgrade" in argv and "dist-upgrade" not in argv and "APT::Get::Always-Include-Phased-Updates=true" in argv and "-y" in argv and argv[0] == "apt-get")
check("phased: dpkg yapilandirma dosyalarini KORUR (force-confold) ve onay istemez (DEBIAN_FRONTEND=noninteractive)", "Dpkg::Options::=--force-confold" in argv and ph["environment"]["DEBIAN_FRONTEND"] == "noninteractive")
for upg, phased, want_plain, want_ph in ((False, False, False, False), (True, False, True, False), (True, True, False, True), (False, True, False, False)):
    v = {"hardening_apt_upgrade": upg, "hardening_apt_upgrade_phased": phased}
    gp, o1 = ran(plain["when"], v); gh, o2 = ran(ph["when"], v); gr, o3 = ran(refresh["when"], v)
    check(f"apt_upgrade={upg} phased={phased}: normal={want_plain} phased={want_ph} (liste yenileme phased ile)", (gp, gh, gr) == (want_plain, want_ph, want_ph), f"{gp},{gh},{gr}")
for out_txt, want in (("0 upgraded, 0 newly installed, 0 to remove and 2 not upgraded.", False), ("3 upgraded, 0 newly installed, 0 to remove and 0 not upgraded.", True), ("12 upgraded, 1 newly installed, 0 to remove and 0 not upgraded.", True), ("The following packages have been kept back:", False)):
    rc_, o = play([{"ansible.builtin.debug": {"msg": "C={{ " + ph["changed_when"].replace("hardening_apt_upgrade_phased_result.stdout", "(txt)") + " }}"}}], vars_={"txt": out_txt})
    check(f"changed_when: {out_txt[:34]!r} -> changed={want}", ("C=True" in o) == want, o[-160:])

# ---- listbugs ----
nt = by["Say that apt-listbugs is only for Debian"]
blk = by["Install apt-listbugs (never blocks apt)"]
for dist, opt, want_note, want_blk in (("Debian", True, False, True), ("Ubuntu", True, True, False), ("Debian", False, False, False), ("Ubuntu", False, False, False)):
    v = {"hardening_apt_listbugs": opt, "ansible_facts": {"distribution": dist}}
    n_, o1 = ran(nt["when"], v); b_, o2 = ran(blk["when"], v)
    check(f"dagitim={dist} secenek={opt}: NOT={want_note} kurulum={want_blk}", (n_, b_) == (want_note, want_blk), f"{n_},{b_}")
inner = {t["name"]: t for t in blk["block"]}
check("paket kurulur (present, kaldirma yok)", inner["Install apt-listbugs"]["ansible.builtin.apt"] == {"name": "apt-listbugs", "state": "present"})
lf = inner["Make the apt-listbugs hook assume yes (so it never blocks apt)"]
with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "10apt-listbugs"
    orig = '// yorum\nDPkg::Pre-Install-Pkgs {"/usr/bin/apt-listbugs apt";};\nDPkg::Tools::Options::/usr/bin/apt-listbugs "";\nAptListbugs::Severities "critical,grave,serious";\n'
    f.write_text(orig, encoding="utf-8")
    t = dict(lf); t.pop("when", None); t["ansible.builtin.lineinfile"] = dict(lf["ansible.builtin.lineinfile"], path="{{ lb }}")
    play([t], vars_={"lb": str(f)}); txt = f.read_text(encoding="utf-8")
    check("kanca `-y` olur, baska satirlar KORUNUR", 'DPkg::Pre-Install-Pkgs {"/usr/bin/apt-listbugs -y apt";};' in txt and '"/usr/bin/apt-listbugs apt"' not in txt and "// yorum" in txt and 'AptListbugs::Severities "critical,grave,serious";' in txt and txt.count("Pre-Install-Pkgs") == 1, txt)
    rc, out = play([t], vars_={"lb": str(f)})
    check("ikinci kosu changed=0 (zaten -y)", "changed=0" in out, out[-150:])
    f.write_text('DPkg::Tools::Options::/usr/bin/apt-listbugs "";\n', encoding="utf-8"); play([t], vars_={"lb": str(f)})
    check("kanca satiri yoksa (baska surum) EKLENIR", 'apt-listbugs -y apt' in f.read_text(encoding="utf-8"))
cv = {v["name"]: v for v in load("component.yml")["vars"] if isinstance(v, dict)}
check("component.yml: apt_upgrade_phased KAPALI warn_if, apt_listbugs KAPALI", cv["hardening_apt_upgrade_phased"]["default"] is False and cv["hardening_apt_upgrade_phased"].get("warn_if") is True and cv["hardening_apt_listbugs"]["default"] is False)
doc = (ROOT / "docs/component-vars.md").read_text(encoding="utf-8")
check("docs/component-vars.md icerir", "`hardening_apt_upgrade_phased`" in doc and "`hardening_apt_listbugs`" in doc)
print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
