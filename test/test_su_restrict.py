#!/usr/bin/env python3
"""hardening_sudo: su kısıtı (CIS 5.2.7), varsayılan KAPALI. /etc/pam.d/su'ya gerçek `lineinfile` ile pam_wheel satırı eklenir (Ubuntu 26.04'ün gerçek su dosyası üzerinde).

Asıl riskler: satırın yanlış yere girmesi (pam_rootok'tan ÖNCE girerse root da reddedilir), tekrar koşuda çoğalması, geçersiz grup adının PAM dosyasına sızması.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
fails = 0

# Ubuntu 26.04 /etc/pam.d/su (yorumlar kısaltıldı; sıra ve yorumlu pam_wheel örnek satırları gerçeğiyle aynı)
SU = """#
# The PAM configuration file for the Shadow `su' service
#

# This allows root to su without passwords (normal operation)
auth       sufficient pam_rootok.so

# Uncomment this to force users to be a member of group wheel
# auth       required   pam_wheel.so

# Uncomment this if you want wheel members to be able to
# su without a password.
# auth       sufficient pam_wheel.so trust

session       required   pam_env.so readenv=1
session    required   pam_limits.so

@include common-auth
@include common-account
@include common-session
"""


def check(name, want, got):
    global fails
    if want == got:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}: beklenen={want!r} gercek={got!r}")


tasks = yaml.safe_load((ROOT / "roles/hardening_sudo/tasks/main.yml").read_text(encoding="utf-8"))
blk = next(t for t in tasks if t.get("name") == "Restrict su to a group (CIS 5.2.7)")
by = {t["name"]: t for t in blk["block"]}
d = yaml.safe_load((ROOT / "roles/hardening_sudo/defaults/main.yml").read_text(encoding="utf-8"))
check("varsayilan KAPALI, grup sugroup", (False, "sugroup"), (d["hardening_su_restrict"], d["hardening_su_group"]))
check("blok kendi degiskeniyle kapanir (sudo_enabled'dan bagimsiz)", ("hardening_su_restrict | bool", False), (blk["when"], "hardening_sudo_enabled" in str(blk["when"])))
check("sira: ad dogrulama -> grup olustur -> PAM satiri", ["Check the su group name", "Make sure the su group exists (empty when created here)", "Require membership of the su group in /etc/pam.d/su"], list(by))
check("grup sistem grubu olarak olusturulur, uye eklenmez (user/groups yok)", (True, False), (by["Make sure the su group exists (empty when created here)"]["ansible.builtin.group"]["system"], "members" in by["Make sure the su group exists (empty when created here)"]["ansible.builtin.group"]))


def play(tmp, group, extra=None):
    lf = dict(by["Require membership of the su group in /etc/pam.d/su"]["ansible.builtin.lineinfile"])
    lf["path"] = str(Path(tmp) / "su"); lf.pop("owner"); lf.pop("group")
    pb = Path(tmp) / "p.yml"
    pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_su_group": group},
                                   "tasks": [by["Check the su group name"], {"ansible.builtin.lineinfile": lf}]}]), encoding="utf-8")
    r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    return r


with tempfile.TemporaryDirectory() as tmp:
    (Path(tmp) / "su").write_text(SU, encoding="utf-8")
    r = play(tmp, "sugroup")
    lines = (Path(tmp) / "su").read_text(encoding="utf-8").splitlines()
    want = "auth       required   pam_wheel.so use_uid group=sugroup"
    check("satir eklendi", (0, 1), (r.returncode, lines.count(want)))
    i, j = lines.index("auth       sufficient pam_rootok.so"), lines.index(want)
    check("pam_rootok'tan HEMEN SONRA (root once gecer; sonra pam_wheel)", j, i + 1)
    check("yorumlu ornek satirlar ve @include'lar bozulmadi", (True, True, True), ("# auth       required   pam_wheel.so" in lines, "# auth       sufficient pam_wheel.so trust" in lines, "@include common-auth" in lines))
    before = (Path(tmp) / "su").read_text(encoding="utf-8")
    r2 = play(tmp, "sugroup")
    check("ikinci kosu changed=0, dosya ayni (satir cogalmaz)", (True, before), ("changed=0" in r2.stdout, (Path(tmp) / "su").read_text(encoding="utf-8")))
    r3 = play(tmp, "sudo")
    t = (Path(tmp) / "su").read_text(encoding="utf-8")
    check("grup degisince eski satir YERINDE guncellenir (iki pam_wheel satiri olmaz)", (1, True), (t.count("pam_wheel.so use_uid"), "group=sudo" in t))

for bad in ("a b", "x;rm", "Grup", "-x", "", "a" * 33, "x\nauth sufficient pam_permit.so"):
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "su").write_text(SU, encoding="utf-8")
        r = play(tmp, bad)
        check(f"gecersiz grup adi {bad[:12]!r} reddedilir, su dosyasina DOKUNULMAZ", (True, SU), (r.returncode != 0, (Path(tmp) / "su").read_text(encoding="utf-8")))

v = next((x for x in yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))["vars"] if isinstance(x, dict) and x["name"] == "hardening_su_restrict"), None)
check("component.yml: bool, varsayilan false, warn_if true (davranis degistirir)", (True, False, True), (v["type"] == "bool", v["default"], v.get("warn_if") is True))
print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
