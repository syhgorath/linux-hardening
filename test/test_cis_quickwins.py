#!/usr/bin/env python3
"""CIS "kolay kazançlar": kernel modülleri, ufw routed ilkesi, auditd servis yeniden başlatma / GRUB audit=1.

Görevlerin kendi ifadeleri gerçek `ansible-playbook` ile (localhost, geçici dosyalar) çalıştırılır; böylece YAML'daki regexp/Jinja
gerçekten denenir, yalnızca metin aranmaz. Tehlikeli yönler: sshd'yi yeniden başlatma listesi (erişim kaybı), audit=1'in tekrar tekrar
eklenmesi, kernel varsayılanlarının sessizce değişmesi.
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


def load(p):
    return yaml.safe_load((ROOT / p).read_text(encoding="utf-8"))


def task(role, name):
    for t in load(f"roles/{role}/tasks/main.yml"):
        if t.get("name") == name:
            return t
    raise SystemExit(f"görev yok: {role}: {name}")


def play(tasks, vars_=None, check_mode=False):
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False,
                                       "vars": vars_ or {}, "tasks": tasks}], allow_unicode=True), encoding="utf-8")
        cmd = ["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)] + (["--check"] if check_mode else [])
        r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


# 1) varsayılanlar: riskli olanlar kapalı, güvenli olan açık
check("varsayilan: ipv6 RA kapatma KAPALI", False, load("roles/hardening_kernel/defaults/main.yml")["hardening_kernel_disable_ipv6_ra"])
check("varsayilan: audit=1 KAPALI", False, load("roles/hardening_auditd/defaults/main.yml")["hardening_auditd_grub_audit"])
check("varsayilan: servis yeniden baslatma listesi BOS", [], load("roles/hardening_auditd/defaults/main.yml")["hardening_auditd_restart_services"])
check("varsayilan: ufw routed deny ACIK", True, load("roles/hardening_ufw/defaults/main.yml")["hardening_ufw_routed_deny"])

# 2) kernel modülleri
kern = (ROOT / "roles/hardening_kernel/tasks/main.yml").read_text(encoding="utf-8")
fs = task("hardening_kernel", "Disable unused filesystem modules (CIS 1.1.1.x)")["ansible.builtin.copy"]["content"]
for m in ("cramfs", "freevxfs", "hfs", "hfsplus", "jffs2", "firewire-core"):
    check(f"fs modulu listede: {m}", True, f"'{m}'" in fs)
proto = task("hardening_kernel", "Disable unused network protocols")["ansible.builtin.copy"]["content"]
for m in ("atm", "can", "dccp", "rds", "sctp", "tipc"):
    check(f"ag protokol modulu listede: {m}", True, f"'{m}'" in proto)
check("usb-storage hala base rolunde", True, "usb-storage" in (ROOT / "roles/hardening_base/tasks/main.yml").read_text(encoding="utf-8"))

# 3) ufw routed ilkesi: görevin kendi loop ifadesi gerçek Jinja ile hesaplanır
t = task("hardening_ufw", "Default policies")
expr = t["loop"]
for val in (True, False):
    rc, out = play([{"ansible.builtin.debug": {"msg": "{{ (" + expr.strip("{} ").strip() + ") | to_json }}"}}], {"hardening_ufw_routed_deny": val, "hardening_ufw_outgoing_deny": False})
    items = []
    for line in out.splitlines():
        if '"msg"' in line:
            items = json.loads(json.loads(line.split('"msg":', 1)[1].strip().rstrip(",")))
    got = sorted((i["key"], i["value"]) for i in items)
    want = [("incoming", "deny"), ("outgoing", "allow")] + ([("routed", "deny")] if val else [])
    check(f"ufw varsayilan ilkeler (routed_deny={val})", sorted(want), got)

# 4) auditd: ssh yeniden başlatma yasağı (gerçek assert)
a = task("hardening_auditd", "Refuse to restart ssh through the auditd role")
for lst, ok in (([], True), (["chrony"], True), (["chrony.service", "cron"], True),
                (["ssh"], False), (["sshd"], False), (["ssh.service"], False), (["sshd.service"], False), (["cron", "ssh.socket"], False)):
    rc, _ = play([{"name": a["name"], "ansible.builtin.assert": a["ansible.builtin.assert"], "when": a["when"]}], {"hardening_auditd_restart_services": lst})
    check(f"restart listesi {lst}: {'kabul' if ok else 'REDDEDILIR'}", ok, rc == 0)

r = task("hardening_auditd", "Restart listed services so they are audited")
check("restart: --check'te calismaz", True, "not ansible_check_mode" in str(r["when"]))
check("restart: yalnizca liste doluyken", True, "length > 0" in str(r["when"]))
u = task("hardening_auditd", "Regenerate GRUB configuration")
check("update-grub: --check'te calismaz, yalniz degisince", True, "not ansible_check_mode" in str(u["when"]) and "is changed" in str(u["when"]))

# 5) GRUB audit=1: görevin kendi regexp/replace parametreleriyle gerçek `replace` modülü
g = task("hardening_auditd", "Add audit=1 to GRUB_CMDLINE_LINUX (reboot required)")["ansible.builtin.replace"]


def run_replace(line, check_mode=False):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "grub"
        f.write_text(line, encoding="utf-8")
        rc, out = play([{"ansible.builtin.replace": {"path": str(f), "regexp": g["regexp"], "replace": g["replace"]}}], check_mode=check_mode)
        return rc, f.read_text(encoding="utf-8"), "changed=1" in out


rc, txt, ch = run_replace('GRUB_CMDLINE_LINUX="quiet splash"\nGRUB_TIMEOUT=0\n')
check("audit=1 eklenir, diger satirlar bozulmaz", ('GRUB_CMDLINE_LINUX="quiet splash audit=1"\nGRUB_TIMEOUT=0\n', True), (txt, ch))
rc, txt2, ch2 = run_replace(txt)
check("ikinci kosu: degisiklik YOK (idempotent)", (txt, False), (txt2, ch2))
rc, txt, ch = run_replace('GRUB_CMDLINE_LINUX=""\n')
check("bos komut satiri: audit=1 eklenir", ('GRUB_CMDLINE_LINUX=" audit=1"\n', True), (txt, ch))
rc, txt, ch = run_replace('GRUB_CMDLINE_LINUX="audit=0 quiet"\n')
check("kullanici audit=0 yazdiysa DOKUNULMAZ", ('GRUB_CMDLINE_LINUX="audit=0 quiet"\n', False), (txt, ch))
rc, txt, ch = run_replace('GRUB_CMDLINE_LINUX_DEFAULT="quiet"\nGRUB_CMDLINE_LINUX="x"\n')
check("yalniz GRUB_CMDLINE_LINUX (DEFAULT'a dokunulmaz)", ('GRUB_CMDLINE_LINUX_DEFAULT="quiet"\nGRUB_CMDLINE_LINUX="x audit=1"\n', True), (txt, ch))
rc, txt, ch = run_replace('GRUB_CMDLINE_LINUX="quiet"\n', check_mode=True)
check("--check: dosya degismez ama degisecegi bildirilir", ('GRUB_CMDLINE_LINUX="quiet"\n', True), (txt, ch))

# 6) journald: kalıcı depolama + sıkıştırma açıkça yazılır (CIS 6.1.1.1.6/7); saklama süresi/boyut ayarlarına dokunulmaz
jd = task("hardening_base", "Persistent, compressed journald storage")
jc = jd["ansible.builtin.copy"]
check("journald drop-in /etc/systemd/journald.conf.d/ altinda, 0644 root", True, jc["dest"].startswith("/etc/systemd/journald.conf.d/") and jc["mode"] == "0644" and jc["owner"] == "root")
check("journald: [Journal] basligi, Storage=persistent, Compress=yes", True, all(x in jc["content"] for x in ("[Journal]", "Storage=persistent", "Compress=yes")))
check("journald: saklama/boyut ayarlarina dokunulmaz (SystemMaxUse, MaxRetention...)", True, not any(x in jc["content"] for x in ("MaxUse", "KeepFree", "MaxRetention", "MaxFileSec")))
check("journald: degisince yeniden baslatilir (handler adi eslesir)", True, jd.get("notify") == "Restart journald")
hand = load("roles/hardening_base/handlers/main.yml")
check("journald handler'i systemd-journald'i restart eder", True, any(h.get("name") == "Restart journald" and h["ansible.builtin.systemd"]["name"] == "systemd-journald" and h["ansible.builtin.systemd"]["state"] == "restarted" for h in hand))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
