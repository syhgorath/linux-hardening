#!/usr/bin/env python3
"""Rol görevlerindeki GERÇEK Jinja ifadelerini (YAML'dan çıkarılıp Ansible ile değerlendirilir) örnek girdilerle sınar.

- hardening_ufw: sshd'nin dinlediği portların `ss` çıktısından türetilmesi (PR-0b)
- hardening_fail2ban: efektif ignoreip (PR-0d)
"""
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


def task_expr(path, task_prefix, fact):
    tasks = yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))
    for t in tasks:
        if str(t.get("name", "")).startswith(task_prefix):
            return t["ansible.builtin.set_fact"][fact]
    raise SystemExit(f"görev bulunamadı: {task_prefix}")


def run_cases(cases):
    """cases: [(ad, {girdi_degiskenleri}, ifade, sonuc_degiskeni)] -> {ad: deger}
    Sonuçlar stdout'tan değil, görevlerin yazdığı dosyalardan okunur (çıktı biçimine bağımlı olmasın)."""
    with tempfile.TemporaryDirectory() as d:
        tasks = []
        for i, (name, inputs, expr, var) in enumerate(cases):
            tasks.append({"ansible.builtin.set_fact": inputs})
            tasks.append({"ansible.builtin.set_fact": {var: expr}})
            tasks.append({"ansible.builtin.copy": {"dest": f"{d}/{i}.json", "content": "{{ " + var + " | to_json }}"}})
        play = [{"hosts": "localhost", "connection": "local", "gather_facts": False, "tasks": tasks}]
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump(play, allow_unicode=True), encoding="utf-8")
        r = subprocess.run(
            ["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
            env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")},
        )
        res = {}
        for i, (name, *_rest) in enumerate(cases):
            f = Path(d) / f"{i}.json"
            if f.exists():
                res[name] = json.loads(f.read_text(encoding="utf-8"))
        if r.returncode != 0:
            print(r.stdout + r.stderr)
    return res


# ---- 0b: sshd portlari ----
ports_expr = task_expr("roles/hardening_ufw/tasks/main.yml", "Derive SSH ports", "hardening_ufw_ssh_ports")
ss = lambda *lines: {"hardening_ufw_ss": {"stdout_lines": list(lines)}}  # noqa: E731
L_22_4 = 'LISTEN 0      4096           0.0.0.0:22         0.0.0.0:*    users:(("sshd",pid=1456,fd=3),("systemd",pid=1,fd=201))'
L_22_6 = 'LISTEN 0      4096              [::]:22            [::]:*    users:(("sshd",pid=1456,fd=4),("systemd",pid=1,fd=202))'
L_2222 = 'LISTEN 0      4096           0.0.0.0:2222       0.0.0.0:*    users:(("sshd",pid=10,fd=3))'
L_25 = 'LISTEN 0      100            0.0.0.0:25         0.0.0.0:*    users:(("master",pid=131924,fd=13))'
L_53 = 'LISTEN 0      4096     127.0.0.53%lo:53         0.0.0.0:*    users:(("systemd-resolve",pid=588,fd=17))'
L_STAR = 'LISTEN 0 128 *:22 *:* users:(("sshd",pid=1,fd=3))'
L_NOPROC = 'LISTEN 0 128 0.0.0.0:22 0.0.0.0:*'
port_cases = [
    ("22 v4+v6 ve baska servisler", ss(L_53, L_22_4, L_22_6, L_25), ["22"]),
    ("sadece 2222", ss(L_2222), ["2222"]),
    ("iki port", ss(L_22_4, L_2222), ["22", "2222"]),
    ("sshd yok", ss(L_25, L_53), []),
    ("bos cikti", ss(), []),
    ("*:22 biçimi", ss(L_STAR), ["22"]),
    ("surec bilgisi yok (root degil)", ss(L_NOPROC), []),
]
res = run_cases([(n, i, ports_expr, "hardening_ufw_ssh_ports") for n, i, _ in port_cases])
for n, _, want in port_cases:
    check(f"ssh portlari: {n}", want, res.get(n))

# ---- 0d: ignoreip ----
ign_expr = task_expr("roles/hardening_fail2ban/tasks/main.yml", "Compute effective ignoreip",
                     "hardening_fail2ban_ignoreip_effective")
base = "127.0.0.1/8 ::1"
conn = lambda rc, out, b=base: {"hardening_fail2ban_ssh_connection": {"rc": rc, "stdout": out},  # noqa: E731
                                "hardening_fail2ban_ignoreip": b}
ign_cases = [
    ("IPv4 eklenir", conn(0, "10.1.2.3 5555 10.9.9.9 22"), "127.0.0.1/8 ::1 10.1.2.3"),
    ("IPv6 eklenir", conn(0, "fd00::5 5555 fd00::9 22"), "127.0.0.1/8 ::1 fd00::5"),
    ("zaten listede tekrar yok", conn(0, "127.0.0.1 5555 127.0.0.1 22", "127.0.0.1 ::1"), "127.0.0.1 ::1"),
    ("rc!=0 taban liste", conn(1, ""), base),
    ("bos stdout taban liste", conn(0, ""), base),
    ("ozel liste + adres", conn(0, "192.168.1.9 1 192.168.1.2 22", "127.0.0.1/8 ::1 192.168.1.0/24"),
     "127.0.0.1/8 ::1 192.168.1.0/24 192.168.1.9"),
]
res = run_cases([(n, i, ign_expr, "hardening_fail2ban_ignoreip_effective") for n, i, _ in ign_cases])
for n, _, want in ign_cases:
    check(f"ignoreip: {n}", want, res.get(n))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
