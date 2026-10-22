#!/usr/bin/env python3
"""CIS kalan Level 1 maddeleri, varsayılan KAPALI seçenekler: pwquality (5.3.3.2.1, .5, .8), journald döndürme (6.1.1.1.5), sshd erişim listeleri (5.1.5) ve SALT OKUNUR rapor rolü.

Gerçek `ansible-playbook` ile (yerel): şablon çıktıları, doğrulama (assert) görevleri ve kendi erişimini kesen listenin REDDİ."""
import getpass
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


def ansible(tasks, extra_vars, hosts_vars=None):
    with tempfile.TemporaryDirectory() as t:
        pb = Path(t) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": extra_vars, "tasks": tasks}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg"), "ANSIBLE_ROLES_PATH": str(ROOT / "roles")})
        return r.returncode, r.stdout + r.stderr


def load(rel):
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def render(template_rel, vars_):
    tpl = (ROOT / template_rel).read_text(encoding="utf-8")
    rc, out = ansible([{"ansible.builtin.debug": {"msg": "OUT<<{{ tpl | b64encode }}>>"}, "vars": {"tpl": ""}}], {})
    # sablonu dogrudan template modulu ile uret
    with tempfile.TemporaryDirectory() as t:
        src = Path(t) / "x.j2"
        src.write_text(tpl, encoding="utf-8")
        dst = Path(t) / "x.out"
        rc, out = ansible([{"ansible.builtin.template": {"src": str(src), "dest": str(dst)}}], vars_)
        return dst.read_text(encoding="utf-8") if dst.exists() else "ERR:" + out[-300:]


# ---- pwquality ----
base = {"hardening_pwquality_minlen": 14, "hardening_pwquality_difok": 0, "hardening_pwquality_maxsequence": 0, "hardening_pwquality_enforce_for_root": False}
t = render("roles/hardening_auth/templates/pwquality.conf.j2", base)
check("pwquality varsayilan: difok/maxsequence/enforce_for_root YAZILMAZ (davranis degismez)", "difok" not in t and "maxsequence" not in t and "enforce_for_root" not in t and "minlen = 14" in t, t)
t = render("roles/hardening_auth/templates/pwquality.conf.j2", {**base, "hardening_pwquality_difok": 3, "hardening_pwquality_maxsequence": 3, "hardening_pwquality_enforce_for_root": True})
check("pwquality acik: difok = 3, maxsequence = 3, enforce_for_root", "difok = 3" in t and "maxsequence = 3" in t and "\nenforce_for_root\n" in t, t)
d = load("roles/hardening_auth/defaults/main.yml")
check("pwquality varsayilanlari 0/0/false", (d["hardening_pwquality_difok"], d["hardening_pwquality_maxsequence"], d["hardening_pwquality_enforce_for_root"]) == (0, 0, False))
auth = load("roles/hardening_auth/tasks/main.yml")
av = next(x for x in auth if x.get("name") == "Validate the pwquality options")
for label, v, ok in (("gecerli", {"hardening_pwquality_difok": 2, "hardening_pwquality_maxsequence": 3, "hardening_pwquality_enforce_for_root": True}, True),
                     ("difok 33", {"hardening_pwquality_difok": 33}, False), ("difok -1", {"hardening_pwquality_difok": -1}, False), ("difok 'x'", {"hardening_pwquality_difok": "x"}, False),
                     ("maxsequence 11", {"hardening_pwquality_maxsequence": 11}, False), ("enforce_for_root 'evet'", {"hardening_pwquality_enforce_for_root": "evet"}, False)):
    rc, out = ansible([av], {**base, **v})
    check(f"pwquality dogrulama: {label} -> {'gecer' if ok else 'REDDEDILIR'}", (rc == 0) == ok, out[-200:])

