#!/usr/bin/env python3
"""Lynis son kalemler: Postfix SMTP banner (MAIL-8818, varsayılan AÇIK, yalnızca postfix kuruluysa) ve /proc hidepid=2 (FILE-6344, varsayılan KAPALI, warn_if).
Gerçek Ansible ile geçici dosyalar üzerinde denenir (mount/postconf/systemd çağrıları testte atlanır ya da sahtelenir)."""
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


# ---- postfix banner ----
bd = load("roles/hardening_base/defaults/main.yml")
check("postfix banner varsayilan ACIK", bd["hardening_postfix_banner"] is True)
bt = load("roles/hardening_base/tasks/main.yml")
by = {t["name"]: t for t in bt if isinstance(t, dict) and "name" in t}
st = by["Look for postfix"]
check("postfix aranir (stat), kapaliyken calismaz", st["ansible.builtin.stat"]["path"] == "/usr/sbin/postconf" and "hardening_postfix_banner" in w(st))
rd = by["Read the postfix SMTP banner (read-only)"]
check("mevcut banner SALT OKUNUR okunur (changed_when false, --check'te de)", rd["ansible.builtin.command"] == "postconf -h smtpd_banner" and rd.get("changed_when") is False and rd.get("check_mode") is False)
stb = by["Hide the software name in the postfix SMTP banner"]
check("banner `postconf -e` ile argv olarak yazilir ($ kabukta genisletilmez)", stb["ansible.builtin.command"]["argv"] == ["postconf", "-e", "smtpd_banner = $myhostname ESMTP"])
def ran(when, vars_):
    """Gorevin GERCEK `when` listesi Ansible'da degerlendirilir: debug gorevi calisti mi?"""
    rc_, out = play([{"ansible.builtin.debug": {"msg": "RAN_MARKER"}, "when": when}], vars_=vars_)
    return "RAN_MARKER" in out and "skipping" not in out.split("RAN_MARKER")[0].split("TASK")[-1], out


for banner, rc, installed, want in (("$myhostname ESMTP $mail_name (Debian)", 0, True, True), ("$myhostname ESMTP", 0, True, False), ("$myhostname ESMTP\n", 0, True, False), ("", 1, True, False), ("$myhostname ESMTP $mail_name", 0, False, False)):
    got, out = ran(stb["when"], {"hardening_postfix_banner": True, "hardening_postfix_postconf": {"stat": {"exists": installed}}, "hardening_postfix_banner_now": {"rc": rc, "stdout": banner}})
    check(f"banner={banner!r} rc={rc} postfix={installed} -> yazilir={want}", got == want, out[-200:])
check("yeniden yukleme yalniz degisince ve --check degilken, basarisizlik kosuyu durdurmaz", "hardening_postfix_banner_set is changed" in w(by["Reload postfix so the new banner is used"]) and by["Reload postfix so the new banner is used"].get("failed_when") is False)

# ---- hidepid ----
fd = load("roles/hardening_files/defaults/main.yml")
check("hidepid varsayilan KAPALI, grup proc, kullanici listesi bos", (fd["hardening_proc_hidepid"], fd["hardening_proc_hidepid_group"], fd["hardening_proc_hidepid_users"]) == (False, "proc", []))
ft = load("roles/hardening_files/tasks/main.yml")
blk = next(t for t in ft if t.get("name") == "Hide other users' processes in /proc (hidepid=2)")
check("blok yalniz hardening_proc_hidepid ile calisir", "hardening_proc_hidepid" in str(blk["when"]))
ib = {t["name"]: t for t in blk["block"]}
order = list(ib)
check("sira: grup -> kullanicilar -> logind drop-in -> yeniden baslat -> gid -> fstab -> mevcut secenekler -> yeniden bagla -> uyari",
      order == ["Create the group that may still see all processes", "Add the listed users to that group", "Make sure the systemd-logind drop-in directory exists", "Let systemd-logind see all processes (drop-in)", "Reload systemd and restart systemd-logind", "Find the group id",
                "Make the /proc mount options persistent (/etc/fstab)", "Read the current /proc mount options (read-only)", "Remount /proc with hidepid=2", "Warn that /proc could not be remounted"], str(order))
