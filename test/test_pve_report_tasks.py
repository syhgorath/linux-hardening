#!/usr/bin/env python3
"""hardening_pve_report: görevler SALT OKUNUR kalmalı (statik), playbook Proxmox olmayan hedefte DURMALI, harden.yml'e BAĞLI OLMAMALI ve gerçek görev zinciri
(sahte okuma çıktıları -> betik girdisi -> sonuç) gerçek Proxmox VE 9.2'den alınan değerlerle doğru çalışmalı."""
import base64
import json
import os
import re
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


tasks = yaml.safe_load((ROOT / "roles/hardening_pve_report/tasks/main.yml").read_text(encoding="utf-8"))
by = {t["name"]: t for t in tasks}
mod = lambda t: next(k for k in t if k.startswith("ansible.builtin."))
reads = [t for t in tasks if mod(t) in ("ansible.builtin.command", "ansible.builtin.shell", "ansible.builtin.script", "ansible.builtin.systemd")]
check("yalniz salt okunur moduller (command, shell, script, systemd-durum-okuma, set_fact, debug)", all(mod(t) in {"ansible.builtin.command", "ansible.builtin.shell", "ansible.builtin.script", "ansible.builtin.systemd", "ansible.builtin.set_fact", "ansible.builtin.debug"} for t in tasks))
check("okuma/degerlendirme gorevleri --check'te de calisir, degisiklik saymaz, hata durdurmaz", all(t.get("check_mode") is False for t in reads) and all(t.get("changed_when") is False for t in reads if mod(t) != "ansible.builtin.systemd") and all(t.get("failed_when") is False for t in reads if mod(t) != "ansible.builtin.script"))
sv = by["Read the Proxmox services (read-only)"]
check("servisler `systemd` modulu ile yalniz OKUNUR (state/enabled/masked/daemon_reload verilmez)", set(sv["ansible.builtin.systemd"]) == {"name"} and sv.get("check_mode") is False and sv.get("failed_when") is False)
check("borulu shell gorevleri `set -o pipefail` ile ve bash ile", all(("set -o pipefail" in t["ansible.builtin.shell"]["cmd"] and t["ansible.builtin.shell"]["executable"] == "/bin/bash") for t in tasks if mod(t) == "ansible.builtin.shell"))
cmds = " ".join(str(t.get("ansible.builtin.command", "")) + str(t.get("ansible.builtin.shell", {}).get("cmd", "")) for t in tasks)
check("yazan/degistiren komut yok (apt, systemctl start/stop/restart/enable, pve-firewall start/stop/compile, qm/pct start/stop/create, rm, mv, cp, chmod, tee, >)",
      not any(re.search(p, cmds) for p in (r"(?<![/\w.-])apt(-get)?\s+(install|remove|purge|update|upgrade|autoremove|dist-upgrade)", r"systemctl (start|stop|restart|enable|disable|mask)", r"pve-firewall (start|stop|restart|compile)", r"\b(qm|pct) (start|stop|create|destroy|set)", r"\brm\b", r"\bmv\b", r"\bcp\b", r"\bchmod\b", r"\btee\b", r"[^-|>2&]>[^&]")), cmds[:300])
check("systemctl hic cagrilmaz (servisler systemd modulu ile)", "systemctl" not in cmds)

pb = yaml.safe_load((ROOT / "playbooks/pve-report.yml").read_text(encoding="utf-8"))[0]
pnames = [t["name"] for t in pb["tasks"]]
check("playbook: Proxmox olmayan hedefte (/etc/pve yok) DURUR ve rolden ONCE", pnames.index("Stop when the target is not a Proxmox VE host") < pnames.index("Proxmox VE report") and "not hardening_pve_marker.stat.exists" in pb["tasks"][1]["when"])
check("playbook /etc/pve'ye bakar, --check'te de", pb["tasks"][0]["ansible.builtin.stat"]["path"] == "/etc/pve" and pb["tasks"][0].get("check_mode") is False)
hy = (ROOT / "playbooks/harden.yml").read_text(encoding="utf-8")
check("harden.yml bu role BAGLI DEGIL (Proxmox hostu sertlestirilmez, koruma bozulmaz)", "hardening_pve_report" not in hy and "pve-report" not in hy)
check("hardening_preflight Proxmox korumasi hala var", "Refuse to run on a Proxmox VE host" in (ROOT / "roles/hardening_preflight/tasks/main.yml").read_text(encoding="utf-8"))

