#!/usr/bin/env python3
"""hardening_pam_faillock: hesap kilitleme (pam_faillock), varsayılan KAPALI. PAM'i değiştirdiği için en çok KORUMALAR sınanır:
güvenlik ağı kapalı/armed değilse rol DURUR; üretilen yığının SIRASI (preauth, pam_unix, authfail; account: faillock, unix) assert ile doğrulanır
(gerçek Ubuntu 26.04 `pam-auth-update` çıktısı ve bozuk varyantlar); hata olursa rescue geri almayı çağırır; ayar satırları gerçek faillock.conf üzerinde."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
fails = 0

GOOD_AUTH = """auth\trequisite    pam_faillock.so preauth
auth\t[success=2 default=ignore]\tpam_unix.so nullok try_first_pass
auth\t[default=die]    pam_faillock.so authfail
auth\trequisite\t\t\tpam_deny.so
auth\trequired\t\t\tpam_permit.so
auth\toptional\t\t\tpam_cap.so
"""
GOOD_ACCOUNT = """account\trequired    pam_faillock.so
account\t[success=1 new_authtok_reqd=done default=ignore]\tpam_unix.so
account\trequisite\t\t\tpam_deny.so
account\trequired\t\t\tpam_permit.so
"""
CONF = """# Configuration for locking the user after multiple failed authentication attempts.
#
# Enable the debugging logs.
# Enabled if option is present.
# audit
#
# The directory where the user files with the failure records are kept.
# The default is /var/run/faillock.
# dir = /var/run/faillock
#
# Deny access if the number of consecutive authentication failures
# for this user during the recent interval exceeds n.
# The default is 3.
# deny = 3
#
# The length of the interval during which the consecutive
# authentication failures must happen for the user account
# lock out is specified in seconds.
# The default is 900 (15 minutes).
# fail_interval = 900
#
# The access will be re-enabled after n seconds after the lock out.
# The default is 600 (10 minutes).
# unlock_time = 600
#
# Root account can become locked as well as regular accounts.
# Enabled if option is present.
# even_deny_root
#
# This option implies the even_deny_root option.
# root_unlock_time = 900
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


tasks = yaml.safe_load((ROOT / "roles/hardening_pam_faillock/tasks/main.yml").read_text(encoding="utf-8"))
d = yaml.safe_load((ROOT / "roles/hardening_pam_faillock/defaults/main.yml").read_text(encoding="utf-8"))
blk = tasks[0]
by = {t["name"]: t for t in blk["block"]}
eq("varsayilan KAPALI ve CIS degerleri", (False, 5, 900, 900, False), (d["hardening_pam_faillock"], d["hardening_pam_faillock_deny"], d["hardening_pam_faillock_unlock_time"], d["hardening_pam_faillock_fail_interval"], d["hardening_pam_faillock_even_deny_root"]))
check("blok yalniz hardening_pam_faillock=true iken calisir", "hardening_pam_faillock | bool" in blk["when"])
names = [t["name"] for t in blk["block"]]
check("sira: ayar dogrulama, GUVENLIK AGI kontrolleri, sonra yazma", names.index("Check the faillock settings") < names.index("Refuse to change PAM without the rollback safety net") < names.index("Refuse to change PAM when the safety net is not armed") < names.index("Write the faillock settings (deny, fail_interval, unlock_time)"))
check("PAM'e dokunan ILK gorev (profil yazma) tum korumalardan SONRA", names.index("Refuse to change PAM when the safety net is not armed") < names.index("Write the faillock profile that runs before pam_unix (preauth and account)") < names.index("Enable the profiles with pam-auth-update"))
check("guvenlik agi kapaliysa durur (hardening_rollback_enabled)", "hardening_rollback_enabled | bool" in str(by["Refuse to change PAM without the rollback safety net"]["ansible.builtin.assert"]["that"]))
check("armed degilse durur (status 'armed=yes')", "'armed=yes' in hardening_faillock_net.stdout" in str(by["Refuse to change PAM when the safety net is not armed"]["ansible.builtin.assert"]["that"]))
check("armed denetimi --check'te atlanir (betik calismaz)", "not ansible_check_mode" in by["Refuse to change PAM when the safety net is not armed"]["when"])
for n in ("Look for the faillock tool and module", "Look for pam_faillock in common-auth", "Read the generated auth and account stacks"):
    check(f"{n}: --check'te de calisir", by[n].get("check_mode") is False)
