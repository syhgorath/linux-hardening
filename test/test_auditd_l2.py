#!/usr/bin/env python3
"""hardening_auditd: CIS Level 2 kural üreticisi (`audit_l2_rules.py`) ve görev bağlantısı. Üretici yalnızca metin üretir; seçenek varsayılan KAPALI; `-e 2` yok;
60-hardening.rules'taki kurallar tekrarlanmaz; var olmayan yola kural yazılmaz; 32 bit kuralları yalnızca 32 bit arayüzü olan mimaride."""
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "roles/hardening_auditd/files/audit_l2_rules.py"
fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail}")


def run(cfg):
    arg = cfg if isinstance(cfg, str) else json.dumps(cfg)
    r = subprocess.run([sys.executable, str(SCRIPT), arg], capture_output=True, text=True)
    return json.loads(r.stdout)


PATHS = ["/etc/issue", "/etc/hosts", "/etc/pam.d/", "/var/log/wtmp", "/usr/bin/kmod", "/usr/sbin/usermod", "/usr/bin/chcon", "/var/log/sudo.log", "/etc/apparmor.d/"]
X86 = {"arch": "x86_64", "has_b32": True, "paths": PATHS, "sudo_logfile": "/var/log/sudo.log", "priv": ["/usr/bin/su", "/usr/bin/passwd"]}
r = run(X86)["rules"]
lines = [l for l in r.splitlines() if l and not l.startswith("#")]

check("-c (hata olsa da yuklemeye devam, 6.2.3.34) var, ilk kural satiri", lines[0] == "-c")
check("-e 2 (degistirilemez yapilandirma) YOK", not any(re.match(r"^-e\b", l) for l in lines))
check("her kural satiri gecerli bicimde (-a always,exit / -w / -c)", all(re.match(r"^(-c|-a always,exit .+ -k \S+|-w \S+ -p [rwxa]+ -k \S+)$", l) for l in lines), [l for l in lines if not re.match(r"^(-c|-a always,exit .+ -k \S+|-w \S+ -p [rwxa]+ -k \S+)$", l)][:3])
check("kural satirlari tekrarsiz (auditctl 'Rule exists' demesin)", len(lines) == len(set(lines)))
dup60 = (ROOT / "roles/hardening_auditd/templates/hardening.rules.j2").read_text(encoding="utf-8")
l60 = {l.strip() for l in dup60.splitlines() if l.strip() and not l.startswith(("#", "{"))}
check("60-hardening.rules'taki hicbir kural tekrar yazilmaz", not (set(lines) & l60), sorted(set(lines) & l60)[:3])
check("var olmayan yola kural YOK (/etc/networks, /etc/netplan/, /var/log/btmp...)", all(p not in r for p in ("/etc/networks", "/etc/netplan", "/var/log/btmp", "/etc/security/opasswd", "/var/log/faillog")))
check("var olan yollar izlenir (issue, hosts, pam.d, wtmp, kmod, apparmor.d)", all(f"-w {p} " in r for p in ("/etc/issue", "/etc/hosts", "/etc/pam.d/", "/var/log/wtmp", "/usr/bin/kmod", "/etc/apparmor.d/")))
check("sudo gunlugu izlenir (sudo_log_file)", "-w /var/log/sudo.log -p wa -k sudo_log_file" in r)
check("sudo gunlugu yok -> kural yok", "sudo_log_file" not in run({**X86, "paths": [p for p in PATHS if p != "/var/log/sudo.log"]})["rules"])
check("ayricalikli komutlar siralanmis ve auid filtreli", "-F path=/usr/bin/passwd -F perm=x -F auid>=1000 -F auid!=unset -k privileged" in r and r.index("/usr/bin/passwd") < r.index("/usr/bin/su"))
check("x86_64: hem b64 hem b32 kurallari", "arch=b64 -S chmod" in r and "arch=b32 -S chmod" in r and "arch=b32 -S adjtimex,settimeofday,clock_settime" in r and "arch=b32 -S init_module" in r)
a64 = run({**X86, "arch": "aarch64", "has_b32": False})["rules"]
check("aarch64 (32 bit arayuzu yok): b32 kurali HIC yok", "b32" not in a64 and "arch=b64 -S chmod" in a64)
check("basarisiz erisim: EACCES ve EPERM ayri kurallar", "-F exit=-EACCES" in r and "-F exit=-EPERM" in r)
check("kullanici kaynakli kurallar auid>=1000 ve unset haric", "-S mount -F auid>=1000 -F auid!=unset -k mounts" in r and "-k delete" in r and "-k perm_mod" in r)
check("user_emulation: auid unset haric", "-C euid!=uid -F auid!=unset -k user_emulation" in r)
check("usermod/chcon komut kurallari yalnizca var olan araclar icin", "path=/usr/sbin/usermod" in r and "path=/usr/bin/chcon" in r and "setfacl" not in r)
check("guvenli olmayan yol (bosluk, ';', '..' disi karakter) atlanir", "evil" not in run({**X86, "priv": ["/tmp/a; rm -rf /", "/usr/bin/ok"], "paths": PATHS + ["/etc/ev il"]})["rules"] and "rm -rf" not in run({**X86, "priv": ["/tmp/a; rm -rf /"]})["rules"])
check("sayac dogru", run(X86)["count"] == len(lines))
check("bozuk girdi cokmez", run("{bozuk")["rules"] == "" and run("[1]")["rules"] == "")

