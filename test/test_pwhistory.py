#!/usr/bin/env python3
"""hardening_auth: parola geçmişi (pam_pwhistory), varsayılan KAPALI. Statik yapı + gerçek `lineinfile` ile Ubuntu 26.04'ün gerçek pwhistory.conf'u üzerinde.

Asıl riskler: yanlış PAM sırası (pwhistory, pwquality'den ÖNCE ya da unix'ten SONRA olursa işe yaramaz), yığın bozulursa şifre değiştirme çalışmaz (assert + rescue ile profil geri alınır),
tekrarlayan koşuda dosyanın bozulması, enforce_for_root kapalıyken kullanıcının yorum satırının silinmesi."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
fails = 0

CONF = """# Configuration for remembering the last passwords used by a user.
#
# Enable the debugging logs.
# Enabled if option is present.
# debug
#
# root account's passwords are also remembered.
# Enabled if option is present.
# enforce_for_root
#
# Number of passwords to remember.
# The default is 10.
# remember = 10
#
# Number of times to prompt for the password.
# The default is 1.
# retry = 1
#
# The file where the last passwords are kept.
# The default is /etc/security/opasswd.
# file = /etc/security/opasswd
"""


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail}")


def eq(name, want, got):
    check(name, want == got, f"beklenen={want!r} gercek={got!r}")


tasks = yaml.safe_load((ROOT / "roles/hardening_auth/tasks/main.yml").read_text(encoding="utf-8"))
d = yaml.safe_load((ROOT / "roles/hardening_auth/defaults/main.yml").read_text(encoding="utf-8"))
blk = next(t for t in tasks if t.get("name") == "Password history (pam_pwhistory)")
by = {t["name"]: t for t in blk["block"]}
eq("varsayilan KAPALI: remember=0, enforce_for_root=false", (0, False), (d["hardening_pam_pwhistory_remember"], d["hardening_pam_pwhistory_enforce_for_root"]))
check("blok yalniz remember > 0 iken calisir", "hardening_pam_pwhistory_remember | int > 0" in blk["when"])

prof = by["Write the pam-auth-update profile for pam_pwhistory"]["ansible.builtin.copy"]
c = prof["content"]
eq("profil yolu ve izin", ("/usr/share/pam-configs/hardening-pwhistory", "0644", "root"), (prof["dest"], prof["mode"], prof["owner"]))
check("profil: Name, Priority 512 (pwquality 1024 ile unix 256 ARASINDA), Password-Type Primary", "Name: " in c and re.search(r"^Priority: 512$", c, re.M) and "Password-Type: Primary" in c)
check("profil: hem Password hem Password-Initial, requisite + pam_pwhistory.so use_authtok", c.count("pam_pwhistory.so use_authtok") == 2 and "Password:\n" in c and "Password-Initial:\n" in c and all("requisite" in l for l in c.splitlines() if "pam_pwhistory.so" in l))
check("profil AUTH/ACCOUNT/SESSION yigininda DEGIL (giris yigina dokunmaz, kilitlenme riski yok)", not re.search(r"^(Auth|Account|Session)", c, re.M))
check("pam_pwhistory'ye enforce_for_root/remember komut satirinda GECMEZ (ayar dosyadan okunur)", "remember=" not in c and "enforce_for_root" not in c)
en = by["Enable the profile with pam-auth-update"]
check("pam-auth-update yalniz profil aktif DEGILKEN ve --check disinda", "hardening_pwhistory_active.rc != 0" in en["when"] and "not ansible_check_mode" in en["when"])
check("komut tam: pam-auth-update --package --enable hardening-pwhistory", en["ansible.builtin.command"] == "pam-auth-update --package --enable hardening-pwhistory")
asrt = by["Check that the password stack still has pwquality, pwhistory and unix, in that order"]
check("sira denetimi: pwquality, pwhistory, unix tam bu sirada (assert)", "pam_pwquality.so', 'pam_pwhistory.so', 'pam_unix.so'" in asrt["ansible.builtin.assert"]["that"][0])
resc = [t.get("name") for t in blk["rescue"]]
check("hata olursa rescue: profil geri alinir ve rol DURUR", resc == ["Take the profile out again after a failure", "Stop after the pam_pwhistory failure"] and "--remove hardening-pwhistory" in str(blk["rescue"][0]))
check("rescue: geri alma komutu basarisiz olsa BILE asil hata kaybolmaz (failed_when: false)", blk["rescue"][0].get("failed_when") is False)
for n in ("Read the generated password stack", "Look for pam_pwhistory in common-password"):
    check(f"{n}: --check'te de calisir", by[n].get("check_mode") is False)


def run_conf(tmp, remember, enforce):
    rem = dict(by["Set the number of remembered passwords"]["ansible.builtin.lineinfile"]); rem["path"] = str(Path(tmp) / "pwhistory.conf")
    en1 = by["Apply the history rule to root as well (optional)"]; en2 = by["Do not apply the history rule to root (only an active line is removed, the commented example stays)"]
    e1 = dict(en1["ansible.builtin.lineinfile"]); e1["path"] = rem["path"]
    e2 = dict(en2["ansible.builtin.lineinfile"]); e2["path"] = rem["path"]
    pb = Path(tmp) / "p.yml"
    pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False,
                                   "vars": {"hardening_pam_pwhistory_remember": remember, "hardening_pam_pwhistory_enforce_for_root": enforce},
                                   "tasks": [{"ansible.builtin.lineinfile": rem},
                                             {"ansible.builtin.lineinfile": e1, "when": en1["when"]},
                                             {"ansible.builtin.lineinfile": e2, "when": en2["when"]}]}]), encoding="utf-8")
    return subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                          env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})


with tempfile.TemporaryDirectory() as t:
    f = Path(t) / "pwhistory.conf"; f.write_text(CONF, encoding="utf-8")
    r = run_conf(t, 24, False)
    L = f.read_text(encoding="utf-8").splitlines()
    check("zincir 1: kosu basarili", r.returncode == 0, r.stdout[-300:])
    eq("   'remember = 24' yazildi, yorumlu '# remember = 10' yerine (tek satir)", (1, False), (sum(1 for l in L if re.match(r"^remember\s*=", l)), "# remember = 10" in L))
    check("   enforce_for_root KAPALI: yorumlu ornek '# enforce_for_root' KORUNDU, etkin satir yok", "# enforce_for_root" in L and "enforce_for_root" not in L)
    before = f.read_text(encoding="utf-8")
    r2 = run_conf(t, 24, False)
    check("   ikinci kosu changed=0 ve dosya ayni (idempotent)", "changed=0" in r2.stdout and f.read_text(encoding="utf-8") == before, r2.stdout[-200:])
    run_conf(t, 24, True)
    L = f.read_text(encoding="utf-8").splitlines()
    check("zincir 2: enforce_for_root ACIK: etkin 'enforce_for_root' satiri var, yorumlu ornek yerine", "enforce_for_root" in L and "# enforce_for_root" not in L)
    r3 = run_conf(t, 24, True)
    check("   tekrar: changed=0", "changed=0" in r3.stdout)
    run_conf(t, 12, False)
    L = f.read_text(encoding="utf-8").splitlines()
    check("zincir 3: enforce kapatilinca etkin satir silinir, remember 12 olur", "enforce_for_root" not in L and "remember = 12" in L and sum(1 for l in L if re.match(r"^remember\s*=", l)) == 1)

for k, want in (("hardening_pam_pwhistory_remember", ("int", 0, 0, 400)), ("hardening_pam_pwhistory_enforce_for_root", ("bool", False, None, None))):
    v = next(x for x in yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))["vars"] if isinstance(x, dict) and x["name"] == k)
    check(f"component.yml {k}: tur/varsayilan/aralik, warn_if yok", (v["type"], v["default"], v.get("min"), v.get("max")) == want and "warn_if" not in v, str(v))
sys.exit(1 if fails else 0)