# ---- journald ----
bt = load("roles/hardening_base/tasks/main.yml")
jv = next(x for x in bt if x.get("name") == "Validate the journald rotation settings")
jd = load("roles/hardening_base/defaults/main.yml")
check("journald varsayilan KAPALI, CIS degerleri 1G/200M/1month", (jd["hardening_journald_rotation"], jd["hardening_journald_system_max_use"], jd["hardening_journald_runtime_max_use"], jd["hardening_journald_max_file_sec"]) == (False, "1G", "200M", "1month"))
jb = {k: v for k, v in jd.items() if k.startswith("hardening_journald")}
for label, v, ok in (("varsayilan", {}, True), ("512M", {"hardening_journald_system_max_use": "512M"}, True), ("2week", {"hardening_journald_max_file_sec": "2week"}, True),
                     ("1GB", {"hardening_journald_system_max_use": "1GB"}, False), ("sinirsiz", {"hardening_journald_system_max_use": "infinity"}, False),
                     ("1 month", {"hardening_journald_max_file_sec": "1 month"}, False), ("rotation 'evet'", {"hardening_journald_rotation": "evet"}, False)):
    rc, out = ansible([jv], {**jb, **v})
    check(f"journald dogrulama: {label} -> {'gecer' if ok else 'REDDEDILIR'}", (rc == 0) == ok, out[-200:])
w = next(x for x in bt if x.get("name") == "Write journald rotation limits")
rm = next(x for x in bt if x.get("name") == "Remove journald rotation limits (this role's file)")
check("yazma yalniz rotation=true; silme yalniz false; ikisi de journald'i yeniden baslatir", "hardening_journald_rotation | bool" in w["when"] and "not (hardening_journald_rotation | bool)" in rm["when"] and w["notify"] == rm["notify"] == "Restart journald")
check("ayri dosya (61-hardening-rotation.conf), 60'a dokunmaz", w["ansible.builtin.copy"]["dest"].endswith("61-hardening-rotation.conf") and rm["ansible.builtin.file"]["path"].endswith("61-hardening-rotation.conf"))
c = w["ansible.builtin.copy"]["content"]
rc, out = ansible([{"ansible.builtin.debug": {"msg": "ICERIK<<" + c + ">>"}}], jb)
check("journald dosya icerigi: SystemMaxUse=1G, RuntimeMaxUse=200M, MaxFileSec=1month", all(x in out for x in ("SystemMaxUse=1G", "RuntimeMaxUse=200M", "MaxFileSec=1month")), out[-300:])

# ---- sshd erisim listeleri ----
sd = load("roles/hardening_ssh/defaults/main.yml")
check("ssh erisim listeleri varsayilan BOS (kisit yok)", sd["hardening_ssh_allow_users"] == [] and sd["hardening_ssh_allow_groups"] == [])
sb = {"hardening_ssh_permit_root_login": "no", "hardening_ssh_disable_password": True, "hardening_ssh_kbdinteractive": False, "hardening_ssh_allow_tcp_forwarding": "no",
      "hardening_ssh_allow_users": [], "hardening_ssh_allow_groups": []}
t = render("roles/hardening_ssh/templates/sshd-hardening.conf.j2", sb)
check("ssh sablon varsayilan: AllowUsers/AllowGroups YAZILMAZ", "AllowUsers" not in t and "AllowGroups" not in t, t)
t = render("roles/hardening_ssh/templates/sshd-hardening.conf.j2", {**sb, "hardening_ssh_allow_users": ["ali", "veli"], "hardening_ssh_allow_groups": ["ssh-users"]})
check("ssh sablon: AllowUsers ali veli ve AllowGroups ssh-users", "AllowUsers ali veli\n" in t and "AllowGroups ssh-users\n" in t, t)
st = load("roles/hardening_ssh/tasks/main.yml")
sv = next(x for x in st if x.get("name") == "Validate the SSH access lists (CIS 5.1.5)")
who = next(x for x in st if x.get("name") == "Login user and groups for the access lists (become olmadan)")
ref = next(x for x in st if x.get("name") == "Refuse access lists that would lock out the login user")
me = getpass.getuser()
for label, v, ok in (("bos", {}, True), ("basit adlar", {"hardening_ssh_allow_users": ["ali", "svc_x", "a-b", "host$"]}, True),
                     ("joker", {"hardening_ssh_allow_users": ["a*"]}, False), ("@ ile", {"hardening_ssh_allow_users": ["ali@10.0.0.1"]}, False),
                     ("buyuk harf", {"hardening_ssh_allow_groups": ["Admins"]}, False), ("string", {"hardening_ssh_allow_users": "ali"}, False)):
    rc, out = ansible([sv], {**sb, **v})
    check(f"ssh liste dogrulama: {label} -> {'gecer' if ok else 'REDDEDILIR'}", (rc == 0) == ok, out[-200:])
