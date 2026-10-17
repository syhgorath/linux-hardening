#!/usr/bin/env python3
"""hardening_time: rolün SALT OKUNUR kalması (statik). Zaman raporu saati/yapılandırmayı değiştirmemeli, hiçbir şeyi başarısız kılmamalı,
`--check`'te de çalışmalı ve kapatılabilmeli (hardening_time_report)."""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
tasks = yaml.safe_load((ROOT / "roles/hardening_time/tasks/main.yml").read_text(encoding="utf-8"))
defaults = yaml.safe_load((ROOT / "roles/hardening_time/defaults/main.yml").read_text(encoding="utf-8"))
play = yaml.safe_load((ROOT / "playbooks/harden.yml").read_text(encoding="utf-8"))[0]
fails = 0
READ_ONLY = {"ansible.builtin.command", "ansible.builtin.script", "ansible.builtin.set_fact", "ansible.builtin.debug", "ansible.builtin.systemd"}


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail}")


def walk(ts):
    for t in ts or []:
        yield t
        yield from walk(t.get("block"))


def mod(t):
    return next((k for k in t if k.startswith("ansible.builtin.")), None)


flat = [t for t in walk(tasks)]
leaf = [t for t in flat if mod(t)]
check("rol var ve görevleri var", len(leaf) >= 6)
check("yalnızca salt okunur modüller kullanılıyor (command, script, set_fact, debug, systemd-durum-okuma)", all(mod(t) in READ_ONLY for t in leaf), f"modüller={sorted({mod(t) for t in leaf})}")
check("hiçbir görev fail/assert kullanmıyor (rapor başarısız kılmaz)", all(mod(t) not in ("ansible.builtin.fail", "ansible.builtin.assert") for t in leaf))
check("notify/handler yok", all("notify" not in t for t in flat))

systemd = [t for t in leaf if mod(t) == "ansible.builtin.systemd"]
check("systemd modülü yalnızca durum okur (state/enabled/daemon_reload/masked verilmez)",
      len(systemd) == 1 and not (set(systemd[0]["ansible.builtin.systemd"]) & {"state", "enabled", "daemon_reload", "daemon_reexec", "masked", "scope", "force"}))
reads = [t for t in leaf if mod(t) in ("ansible.builtin.command", "ansible.builtin.script", "ansible.builtin.systemd")]
check("okuma/değerlendirme görevleri `--check`'te de çalışır (check_mode: false)", all(t.get("check_mode") is False for t in reads))
check("command/script görevleri değişiklik saymaz (changed_when: false)", all(t.get("changed_when") is False for t in reads if mod(t) != "ansible.builtin.systemd"))
check("okumalar başarısız olursa rol durmaz (failed_when: false)", all(t.get("failed_when") is False for t in reads if mod(t) in ("ansible.builtin.command", "ansible.builtin.systemd")))

wrapper = tasks[0]
check("tüm görevler hardening_time_report ile kapatılabilir", "hardening_time_report" in str(wrapper.get("when")) and "block" in wrapper)
check("varsayılanlar: rapor açık, eşik 5 sn", defaults == {"hardening_time_report": True, "hardening_time_max_offset_seconds": 5}, f"defaults={defaults}")

cmds = " ".join(str(t.get("ansible.builtin.command", "")) for t in leaf)
check("saati değiştiren komut yok (makestep, systemctl restart/start/stop, timedatectl set-*)",
      not any(x in cmds for x in ("makestep", "restart", "systemctl start", "systemctl stop", "set-time", "set-ntp", "hwclock", "date -s", "date --set", "ntpdate")), f"komutlar={cmds}")
dates = [str(t["ansible.builtin.command"]) for t in leaf if mod(t) == "ansible.builtin.command" and str(t["ansible.builtin.command"]).startswith("date")]
check("`date` yalnızca epoch OKUR (date +%s)", dates == ["date +%s"], f"date komutları={dates}")

roles = [r.get("role") for r in play["roles"] if isinstance(r, dict)]
entry = next((r for r in play["roles"] if isinstance(r, dict) and r.get("role") == "hardening_time"), None)
check("harden.yml'de rol var, etiketi `time`", entry is not None and entry.get("tags") == ["time"])
check("rol, ufw/ssh'tan ÖNCE (erişim kaybı korumalarından bağımsız, yalnızca rapor)", roles.index("hardening_time") < roles.index("hardening_ufw") < roles.index("hardening_ssh"))
# kontrol makinesi epoch ifadesi: saat diliminden bağımsız doğru olmalı (now(utc=true).timestamp() naive UTC'yi yerel sayar ve saat dilimi kadar kayar; VM'de 3 sa kayma olarak görüldü)
import os
import re
import subprocess
import tempfile
import time
text = (ROOT / "roles/hardening_time/tasks/main.yml").read_text(encoding="utf-8")
m = re.search(r"'controller_epoch': (.+?\| int),", text)
check("controller_epoch ifadesi bulundu", bool(m))
if m:
    expr = m.group(1)
    for tz in ("UTC", "Europe/Istanbul", "America/New_York", "Pacific/Auckland"):
        with tempfile.TemporaryDirectory() as d:
            pb = Path(d) / "p.yml"
            pb.write_text("- hosts: localhost\n  connection: local\n  gather_facts: false\n  tasks:\n    - ansible.builtin.debug:\n        msg: \"EPOCH={{ " + expr + " }}\"\n", encoding="utf-8")
            r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                               env={**os.environ, "TZ": tz, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        got = re.search(r"EPOCH=(\d+)", r.stdout)
        check(f"controller_epoch gerçek epoch'a eşit (TZ={tz})", bool(got) and abs(int(got.group(1)) - time.time()) < 30, f"çıktı={got.group(1) if got else r.stdout[-200:]}")

sys.exit(1 if fails else 0)
