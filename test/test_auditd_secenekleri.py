#!/usr/bin/env python3
"""auditd/AIDE ek seçenekleri (hepsi varsayılan KAPALI): auditd.conf (CIS 6.2.2.x), disk dolunca durdur (6.2.2), audit_backlog_limit (6.2.1, GRUB), değiştirilemez yapılandırma -e 2 (6.2.3.x son madde),
AIDE audit araçları (6.3.3). Gerçek Ansible ile geçici dosyalar üzerinde denenir; kilitliyken kural yüklemesi atlanır."""
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


def ap(pb, extra=None):
    return subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)] + (["-e", yaml.safe_dump(extra, default_flow_style=True)] if extra else []),
                          capture_output=True, text=True, stdin=subprocess.DEVNULL, env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})


ad = load("roles/hardening_auditd/defaults/main.yml")
aid = load("roles/hardening_aide/defaults/main.yml")
check("varsayilanlar: hepsi KAPALI / 0", (ad["hardening_auditd_conf_cis"], ad["hardening_auditd_disk_full_halt"], ad["hardening_auditd_backlog_limit"], ad["hardening_auditd_immutable"], aid["hardening_aide_audit_tools"]) == (False, False, 0, False, False))
check("auditd.conf degerleri CIS 6.2.2.x: keep_logs, space_left email, admin_space_left single", ad["hardening_auditd_conf_values"] == {"max_log_file": 8, "max_log_file_action": "keep_logs", "space_left_action": "email", "admin_space_left_action": "single"})

tasks = load("roles/hardening_auditd/tasks/main.yml")
by = {t["name"]: t for t in tasks if isinstance(t, dict) and "name" in t}
names = [t.get("name") for t in tasks if isinstance(t, dict)]


def need(n):
    t = by.get(n)
    check(f"gorev var: {n}", t is not None)
    return t or {}


def w(t):
    x = t.get("when")
    return " ".join(x) if isinstance(x, list) else str(x)


# ---- auditd.conf: gercek lineinfile (gorevin kendisi, yol degistirilmis) ----
t = need("Configure auditd.conf (log size, keep logs, low disk space actions)")
check("auditd.conf: kendi degiskeniyle kapanir, --check + yeni kurulum iken atlanir", "hardening_auditd_conf_cis" in w(t) and "hardening_auditd_install" in w(t) and "ansible_check_mode" in w(t))
with tempfile.TemporaryDirectory() as d:
    conf = Path(d) / "auditd.conf"
    conf.write_text("# auditd\nlog_file = /var/log/audit/audit.log\nmax_log_file = 6\nmax_log_file_action = ROTATE\nspace_left_action = SYSLOG\nadmin_space_left_action = SUSPEND\ndisk_full_action = SUSPEND\n", encoding="utf-8")
    tt = dict(t); tt.pop("when", None); tt["ansible.builtin.lineinfile"] = dict(t["ansible.builtin.lineinfile"], path=str(conf))
    pb = Path(d) / "p.yml"
    pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_auditd_conf_values": ad["hardening_auditd_conf_values"]}, "tasks": [tt]}]), encoding="utf-8")
    ap(pb)
    txt = conf.read_text(encoding="utf-8")
    check("auditd.conf: dort anahtar yazildi, eski degerler yok", all(x in txt for x in ("max_log_file = 8", "max_log_file_action = keep_logs", "space_left_action = email", "admin_space_left_action = single")) and "ROTATE" not in txt and "SYSLOG" not in txt, txt)
    check("auditd.conf: baska satirlar KORUNUR (log_file, disk_full_action)", "log_file = /var/log/audit/audit.log" in txt and "disk_full_action = SUSPEND" in txt)
    check("auditd.conf: ikinci kosu changed=0", "changed=0" in ap(pb).stdout)

