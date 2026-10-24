#!/usr/bin/env python3
"""Erişim/ağ seçenekleri (hepsi varsayılan KAPALI ya da değişmez): sshd MaxSessions (CIS en çok 10, varsayılan 4), ufw giden trafik DROP (CIS 4.1.4) + izin listesi,
derleyici kısıtlama (Lynis HRDN-7222), AppArmor enforce (CIS 1.3). Gerçek Ansible ile geçici dosyalar / sahte aa-status çıktısı üzerinde denenir."""
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


def w(t):
    x = t.get("when")
    return " ".join(x) if isinstance(x, list) else str(x)


# ---- varsayilanlar ----
sd, ud, fd, ad = (load(f"roles/hardening_{r}/defaults/main.yml") for r in ("ssh", "ufw", "files", "apparmor"))
check("varsayilanlar: MaxSessions 4 (degismez), ufw giden DROP KAPALI, derleyici KAPALI, AppArmor KAPALI", (sd["hardening_ssh_max_sessions"], ud["hardening_ufw_outgoing_deny"], fd["hardening_restrict_compilers"], ad["hardening_apparmor_enforce"]) == (4, False, False, False))
check("ufw giden izin listesi varsayilan: DNS, NTP, http, https", ud["hardening_ufw_outgoing_allow"] == ["53", "123/udp", "80/tcp", "443/tcp"])

# ---- ssh MaxSessions ----
st = load("roles/hardening_ssh/tasks/main.yml")
val = next(t for t in st if t.get("name") == "Validate MaxSessions (CIS allows at most 10)")
for v, ok in ((1, True), (4, True), (10, True), (0, False), (11, False), ("4", False), (2.5, False)):
    rc, out = play([val], extra={"hardening_ssh_max_sessions": v})
    check(f"MaxSessions={v!r} -> {'kabul' if ok else 'RED'}", (rc == 0) == ok, out[-160:])
tpl = (ROOT / "roles/hardening_ssh/templates/sshd-hardening.conf.j2").read_text(encoding="utf-8")
check("sablon: MaxSessions degiskenden gelir (sabit 4 degil)", "MaxSessions {{ hardening_ssh_max_sessions }}" in tpl)
check("golden: varsayilan MaxSessions 4, maxsessions varyanti 2", "MaxSessions 4\n" in (ROOT / "test/golden/sshd-hardening.default.conf").read_text(encoding="utf-8") and "MaxSessions 2\n" in (ROOT / "test/golden/sshd-hardening.maxsessions.conf").read_text(encoding="utf-8"))

# ---- ufw giden trafik ----
ut = load("roles/hardening_ufw/tasks/main.yml")
by = {t["name"]: t for t in ut if isinstance(t, dict) and "name" in t}
names = [t.get("name") for t in ut if isinstance(t, dict)]
pol = by["Default policies"]
for deny, want in ((False, "allow"), (True, "deny")):
    expr = pol["loop"].strip("{} ").strip()
    rc, out = play([{"ansible.builtin.debug": {"msg": "{{ (" + expr + ") | to_json }}"}}], extra={"hardening_ufw_routed_deny": True, "hardening_ufw_outgoing_deny": deny})
    items = []
    for line in out.splitlines():
        if '"msg"' in line:
            items = json.loads(json.loads(line.split('"msg":', 1)[1].strip().rstrip(",")))
    got = {i["key"]: i["value"] for i in items}
    check(f"varsayilan politika (giden DROP={deny}): outgoing={want}, incoming=deny, routed=deny", got == {"incoming": "deny", "outgoing": want, "routed": "deny"}, str(got))
allow = by["Allow outgoing traffic before denying the rest"]
check("giden izin kurallari yalniz hardening_ufw_outgoing_deny iken ve varsayilan degismeden ONCE", "hardening_ufw_outgoing_deny" in w(allow) and names.index("Allow outgoing traffic before denying the rest") < names.index("Default policies"))
check("giden izin kurali `ufw allow out <kural>`", "ufw allow out" in allow["ansible.builtin.command"])
vo = by["Validate the outgoing allow list"]
for lst, ok in ((["53", "123/udp", "80/tcp", "443/tcp"], True), (["8000:8010/udp"], True), (["abc"], False), (["53; rm -rf /"], False), ("53", False), (["99999999"], False)):
    rc, out = play([vo], extra={"hardening_ufw_outgoing_deny": True, "hardening_ufw_outgoing_allow": lst})
    check(f"giden izin listesi {lst!r} -> {'kabul' if ok else 'RED'}", (rc == 0) == ok, out[-160:])
rc, out = play([vo], extra={"hardening_ufw_outgoing_deny": False, "hardening_ufw_outgoing_allow": ["abc"]})
check("giden DROP kapaliyken liste dogrulanmaz (atlanir)", rc == 0)