check("pam-auth-update yalniz faillock yokken ve --check disinda", "hardening_faillock_active.rc != 0" in by["Enable the profiles with pam-auth-update"]["when"] and "not ansible_check_mode" in by["Enable the profiles with pam-auth-update"]["when"])
check("iki profil birlikte etkinlestirilir", by["Enable the profiles with pam-auth-update"]["ansible.builtin.command"] == "pam-auth-update --package --enable hardening-faillock-preauth hardening-faillock-authfail")
p1 = by["Write the faillock profile that runs before pam_unix (preauth and account)"]["ansible.builtin.copy"]["content"]
p2 = by["Write the faillock profile that runs after pam_unix (authfail)"]["ansible.builtin.copy"]["content"]
check("preauth profili: Priority 512 (unix 256'dan ONCE), preauth + account, requisite/required", re.search(r"^Priority: 512$", p1, re.M) and p1.count("requisite    pam_faillock.so preauth") == 2 and p1.count("required    pam_faillock.so") == 2 and "Auth-Type: Primary" in p1 and "Account-Type: Primary" in p1)
check("authfail profili: Priority 128 (unix 256'dan SONRA), [default=die] authfail", re.search(r"^Priority: 128$", p2, re.M) and p2.count("[default=die]    pam_faillock.so authfail") == 2)
check("profiller session/password yiginina DOKUNMAZ", not re.search(r"^(Session|Password)", p1 + p2, re.M))
resc = [t["name"] for t in blk["rescue"]]
check("rescue: geri alma betigini CAGIRIR (hardening-rollback restore) ve rol DURUR", resc == ["Restore PAM from the rollback backup after a failure", "Stop after the faillock failure"] and blk["rescue"][0]["ansible.builtin.command"] == "/usr/local/sbin/hardening-rollback restore" and blk["rescue"][0].get("failed_when") is False)
probe = by["Check that privilege escalation still works"]
check("become denemesi var (id -u == 0)", probe.get("become") is True and "!= '0'" in probe["failed_when"])


def play(extra_tasks, vars_):
    with tempfile.TemporaryDirectory() as t:
        pb = Path(t) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": vars_, "tasks": extra_tasks}]), encoding="utf-8")
        return subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                              env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})


def order(auth, account):
    t = by["Check the order, preauth before pam_unix, authfail after it, account entry present"]
    r = play([{"ansible.builtin.set_fact": {"hardening_faillock_stacks": {"results": [{"content": __import__("base64").b64encode(auth.encode()).decode()}, {"content": __import__("base64").b64encode(account.encode()).decode()}]}}},
              {"ansible.builtin.assert": t["ansible.builtin.assert"]}], {})
    return r.returncode == 0


check("yigin sirasi: GERCEK Ubuntu 26.04 ciktisi KABUL edilir", order(GOOD_AUTH, GOOD_ACCOUNT))
check("   authfail pam_unix'ten ONCE: REDDEDILIR", not order(GOOD_AUTH.replace("auth\t[default=die]    pam_faillock.so authfail\n", "").replace("auth\trequisite    pam_faillock.so preauth\n", "auth\trequisite    pam_faillock.so preauth\nauth\t[default=die]    pam_faillock.so authfail\n"), GOOD_ACCOUNT))
check("   preauth YOK: REDDEDILIR", not order(GOOD_AUTH.replace("auth\trequisite    pam_faillock.so preauth\n", ""), GOOD_ACCOUNT))
check("   authfail YOK: REDDEDILIR", not order(GOOD_AUTH.replace("auth\t[default=die]    pam_faillock.so authfail\n", ""), GOOD_ACCOUNT))
check("   preauth pam_unix'ten SONRA: REDDEDILIR", not order("auth\t[success=1 default=ignore]\tpam_unix.so nullok\nauth\trequisite    pam_faillock.so preauth\nauth\t[default=die]    pam_faillock.so authfail\nauth\trequired\t\t\tpam_permit.so\n", GOOD_ACCOUNT))
check("   account'ta faillock YOK: REDDEDILIR", not order(GOOD_AUTH, GOOD_ACCOUNT.replace("account\trequired    pam_faillock.so\n", "")))
check("   account'ta faillock pam_unix'ten SONRA (basari sayacini sifirlamaz): REDDEDILIR", not order(GOOD_AUTH, "account\t[success=1 default=ignore]\tpam_unix.so\naccount\trequired    pam_faillock.so\naccount\trequired\t\t\tpam_permit.so\n"))
check("   faillock iki kez: REDDEDILIR", not order(GOOD_AUTH + "auth\trequisite    pam_faillock.so preauth\n", GOOD_ACCOUNT))