rc, out = ansible([who, ref], {**sb, "hardening_ssh_allow_users": ["baskasi"]})
check("giris kullanicisi listede DEGIL -> DURUR (erisim kesilmez)", rc != 0 and "yazılmadı" in out, out[-300:])
rc, out = ansible([who, ref], {**sb, "hardening_ssh_allow_users": [me]})
check("giris kullanicisi listede -> gecer", rc == 0, out[-300:])
rc, out = ansible([who, ref], {**sb, "hardening_ssh_allow_groups": ["yok-boyle-grup"]})
check("giris kullanicisi izinli grupta DEGIL -> DURUR", rc != 0, out[-300:])
grp = subprocess.run(["id", "-gn"], capture_output=True, text=True).stdout.strip()
rc, out = ansible([who, ref], {**sb, "hardening_ssh_allow_groups": [grp]})
check("giris kullanicisi izinli grupta -> gecer", rc == 0, out[-300:])
rc, out = ansible([who, ref], {**sb, "hardening_ssh_allow_users": [me], "hardening_ssh_allow_groups": ["yok-boyle-grup"]})
check("ikisi dolu (VE): kullanici listede ama grup degil -> DURUR", rc != 0, out[-300:])
rc, out = ansible([who, ref], sb)
check("listeler bos -> kontrol hic calismaz (atlanir)", rc == 0 and "skipping" in out, out[-200:])
names = [x.get("name") for x in st]
check("liste dogrulamasi ve kilitlenme korumasi drop-in yazmadan ONCE", names.index("Refuse access lists that would lock out the login user") < names.index("Write sshd drop-in (00- oneki: cloud-init drop-in dosyasindan once okunur)"))

# ---- rapor rolu ----
rt = load("roles/hardening_report/tasks/main.yml")
inner = rt[0]["block"]
mods = {next(k for k in x if k.startswith("ansible.builtin.")) for x in inner}
check("rapor rolu yalniz okuma/degerlendirme modulleri (shell, script, set_fact, debug)", mods <= {"ansible.builtin.shell", "ansible.builtin.script", "ansible.builtin.set_fact", "ansible.builtin.debug"}, str(mods))
reads = [x for x in inner if "ansible.builtin.shell" in x or "ansible.builtin.script" in x]
check("tum okumalar --check'te de calisir ve degisiklik saymaz", all(x.get("check_mode") is False and x.get("changed_when") is False for x in reads))
cmds = " ".join(x["ansible.builtin.shell"]["cmd"] for x in inner if "ansible.builtin.shell" in x)
import re
check("yazan/degistiren komut yok (rm, mv, cp, chmod, chown, tee, sed -i, yonlendirme, systemctl, apt)", not re.search(r"\b(rm|mv|cp|chmod|chown|tee|systemctl|apt|apt-get|usermod)\b|(?<!getent )\bpasswd\b|sed -i|(?<![=\s2&])>(?!=)|(?<=\s)>(?!=)\s*[/\w$\"]", cmds.replace("2>/dev/null", "").replace(">/dev/null", "")), cmds[:200])
rd = load("roles/hardening_report/defaults/main.yml")
check("rapor varsayilan ACIK, onayli dinleyici listesi bos", rd["hardening_report"] is True and rd["hardening_approved_listeners"] == [])
hy = (ROOT / "playbooks/harden.yml").read_text(encoding="utf-8")
check("harden.yml rapor rolunu `report` etiketiyle calistirir, ufw/ssh'tan ONCE", "{ role: hardening_report, tags: [report] }" in hy and hy.index("hardening_report") < hy.index("role: hardening_ufw"))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
