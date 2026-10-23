#!/usr/bin/env python3
"""ufw'nin kendi /etc/ufw/sysctl.conf dosyası log_martians=0 yazar ve sysctl.d'deki 1'i (CIS 3.3.1) ufw etkinken eziyordu (gerçek Ubuntu VM'inde Lynis KRNL-6000 ile görüldü).
Rol bu dosyayı hizalar ve canlı değeri düzeltir; hardening_ufw_log_martians=false ile kapanır."""
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


tasks = load("roles/hardening_ufw/tasks/main.yml")
by = {t["name"]: t for t in tasks if isinstance(t, dict) and "name" in t}
names = [t.get("name") for t in tasks if isinstance(t, dict)]
check("varsayilan: hardening_ufw_log_martians ACIK", load("roles/hardening_ufw/defaults/main.yml")["hardening_ufw_log_martians"] is True)
lf_t = by.get("Keep log_martians=1 in ufw's own sysctl file (CIS 3.3.1)", {})
lf = lf_t.get("ansible.builtin.lineinfile", {})
check("lineinfile: /etc/ufw/sysctl.conf, all ve default, create YOK", lf.get("path") == "/etc/ufw/sysctl.conf" and lf_t.get("loop") == ["all", "default"] and not lf.get("create"))
check("satir: net/ipv4/conf/<ag>/log_martians=1", "log_martians=1" in lf.get("line", "") and "log_martians=" in lf.get("regexp", ""))
check("kendi degiskeniyle kapanir; --check + yeni ufw kurulumu iken atlanir", "hardening_ufw_log_martians" in str(lf_t.get("when")) and "ansible_check_mode" in str(lf_t.get("when")) and "hardening_ufw_installed" in str(lf_t.get("when")))
live = by.get("Read the live log_martians values", {})
check("canli deger SALT OKUNUR okunur (changed_when false, --check'te de)", live.get("changed_when") is False and live.get("check_mode") is False)
setv = by.get("Set the live log_martians values", {})
check("canli deger yalniz 1 degilse ve --check degilken yazilir", "ansible_check_mode" in str(setv.get("when")) and "!= '1'" in str(setv.get("when")) and "sysctl -w" in str(setv.get("ansible.builtin.command")))
check("duzeltme, ufw'nin ENABLE gorevinden SONRA (ufw baslarken dosyayi uygular)", names.index("Keep log_martians=1 in ufw's own sysctl file (CIS 3.3.1)") > names.index("Enable ufw"))

# gercek lineinfile: ufw paketinin dosyasi (log_martians=0) -> 1, ikinci kosu changed=0, kullanicinin baska satirlarina dokunulmaz
with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "sysctl.conf"
    f.write_text("# ufw\nnet/ipv4/icmp_echo_ignore_broadcasts=1\nnet/ipv4/conf/all/log_martians=0\nnet/ipv4/conf/default/log_martians=0\nnet/ipv4/icmp_echo_ignore_all=0\n", encoding="utf-8")
    t = dict(lf_t); t.pop("when", None); t["ansible.builtin.lineinfile"] = dict(lf, path=str(f))
    pb = Path(d) / "p.yml"
    pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "tasks": [t]}]), encoding="utf-8")
    run = lambda: subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL, env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    r1 = run()
    txt = f.read_text(encoding="utf-8")
    check("log_martians=0 -> 1 (all ve default)", "conf/all/log_martians=1" in txt and "conf/default/log_martians=1" in txt and "log_martians=0" not in txt, txt)
    check("baska satirlar KORUNUR", "icmp_echo_ignore_broadcasts=1" in txt and "icmp_echo_ignore_all=0" in txt)
    r2 = run()
    check("ikinci kosu changed=0", "changed=0" in r2.stdout, r2.stdout[-200:])

comp = load("component.yml")
cv = {v["name"]: v for v in comp["vars"] if isinstance(v, dict)}
check("component.yml: hardening_ufw_log_martians bool, varsayilan true, warn_if YOK", cv["hardening_ufw_log_martians"]["default"] is True and "warn_if" not in cv["hardening_ufw_log_martians"])
check("component.yml: hardening_kernel_modules_disabled bool, varsayilan false, warn_if true", cv["hardening_kernel_modules_disabled"]["default"] is False and cv["hardening_kernel_modules_disabled"].get("warn_if") is True)
check("rol varsayilani = component.yml (modules_disabled)", load("roles/hardening_kernel/defaults/main.yml")["hardening_kernel_modules_disabled"] is False)

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