t = need("Halt the system when the audit disk is full or fails")
with tempfile.TemporaryDirectory() as d:
    conf = Path(d) / "auditd.conf"
    conf.write_text("disk_full_action = SUSPEND\ndisk_error_action = SYSLOG\nlog_file = /x\n", encoding="utf-8")
    tt = dict(t); tt.pop("when", None); tt["ansible.builtin.lineinfile"] = dict(t["ansible.builtin.lineinfile"], path=str(conf))
    pb = Path(d) / "p.yml"; pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "tasks": [tt]}]), encoding="utf-8")
    ap(pb)
    txt = conf.read_text(encoding="utf-8")
    check("disk dolunca: disk_full_action ve disk_error_action = halt, baska satir korunur", "disk_full_action = halt" in txt and "disk_error_action = halt" in txt and "log_file = /x" in txt, txt)
check("disk dolunca durdur: kendi degiskeniyle kapanir", "hardening_auditd_disk_full_halt" in w(t))
check("auditd.conf degisince auditd yeniden OKUR (reload), basarisizlik koşuyu durdurmaz", need("Reload auditd so it re-reads auditd.conf").get("failed_when") is False)

# ---- -e 2 ----
t = need("Make the audit configuration immutable (-e 2)")
cp = t.get("ansible.builtin.copy", {})
check("-e 2 dosyasi: 99- ile baslar (son yuklenir), icerik '-e 2', kendi degiskeniyle", cp.get("dest") == "/etc/audit/rules.d/99-hardening-finalize.rules" and "\n-e 2" in cp.get("content", "") and "hardening_auditd_immutable" in w(t))
check("-e 2: diger audit kural dosyalarindan SONRA siralanir (60-, 61-)", Path(cp["dest"]).name > "61-hardening-cis-l2.rules")
rm = need("Remove the immutable-configuration rule (option off)")
check("-e 2 kapaliyken dosya silinir", rm.get("ansible.builtin.file", {}).get("state") == "absent" and "not (hardening_auditd_immutable" in w(rm))
load_t = need("Load audit rules")
check("kural yukleme KILITLIYKEN atlanir, -e 2 dosyasi degisince de yuklenir", "not (hardening_auditd_locked | bool)" in w(load_t) and "hardening_auditd_immutable_file is changed" in w(load_t))
check("kilit durumu auditctl -s ile SALT OKUNUR okunur", need("Read whether the audit configuration is locked (-e 2)").get("check_mode") is False)
sf = need("Remember whether the audit configuration is locked")
for label, out, want in (("enabled 2", "enabled 2\nfailure 1\npid 99\n", True), ("enabled 1", "enabled 1\nfailure 1\npid 99\n", False), ("enabled 0", "enabled 0\n", False), ("bos/okunamadi", "", False)):
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_auditd_status": {"stdout": out}},
                                       "tasks": [sf, {"ansible.builtin.fail": {"msg": "LOCKED_TRUE"}, "when": "hardening_auditd_locked | bool"}]}]), encoding="utf-8")
        r = ap(pb)
        check(f"kilit algilama: '{label}' -> {want}", ("LOCKED_TRUE" in r.stdout + r.stderr) == want, (r.stdout + r.stderr)[-200:])