# ---- derleyici kisitlama: gercek chmod, sembolik bag cozulur, olmayan yol atlanir ----
ft = load("roles/hardening_files/tasks/main.yml")
blk = next(t for t in ft if t.get("name") == "Restrict compilers to root and its group (Lynis HRDN-7222)")
with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    (root / "usr/bin").mkdir(parents=True)
    real = root / "usr/bin/x86_64-linux-gnu-gcc-15"; real.write_text("#!/bin/sh\n"); real.chmod(0o755)
    (root / "usr/bin/gcc").symlink_to("x86_64-linux-gnu-gcc-15")
    asb = root / "usr/bin/as"; asb.write_text("x"); asb.chmod(0o755)
    other = root / "usr/bin/ls-benzeri"; other.write_text("x"); other.chmod(0o755)
    paths = ["/usr/bin/gcc", "/usr/bin/as", "/usr/bin/clang", "/usr/bin/cc"]
    ev = {"hardening_files_root": str(root), "hardening_restrict_compilers_paths": paths}
    rc, out = play([blk], extra={**ev, "hardening_restrict_compilers": False})
    check("derleyici KAPALIYKEN izinler degismez", oct(real.stat().st_mode & 0o777) == "0o755" and oct(asb.stat().st_mode & 0o777) == "0o755", out[-200:])
    rc, out = play([blk], extra={**ev, "hardening_restrict_compilers": True})
    check("derleyici ACIKKEN: 'diger' erisim kalkar, sahip/grup izni korunur (0750)", oct(real.stat().st_mode & 0o777) == "0o750" and oct(asb.stat().st_mode & 0o777) == "0o750", f"{oct(real.stat().st_mode & 0o777)} {oct(asb.stat().st_mode & 0o777)} {out[-200:]}")
    check("sembolik bag cozulur: link degil GERCEK dosya sikilasir, link korunur", (root / "usr/bin/gcc").is_symlink() and oct(real.stat().st_mode & 0o777) == "0o750")
    check("listede olmayan dosyaya dokunulmaz, olmayan yollar (clang, cc) hata vermez", oct(other.stat().st_mode & 0o777) == "0o755" and rc == 0)
    rc, out = play([blk], extra={**ev, "hardening_restrict_compilers": True})
    check("ikinci kosu changed=0", "changed=0" in out, out[-200:])

# ---- AppArmor ----
at = load("roles/hardening_apparmor/tasks/main.yml")
inner = at[0]["block"]
ib = {t["name"]: t for t in inner}
check("AppArmor: tum gorevler hardening_apparmor_enforce ile kapanir", "hardening_apparmor_enforce" in str(at[0].get("when")))
sf = ib["Work out the profiles in complain mode and the unconfined processes"]
sample = {"profiles": {"nvidia_modprobe": "complain", "man_filter": "enforce", "lsb_release": "complain"},
          "processes": {"/usr/sbin/chronyd": [{"profile": "chronyd", "pid": "1", "status": "enforced"}], "/usr/sbin/cupsd": [{"profile": "cupsd", "pid": "2", "status": "unconfined"}]}}
fake = {"hardening_apparmor_enabled": {"rc": 0}, "hardening_apparmor_json": {"rc": 0, "stdout": json.dumps(sample)}}
rc, out = play([{"ansible.builtin.set_fact": fake}, sf, {"ansible.builtin.debug": {"msg": "C={{ hardening_apparmor_complain | sort | join(',') }} U={{ hardening_apparmor_unconfined }}"}}])
check("complain profilleri ve korumasiz surec sayisi aa-status --json'dan dogru cikarilir", "C=lsb_release,nvidia_modprobe U=1" in out, out[-300:])
sample2 = {"profiles": {"a": "enforce", "b": "enforce"}, "processes": {}}
rc, out = play([{"ansible.builtin.set_fact": {**fake, "hardening_apparmor_json": {"rc": 0, "stdout": json.dumps(sample2)}}}, sf, {"ansible.builtin.debug": {"msg": "C={{ hardening_apparmor_complain | length }} U={{ hardening_apparmor_unconfined }}"}}])
check("hepsi enforce ise complain=0, korumasiz=0", "C=0 U=0" in out, out[-300:])
en = ib["Put the complain-mode profiles in enforce mode"]
check("aa-enforce yalniz complain profil VARSA ve --check degilken", "hardening_apparmor_complain" in w(en) and "length > 0" in w(en) and "ansible_check_mode" in w(en) and "aa-enforce /etc/apparmor.d/*" in en["ansible.builtin.shell"]["cmd"])
check("AppArmor etkin degilse (konteyner) NOT verir, baska bir sey yapmaz", "hardening_apparmor_enabled.rc" in w(ib["Say that AppArmor is not enabled"]))
check("aa-status okumalari salt okunur (check_mode false, changed false)", all(ib[n].get("check_mode") is False and ib[n].get("changed_when") is False for n in ("Check whether AppArmor is enabled in the kernel (read-only)", "Read the AppArmor profiles (read-only)")))
hy = load("playbooks/harden.yml")[0]["roles"]
roles = [r["role"] for r in hy if isinstance(r, dict)]
ent = next(r for r in hy if isinstance(r, dict) and r["role"] == "hardening_apparmor")
check("harden.yml: hardening_apparmor `apparmor` etiketiyle, kernel'den SONRA, ufw/ssh'tan ONCE", ent["tags"] == ["apparmor"] and roles.index("hardening_apparmor") > roles.index("hardening_kernel") and roles.index("hardening_apparmor") < roles.index("hardening_ufw"))

# ---- component.yml ----
comp = load("component.yml")
cv = {v["name"]: v for v in comp["vars"] if isinstance(v, dict)}
exp = {"hardening_ssh_max_sessions": (4, False), "hardening_ufw_outgoing_deny": (False, True), "hardening_restrict_compilers": (False, True), "hardening_apparmor_enforce": (False, True)}
for n, (dflt, warn) in exp.items():
    v = cv.get(n)
    check(f"component.yml: {n} varsayilan {dflt}, warn_if={warn}", v is not None and v["default"] == dflt and bool(v.get("warn_if")) == warn, str(v))
doc = (ROOT / "docs/component-vars.md").read_text(encoding="utf-8")
check("docs/component-vars.md bunlari icerir", all(f"`{n}`" in doc for n in exp))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