def conf_run(deny, interval, unlock, root, text=CONF):
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "faillock.conf"; f.write_text(text, encoding="utf-8")
        li = by["Write the faillock settings (deny, fail_interval, unlock_time)"]
        step = dict(li["ansible.builtin.lineinfile"]); step["path"] = str(f)
        e1 = by["Lock root as well (optional)"]; e2 = by["Do not lock root (only an active line is removed, the commented example stays)"]
        a = dict(e1["ansible.builtin.lineinfile"]); a["path"] = str(f)
        b = dict(e2["ansible.builtin.lineinfile"]); b["path"] = str(f)
        vars_ = {"hardening_pam_faillock_deny": deny, "hardening_pam_faillock_fail_interval": interval, "hardening_pam_faillock_unlock_time": unlock, "hardening_pam_faillock_even_deny_root": root}
        tasks_ = [{"ansible.builtin.lineinfile": step, "loop": li["loop"], "loop_control": li["loop_control"]},
                  {"ansible.builtin.lineinfile": a, "when": e1["when"]}, {"ansible.builtin.lineinfile": b, "when": e2["when"]}]
        r1 = play(tasks_, vars_)
        text1 = f.read_text(encoding="utf-8")
        r2 = play(tasks_, vars_)
        return r1.returncode == 0, text1, "changed=0" in r2.stdout and f.read_text(encoding="utf-8") == text1


ok, text1, idem = conf_run(5, 900, 900, False)
L = text1.splitlines()
check("faillock.conf: deny/fail_interval/unlock_time YAZILDI (yorumlu ornekler yerine, tek satir)", ok and "deny = 5" in L and "fail_interval = 900" in L and "unlock_time = 900" in L and not any(re.match(r"^# (deny|unlock_time|fail_interval) =", l) for l in L if l.startswith("# deny = 3") or l.startswith("# unlock_time = 600")))
check("   even_deny_root KAPALI: yorumlu ornek KORUNDU, etkin satir yok", "# even_deny_root" in L and "even_deny_root" not in L)
check("   ikinci kosu changed=0 (idempotent)", idem)
ok, text2, _ = conf_run(3, 600, 0, True)
L2 = text2.splitlines()
check("   deger degisimi: deny=3, unlock_time=0 (elle acilana dek), even_deny_root ACIK", "deny = 3" in L2 and "unlock_time = 0" in L2 and "even_deny_root" in L2 and "# even_deny_root" not in L2)

# ayar dogrulamasi (gercek assert)
asr = by["Check the faillock settings"]["ansible.builtin.assert"]
for name, v, good in (("deny=5", {"deny": 5, "unlock": 900, "interval": 900}, True), ("deny=0", {"deny": 0, "unlock": 900, "interval": 900}, False), ("deny=11", {"deny": 11, "unlock": 900, "interval": 900}, False),
                      ("unlock_time=0 (elle acilana dek)", {"deny": 5, "unlock": 0, "interval": 900}, True), ("unlock_time=-1", {"deny": 5, "unlock": -1, "interval": 900}, False),
                      ("unlock_time buyuk", {"deny": 5, "unlock": 604801, "interval": 900}, False), ("fail_interval=901 (CIS en cok 900)", {"deny": 5, "unlock": 900, "interval": 901}, False),
                      ("deny metin 'abc'", {"deny": "abc", "unlock": 900, "interval": 900}, False), ("deny enjeksiyon '5; rm'", {"deny": "5; rm", "unlock": 900, "interval": 900}, False)):
    r = play([{"ansible.builtin.assert": asr}], {"hardening_pam_faillock_deny": v["deny"], "hardening_pam_faillock_unlock_time": v["unlock"], "hardening_pam_faillock_fail_interval": v["interval"]})
    check(f"ayar dogrulama: {name} -> {'kabul' if good else 'RED'}", (r.returncode == 0) == good)

for k, want in (("hardening_pam_faillock", ("bool", False, True)), ("hardening_pam_faillock_even_deny_root", ("bool", False, True))):
    v = next(x for x in yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))["vars"] if isinstance(x, dict) and x["name"] == k)
    check(f"component.yml {k}: tur/varsayilan/warn_if", (v["type"], v["default"], v.get("warn_if")) == want, str(v))
sys.exit(1 if fails else 0)