# ---- GRUB audit_backlog_limit: gercek replace ----
add = need("Add audit_backlog_limit to GRUB_CMDLINE_LINUX (reboot required)")
upd = need("Update a different audit_backlog_limit in GRUB_CMDLINE_LINUX (reboot required)")
check("backlog: yalniz hardening_auditd_backlog_limit > 0 ve /etc/default/grub varken", "hardening_auditd_backlog_limit | int > 0" in w(add) and "hardening_auditd_grub_file.stat.exists" in w(add) and "hardening_auditd_backlog_limit | int > 0" in w(upd))
check("GRUB yeniden uretimi backlog degisince de calisir", "hardening_auditd_backlog_add is changed" in w(need("Regenerate GRUB configuration")))
check("GRUB dosyasi kontrolu backlog_limit > 0 iken de yapilir", "hardening_auditd_backlog_limit | int > 0" in w(need("Check GRUB default file")))
for label, start, want_has in (("hic yok", 'GRUB_CMDLINE_LINUX="quiet splash audit=1"\n', "audit_backlog_limit=8192"), ("farkli deger", 'GRUB_CMDLINE_LINUX="quiet audit_backlog_limit=64 audit=1"\n', "audit_backlog_limit=8192"), ("bos satir", 'GRUB_CMDLINE_LINUX=""\n', "audit_backlog_limit=8192")):
    with tempfile.TemporaryDirectory() as d:
        g = Path(d) / "grub"; g.write_text("GRUB_DEFAULT=0\n" + start, encoding="utf-8")
        a2 = dict(add); a2["ansible.builtin.replace"] = dict(add["ansible.builtin.replace"], path=str(g)); u2 = dict(upd); u2["ansible.builtin.replace"] = dict(upd["ansible.builtin.replace"], path=str(g))
        for x in (a2, u2): x.pop("when", None)
        pb = Path(d) / "p.yml"; pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_auditd_backlog_limit": 8192}, "tasks": [a2, u2]}]), encoding="utf-8")
        ap(pb)
        txt = g.read_text(encoding="utf-8")
        line = [l for l in txt.splitlines() if l.startswith("GRUB_CMDLINE_LINUX=")][0]
        keep = all(k in line for k in (("quiet", "splash", "audit=1") if "splash" in start else ("quiet", "audit=1") if "quiet" in start else ()))
        check(f"GRUB backlog ({label}): {want_has}, mevcut parametreler korunur, tek kez", want_has in line and line.count("audit_backlog_limit=") == 1 and keep and "GRUB_DEFAULT=0" in txt, line)
        check(f"GRUB backlog ({label}): ikinci kosu changed=0", "changed=0" in ap(pb).stdout)

# ---- AIDE ----
at = load("roles/hardening_aide/tasks/main.yml")
ab = {t["name"]: t for t in at if isinstance(t, dict) and "name" in t}
tools = ab.get("Protect the audit tools with cryptographic checksums (CIS 6.3.3)", {})
cp = tools.get("ansible.builtin.copy", {})
check("AIDE: 00_ ile baslayan dosya (varsayilan kurallardan ONCE okunur), sha512 + oznitelikler, kendi degiskeniyle", Path(cp.get("dest", "")).name == "00_hardening_audit_tools" and "sha512" in cp.get("content", "") and "acl+xattrs" in cp.get("content", "") and "hardening_aide_audit_tools" in str(tools.get("when")))
with tempfile.TemporaryDirectory() as d:
    out = Path(d) / "00_hardening_audit_tools"
    tt = dict(tools); tt.pop("when", None); tt["ansible.builtin.copy"] = dict(cp, dest=str(out), owner=None, group=None)
    tt["ansible.builtin.copy"].pop("owner"); tt["ansible.builtin.copy"].pop("group")
    pb = Path(d) / "p.yml"; pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_aide_audit_tool_paths": aid["hardening_aide_audit_tool_paths"]}, "tasks": [tt]}]), encoding="utf-8")
    ap(pb)
    txt = out.read_text(encoding="utf-8") if out.exists() else ""
    lines = [l for l in txt.splitlines() if l and not l.startswith("#")]
    check("AIDE: alti arac, her biri sha512 + oznitelik kuraliyla", len(lines) == 6 and all(l.endswith("p+i+n+u+g+s+b+acl+xattrs+sha512") for l in lines) and any(l.startswith("/usr/sbin/auditctl ") for l in lines), txt)
check("AIDE: kapaliyken dosya silinir", ab.get("Remove the audit tools AIDE rules (option off)", {}).get("ansible.builtin.file", {}).get("state") == "absent")

# ---- component.yml ----
comp = load("component.yml")
cv = {v["name"]: v for v in comp["vars"] if isinstance(v, dict)}
exp = {"hardening_auditd_conf_cis": (False, True), "hardening_auditd_disk_full_halt": (False, True), "hardening_auditd_backlog_limit": (0, False), "hardening_auditd_immutable": (False, True), "hardening_aide_audit_tools": (False, False)}
for n, (dflt, warn) in exp.items():
    v = cv.get(n)
    check(f"component.yml: {n} varsayilan {dflt}, warn_if={warn}", v is not None and v["default"] == dflt and bool(v.get("warn_if")) == warn, str(v))
doc = (ROOT / "docs/component-vars.md").read_text(encoding="utf-8")
check("docs/component-vars.md bunlari icerir", all(f"`{n}`" in doc for n in exp))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
