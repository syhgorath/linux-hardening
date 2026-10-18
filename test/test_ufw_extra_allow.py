#!/usr/bin/env python3
"""ufw ek kuralları: grup + sunucu listeleri BİRLEŞİR, geçersiz girdi ufw'ye ve ağır rollere dokunmadan reddedilir, iki doğrulayıcı aynı kalıbı kullanır.

Görevlerin kendi assert/set_fact ifadeleri gerçek `ansible-playbook` ile çalıştırılır (yalnızca metin aranmaz). Ansible liste değişkenlerini birleştirmez, ezer;
bu yüzden sunucuya özel kurallar için ayrı değişken var (hardening_ufw_extra_allow_host).
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
fails = 0


def check(name, want, got):
    global fails
    if want == got:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}: beklenen={want!r} gercek={got!r}")


def load(p):
    return yaml.safe_load((ROOT / p).read_text(encoding="utf-8"))


def task(role, file, name):
    for t in load(f"roles/{role}/tasks/{file}"):
        if t.get("name") == name:
            return t
    raise SystemExit(f"görev yok: {name}")


def play(tasks, vars_):
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": vars_, "tasks": tasks}], allow_unicode=True), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


ufw_d = load("roles/hardening_ufw/defaults/main.yml")
pre_d = load("roles/hardening_preflight/defaults/main.yml")
check("varsayilan: extra_allow ve extra_allow_host BOS liste", ([], []), (ufw_d["hardening_ufw_extra_allow"], ufw_d["hardening_ufw_extra_allow_host"]))
check("iki dogrulayici AYNI kalibi kullanir (ufw rolu ve preflight)", ufw_d["hardening_ufw_extra_allow_pattern"], pre_d["hardening_preflight_extra_allow_pattern"])

VALID = ["443/tcp", "80", "8000:8010/tcp", "53/udp", "from 192.0.2.5 to any port 6379 proto tcp", "from 198.51.100.0/24 to any port 80 proto tcp",
         "from 2001:db8::/32 to any port 6379 proto tcp", "from any to any port 443 proto tcp"]
INVALID = ["443/tpc", "22; rm -rf /", "allow 443", "443 from 192.0.2.5", "", "from 192.0.2.5 to any port 6379", "from 192.0.2.5 to 10.0.0.1 port 6379 proto tcp",
           "443/tcp comment 'x'", "deny 23", "-", "from  to any port 80 proto tcp", "$(id)", "80/tcp\n443/tcp", "443/sctp"]

assert_ufw = task("hardening_ufw", "main.yml", "Validate extra ufw rules")
combine = task("hardening_ufw", "main.yml", "Combine extra ufw rules (group + host)")
assert_pre = task("hardening_preflight", "access.yml", "Extra ufw rules must have a valid format (daha roller çalışmadan)")
base_vars = {"hardening_ufw_extra_allow": [], "hardening_ufw_extra_allow_host": [], "hardening_ufw_extra_allow_pattern": ufw_d["hardening_ufw_extra_allow_pattern"],
             "hardening_preflight_extra_allow_pattern": pre_d["hardening_preflight_extra_allow_pattern"]}

for label, tasks in (("ufw rolu", [combine, assert_ufw]), ("preflight", [assert_pre])):
    for rule in VALID:
        rc, _ = play([{k: v for k, v in t.items()} for t in tasks], {**base_vars, "hardening_ufw_extra_allow": [rule]})
        check(f"{label}: gecerli kabul: {rule!r}", 0, rc)
    for rule in INVALID:
        rc, _ = play([{k: v for k, v in t.items()} for t in tasks], {**base_vars, "hardening_ufw_extra_allow": [rule]})
        check(f"{label}: gecersiz REDDEDILIR: {rule!r}", True, rc != 0)
    rc, _ = play(tasks, {**base_vars, "hardening_ufw_extra_allow": ["443/tcp"], "hardening_ufw_extra_allow_host": ["bozuk"]})
    check(f"{label}: sunucuya ozel listedeki gecersiz kural da reddedilir", True, rc != 0)
    rc, _ = play(tasks, {**base_vars, "hardening_ufw_extra_allow": "443/tcp"})
    check(f"{label}: liste yerine METIN verilirse reddedilir", True, rc != 0)

# birleştirme
rc, out = play([combine, {"ansible.builtin.debug": {"msg": "ALL={{ hardening_ufw_extra_allow_all | to_json | b64encode }}"}}],
               {**base_vars, "hardening_ufw_extra_allow": ["443/tcp", "80/tcp"], "hardening_ufw_extra_allow_host": ["from 192.0.2.5 to any port 6379 proto tcp", "443/tcp"]})
got = None
for line in out.splitlines():
    if "ALL=" in line:
        got = json.loads(base64.b64decode(line.split("ALL=", 1)[1].strip().rstrip('",')).decode())
check("grup + sunucu listeleri BIRLESIR, tekrar atilir, sira korunur", ["443/tcp", "80/tcp", "from 192.0.2.5 to any port 6379 proto tcp"], got)
rc, out = play([combine, {"ansible.builtin.debug": {"msg": "ALL={{ hardening_ufw_extra_allow_all | to_json | b64encode }}"}}], {**base_vars, "hardening_ufw_extra_allow_host": ["8080/tcp"]})
got2 = None
for line in out.splitlines():
    if "ALL=" in line:
        got2 = json.loads(base64.b64decode(line.split("ALL=", 1)[1].strip().rstrip('",')).decode())
check("yalniz sunucu listesi verilirse o gecerli", ["8080/tcp"], got2)

# bağlantılar: ufw kuralları, eski-kural koruması ve doğrulama hep BİRLEŞİK listeyi kullanır
text = (ROOT / "roles/hardening_ufw/tasks/main.yml").read_text(encoding="utf-8")
check("kurallar birlesik listeden yazilir", True, 'loop: "{{ hardening_ufw_extra_allow_all }}"' in text)
check("eski-kural korumasi (prune) BIRLESIK listeyi gorur (2 yer)", 2, text.count("'extra_allow': hardening_ufw_extra_allow_all,"))
check("ufw'ye dokunan hicbir gorev ham hardening_ufw_extra_allow kullanmaz", True, "loop: \"{{ hardening_ufw_extra_allow }}\"" not in text and "'extra_allow': hardening_ufw_extra_allow," not in text)
names = [t.get("name") for t in load("roles/hardening_ufw/tasks/main.yml")]
check("dogrulama, ufw kurulumundan ve kural yazmadan ONCE", True, names.index("Validate extra ufw rules") < names.index("Install ufw") < names.index("Allow extra ports"))
comp = load("component.yml")
v = next((x for x in comp["vars"] if isinstance(x, dict) and x["name"] == "hardening_ufw_extra_allow"), None)
check("component.yml: hardening_ufw_extra_allow list[string], varsayilan []", True, bool(v) and v["type"] == "list[string]" and v["default"] == [])

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