# ---- gorev baglantisi ----
tasks = yaml.safe_load((ROOT / "roles/hardening_auditd/tasks/main.yml").read_text(encoding="utf-8"))
names = [t.get("name") for t in tasks]
blk = next(t for t in tasks if t.get("name") == "CIS Level 2 audit rules and file permissions")
check("blok yalniz hardening_auditd_cis_l2=true iken", blk["when"] == "hardening_auditd_cis_l2 | bool")
d = yaml.safe_load((ROOT / "roles/hardening_auditd/defaults/main.yml").read_text(encoding="utf-8"))
check("hardening_auditd_cis_l2 varsayilan KAPALI", d["hardening_auditd_cis_l2"] is False)
check("aday yollar listesi var ve mutlak", all(p.startswith("/") for p in d["hardening_auditd_l2_candidates"]))
rm = next(t for t in tasks if t.get("name") == "Remove the Level 2 audit rules (option off)")
check("kapaliyken kural dosyasi silinir", rm["ansible.builtin.file"]["state"] == "absent" and "not (hardening_auditd_cis_l2 | bool)" in rm["when"])
load = next(t for t in tasks if t.get("name") == "Load audit rules")
check("kurallar L2 dosyasi degisince / silinince YENIDEN yuklenir", "hardening_auditd_l2_file is changed" in load["when"] and "hardening_auditd_l2_removed is changed" in load["when"])
check("L2 bloku, kural yuklemeden ONCE", names.index("CIS Level 2 audit rules and file permissions") < names.index("Load audit rules"))
write = next(t for t in blk["block"] if t.get("name") == "Write the Level 2 audit rules")
check("L2 dosyasi 61-hardening-cis-l2.rules, 0640 root", write["ansible.builtin.copy"]["dest"].endswith("61-hardening-cis-l2.rules") and write["ansible.builtin.copy"]["mode"] == "0640")
reads = [t for t in blk["block"] if "ansible.builtin.command" in t or "ansible.builtin.shell" in t or "ansible.builtin.script" in t or "ansible.builtin.stat" in t or "ansible.builtin.find" in t]
check("okuma/uretme gorevleri --check'te de calisir (check_mode: false)", all(t.get("check_mode") is False for t in reads))
perm_tasks = [t for t in blk["block"] if "ansible.builtin.file" in t]
check("izin gorevleri yalnizca KALDIRIR (sembolik mod, rakam yok)", all(re.fullmatch(r"[ugo,]+-[rwx]+(,[ugo]+-[rwx]+)*", t["ansible.builtin.file"]["mode"]) for t in perm_tasks), [t["ansible.builtin.file"]["mode"] for t in perm_tasks])
cj = yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))
v = next((x for x in cj["vars"] if x["name"] == "hardening_auditd_cis_l2"), None)
check("component.yml: hardening_auditd_cis_l2 bool, false, warn_if true", bool(v) and v["type"] == "bool" and v["default"] is False and v.get("warn_if") is True)

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