# gercek zincir: Proxmox VE 9.2.21 degerleri
STATE = ["CLUSTERED=no", "FIREWALL=Status: disabled/running", "QEMU=0", "LXC=0", "SUBSCRIPTION=notfound", "PVE_NEEDS_MTA=yes", "POSTFIX=yes", "UFW=no"]
NAMES = ["pve-cluster", "pvedaemon", "pveproxy", "pvestatd", "pve-firewall"]
SERV = ["active"] * 5
NET = ["LISTEN=127.0.0.1:85", "LISTEN=0.0.0.0:111", "LISTEN=0.0.0.0:22", "LISTEN=127.0.0.1:25", "LISTEN=[::1]:25", "LISTEN=*:8006", "LISTEN=*:3128", "LISTEN=[::]:111", "LISTEN=[::]:22",
       "SSHD_PERMITROOTLOGIN=yes", "SSHD_PASSWORDAUTHENTICATION=yes", "NO_SUBSCRIPTION=yes"]


def chain(version, state, serv, net):
    ev = dict(by["Evaluate the Proxmox host"]["ansible.builtin.script"])
    ev["cmd"] = re.sub(r"^pve_report\.py", str(ROOT / "roles/hardening_pve_report/files/pve_report.py"), ev["cmd"].strip())
    with tempfile.TemporaryDirectory() as d:
        pb_ = Path(d) / "p.yml"
        pb_.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "tasks": [
            {"ansible.builtin.set_fact": {"hardening_pve_version": {"stdout": version}, "hardening_pve_state": {"stdout_lines": state},
                                           "hardening_pve_services": {"results": [{"item": n, "status": {"ActiveState": st}} for n, st in zip(NAMES, serv)]}, "hardening_pve_net": {"stdout_lines": net}}},
            {"ansible.builtin.script": ev, "register": "hardening_pve_raw", "changed_when": False},
            {"ansible.builtin.set_fact": {"hardening_pve_result": by["Parse the Proxmox report"]["ansible.builtin.set_fact"]["hardening_pve_result"]}},
            {"ansible.builtin.debug": {"msg": "R={{ hardening_pve_result | to_json | b64encode }}"}}]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb_)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    m = re.search(r"R=(\S+?)\"?\s*$", r.stdout, re.M)
    return json.loads(base64.b64decode(m.group(1))) if m else {"_ham": r.stdout[-300:]}


VER = "pve-manager/9.2.21/4f6e0ac86f9e8c7f (running kernel: 7.0.14-25-pve)\nikinci satir"
o = chain(VER, STATE, SERV, NET)
w = " ".join(o.get("warnings", [])); n = " ".join(o.get("notes", []))
check("zincir: gercek degerler -> surum 9.2.21, warn, firewall + root SSH uyarisi", (o.get("version"), o.get("status"), "DEVRE DIŞI" in w, "PermitRootLogin yes" in w), str(o)[:200])
check("   notlar: postfix/dma, spiceproxy, rpcbind, ufw kurulu degil, tek dugum, no-subscription", all(k in n for k in ("postfix -> dma", "spiceproxy", "rpcbind", "ufw kurulu değil", "Tek düğüm", "no-subscription")))
o2 = chain(VER, [s.replace("disabled", "enabled") if s.startswith("FIREWALL") else s for s in STATE], SERV, [x for x in NET if not x.startswith("SSHD_")] + ["SSHD_PERMITROOTLOGIN=no", "SSHD_PASSWORDAUTHENTICATION=no"])
check("   firewall etkin + SSH sikilastirilmis -> status ok", o2.get("status") == "ok", str(o2)[:200])
o3 = chain(VER, STATE, ["active", "active", "inactive", "active", "active"], NET)
check("   servis sirasi dogru eslenir: 3. servis (pveproxy) inactive -> pveproxy uyarisi", "pveproxy" in " ".join(o3.get("warnings", [])) and "pvedaemon" not in " ".join(o3.get("warnings", [])), str(o3)[:200])
o3b = chain(VER, STATE, SERV, NET)
check("   (kontrol) tum servisler active: servis uyarisi yok", not any("Proxmox servisi" in x for x in o3b.get("warnings", [])))
o4 = chain(VER, [s.replace("CLUSTERED=no", "CLUSTERED=yes").replace("QEMU=0", "QEMU=4").replace("LXC=0", "LXC=2") for s in STATE], SERV, NET)
check("   kume + 4 VM / 2 CT zincirden gecer", "küme" in o4.get("summary", "") and "4 VM / 2 CT" in o4.get("summary", ""), str(o4)[:200])
o5 = chain("", STATE, SERV, NET)
check("   pveversion bos (Proxmox degil) -> unknown", o5.get("status") == "unknown")
sys.exit(1 if fails else 0)