check("logind yeniden baslatmasi yeniden baglamadan ONCE (logind hidepid altinda gormez)", order.index("Reload systemd and restart systemd-logind") < order.index("Remount /proc with hidepid=2"))
check("grup sistem grubu, kullanicilar `append`", ib["Create the group that may still see all processes"]["ansible.builtin.group"]["system"] is True and ib["Add the listed users to that group"]["ansible.builtin.user"]["append"] is True)
dd = ib["Make sure the systemd-logind drop-in directory exists"]["ansible.builtin.file"]
check("drop-in dizini OLUSTURULUR (yoksa copy basarisiz olur: Colima'da gorulen hata), drop-in ondan sonra", dd["state"] == "directory" and dd["path"] == "/etc/systemd/system/systemd-logind.service.d" and order.index("Make sure the systemd-logind drop-in directory exists") < order.index("Let systemd-logind see all processes (drop-in)"))
dp = ib["Let systemd-logind see all processes (drop-in)"]["ansible.builtin.copy"]
check("logind drop-in: SupplementaryGroups=<grup>", dp["dest"] == "/etc/systemd/system/systemd-logind.service.d/60-hardening-hidepid.conf" and "SupplementaryGroups={{ hardening_proc_hidepid_group }}" in dp["content"])
rm = ib["Remount /proc with hidepid=2"]
check("yeniden baglama: hidepid=2 + gid; seceneklerde yoksa; basarisizlik kosuyu durdurmaz (uyarir)", "hidepid=2,gid=" in rm["ansible.builtin.command"] and "hidepid=(2|invisible)" in w(rm) and rm.get("failed_when") is False)
for opts, gid, want in (("rw,nosuid,nodev,noexec,relatime", "996", True), ("rw,nosuid,nodev,noexec,relatime,gid=996,hidepid=invisible", "996", False), ("rw,nosuid,nodev,noexec,relatime,gid=996,hidepid=2", "996", False),
                        ("rw,nosuid,nodev,noexec,relatime,gid=10,hidepid=invisible", "996", True), ("rw,nosuid,nodev,noexec,relatime,hidepid=1", "996", True)):
    got, out = ran(rm["when"], {"hardening_proc_hidepid_group": "proc", "hardening_proc_options": {"stdout": opts}, "ansible_facts": {"getent_group": {"proc": ["x", gid]}}})
    check(f"/proc secenekleri {opts[-34:]!r} gid={gid} -> yeniden baglanir={want}", got == want, out[-250:])
# fstab: gercek lineinfile
fl = ib["Make the /proc mount options persistent (/etc/fstab)"]
with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "fstab"
    f.write_text("UUID=abc / ext4 defaults 0 1\nproc /proc proc defaults 0 0\n# yorum\n", encoding="utf-8")
    t = dict(fl); t.pop("when", None); t["ansible.builtin.lineinfile"] = dict(fl["ansible.builtin.lineinfile"], path=str(f))
    pb_vars = {"hardening_proc_hidepid_group": "proc", "ansible_facts": {"getent_group": {"proc": ["x", "996"]}}}
    play([t], vars_=pb_vars); txt = f.read_text(encoding="utf-8")
    check("fstab: mevcut proc satiri DEGISTIRILIR (cogaltilmaz), digerleri korunur", txt.count("/proc") == 1 and "proc /proc proc defaults,hidepid=2,gid=996 0 0" in txt and "UUID=abc / ext4 defaults 0 1" in txt and "# yorum" in txt, txt)
    rc, out = play([t], vars_=pb_vars)
    check("fstab: ikinci kosu changed=0", "changed=0" in out, out[-150:])
    f.write_text("UUID=abc / ext4 defaults 0 1\n", encoding="utf-8"); play([t], vars_=pb_vars)
    check("fstab: proc satiri yoksa EKLENIR", "proc /proc proc defaults,hidepid=2,gid=996 0 0" in f.read_text(encoding="utf-8"))

cv = {v["name"]: v for v in load("component.yml")["vars"] if isinstance(v, dict)}
exp = {"hardening_postfix_banner": (True, False), "hardening_proc_hidepid": (False, True), "hardening_proc_hidepid_users": ([], False)}
for n, (d_, wi) in exp.items():
    v = cv.get(n)
    check(f"component.yml: {n} varsayilan {d_!r}, warn_if={wi}", v is not None and v["default"] == d_ and bool(v.get("warn_if")) == wi, str(v))
doc = (ROOT / "docs/component-vars.md").read_text(encoding="utf-8")
check("docs/component-vars.md bunlari icerir", all(f"`{n}`" in doc for n in exp))
print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
