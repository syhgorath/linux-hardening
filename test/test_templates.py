#!/usr/bin/env python3
"""Şablonları YALNIZCA rol varsayılanlarıyla (group_vars YOK) render edip golden dosyalarla karşılaştırır.

Varsayılan çıktının istemeden değişmesini yakalar. Bilerek değiştirdiyseniz:
    UPDATE_GOLDEN=1 python3 -I test/test_templates.py
ve değişen golden dosyalarını PR'da gözden geçirin.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = ROOT / "test/golden"
UPDATE = os.environ.get("UPDATE_GOLDEN") == "1"
fails = 0

DEFAULTS = [
    "roles/hardening_auth/defaults/main.yml",
    "roles/hardening_fail2ban/defaults/main.yml",
    "roles/hardening_ufw/defaults/main.yml",
    "roles/hardening_ssh/defaults/main.yml",
    "roles/hardening_rollback/defaults/main.yml",
    "roles/hardening_preflight/defaults/main.yml",
    "vars/ubuntu-26.04.yml",
]
# (golden adi, sablon, ek degiskenler)
CASES = [
    ("pwquality.conf", "roles/hardening_auth/templates/pwquality.conf.j2", {}),
    ("sshd.local", "roles/hardening_fail2ban/templates/sshd.local.j2",
     {"hardening_fail2ban_ignoreip_effective": "127.0.0.1/8 ::1 192.0.2.10"}),
    ("sshd-hardening.default.conf", "roles/hardening_ssh/templates/sshd-hardening.conf.j2", {}),
    ("sshd-hardening.kbd.conf", "roles/hardening_ssh/templates/sshd-hardening.conf.j2",
     {"hardening_ssh_kbdinteractive": True}),
    ("sshd-hardening.fwd-local.conf", "roles/hardening_ssh/templates/sshd-hardening.conf.j2",
     {"hardening_ssh_allow_tcp_forwarding": "local"}),
    ("sshd-hardening.pw-yes.conf", "roles/hardening_ssh/templates/sshd-hardening.conf.j2",
     {"hardening_ssh_disable_password": False}),
    ("sysctl.conf", "roles/hardening_kernel/templates/sysctl.conf.j2", {}),
    ("hardening.rules", "roles/hardening_auditd/templates/hardening.rules.j2", {}),
    ("hardening-rollback.sh", "roles/hardening_rollback/templates/hardening-rollback.sh.j2", {}),
    ("hardening-rollback.service", "roles/hardening_rollback/templates/hardening-rollback.service.j2", {}),
    ("hardening-rollback.timer", "roles/hardening_rollback/templates/hardening-rollback.timer.j2", {}),
    ("hardening-rollback.timer.600", "roles/hardening_rollback/templates/hardening-rollback.timer.j2",
     {"hardening_rollback_timeout": 600}),
]


def render(d):
    vars_ = {}
    for f in DEFAULTS:
        vars_.update(yaml.safe_load((ROOT / f).read_text(encoding="utf-8")) or {})
    tasks = []
    for name, tpl, extra in CASES:
        tasks.append({
            "vars": {**vars_, **extra},
            "ansible.builtin.template": {"src": str(ROOT / tpl), "dest": f"{d}/{name}"},
        })
    play = [{"hosts": "localhost", "connection": "local", "gather_facts": False, "tasks": tasks}]
    pb = Path(d) / "p.yml"
    pb.write_text(yaml.safe_dump(play, allow_unicode=True), encoding="utf-8")
    r = subprocess.run(
        ["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
        env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")},
    )
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        raise SystemExit("şablon render edilemedi")


with tempfile.TemporaryDirectory() as d:
    render(d)
    GOLDEN.mkdir(exist_ok=True)
    for name, _, _ in CASES:
        got = (Path(d) / name).read_text(encoding="utf-8")
        gp = GOLDEN / name
        if UPDATE:
            gp.write_text(got, encoding="utf-8")
            print(f"  güncellendi {name}")
            continue
        if not gp.exists():
            fails += 1
            print(f"  FAIL {name}: golden yok (UPDATE_GOLDEN=1 ile üretin)")
        elif gp.read_text(encoding="utf-8") != got:
            fails += 1
            print(f"  FAIL {name}: golden ile farklı")
            import difflib
            for line in difflib.unified_diff(gp.read_text(encoding="utf-8").splitlines(), got.splitlines(),
                                             "golden", "uretilen", lineterm=""):
                print("      " + line)
        else:
            print(f"  ok   {name}")

# anlamsal denetimler (golden'dan bağımsız)
def read(n):
    return (GOLDEN / n).read_text(encoding="utf-8") if (GOLDEN / n).exists() else ""

def assert_has(label, text, needle, want=True):
    global fails
    has = needle in text
    if has == want:
        print(f"  ok   {label}")
    else:
        fails += 1
        print(f"  FAIL {label}")

if not UPDATE:
    d_ = read("sshd-hardening.default.conf")
    assert_has("varsayilan: PasswordAuthentication no", d_, "PasswordAuthentication no")
    assert_has("varsayilan: KbdInteractive no", d_, "KbdInteractiveAuthentication no")
    assert_has("varsayilan: AuthenticationMethods YOK", d_, "AuthenticationMethods", want=False)
    assert_has("varsayilan: AllowTcpForwarding no", d_, "AllowTcpForwarding no")
    assert_has("varsayilan: PermitRootLogin no", d_, "PermitRootLogin no")
    k = read("sshd-hardening.kbd.conf")
    assert_has("kbd: yes", k, "KbdInteractiveAuthentication yes")
    assert_has("kbd: AuthenticationMethods publickey,keyboard-interactive", k,
               "AuthenticationMethods publickey,keyboard-interactive")
    assert_has("kbd: PasswordAuthentication hala no", k, "PasswordAuthentication no")
    assert_has("fail2ban: efektif ignoreip kullanilir", read("sshd.local"), "ignoreip = 127.0.0.1/8 ::1 192.0.2.10")
    assert_has("fail2ban: 10.0.0.0/8 muaf DEGIL", read("sshd.local"), "10.0.0.0/8", want=False)
    assert_has("rollback: timer 300s", read("hardening-rollback.timer"), "OnActiveSec=300s")
    assert_has("rollback: timer 600s degiskenden", read("hardening-rollback.timer.600"), "OnActiveSec=600s")
    assert_has("rollback: service restore cagirir", read("hardening-rollback.service"),
               "ExecStart=/usr/local/sbin/hardening-rollback restore")
    assert_has("rollback: betik ssh servisi varsayilani", read("hardening-rollback.sh"),
               "DEFAULT_SSH_SERVICE='ssh'")

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
