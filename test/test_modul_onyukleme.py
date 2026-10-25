#!/usr/bin/env python3
"""kernel.modules_disabled=1 önyüklemede modül yüklemeyi kilitler: ufw/netfilter başlamaz, güvenlik duvarı SESSİZCE kapalı kalırdı (gerçek VM, sshpocket 0.8.0 turu).
Seçenek açıkken kilitten ÖNCE yüklenecek modüller (şu an yüklü olanlar + ufw/netfilter + binfmt_misc) /etc/modules-load.d/ altına yazılır; kapalıyken dosya silinir.
Ayrıca hardening_verify_access: tek anahtar belirtme (IdentitiesOnly), ek ssh bağımsız değişkenleri ve 'Too many authentication failures' ipucu."""
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


def load(p):
    return yaml.safe_load((ROOT / p).read_text(encoding="utf-8"))


def play(tasks, vars_=None, extra=None):
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": vars_ or {}, "tasks": tasks}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)] + (["-e", json.dumps(extra)] if extra else []), capture_output=True, text=True,
                           stdin=subprocess.DEVNULL, env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


kd = load("roles/hardening_kernel/defaults/main.yml")
need = {"nf_tables", "nfnetlink", "nf_conntrack", "nf_defrag_ipv4", "nf_defrag_ipv6", "nf_log_syslog", "nf_reject_ipv4", "nf_reject_ipv6", "nft_compat", "nft_limit", "x_tables", "xt_addrtype",
        "xt_conntrack", "xt_hl", "xt_limit", "xt_LOG", "xt_tcpudp", "ipt_REJECT", "ip6t_REJECT", "ip6t_rt", "binfmt_misc"}
check("on yukleme listesi: ufw/netfilter modulleri (gercek VM'de ufw'yi calistiran 20) + binfmt_misc", set(kd["hardening_kernel_preload_modules"]) == need, str(set(kd["hardening_kernel_preload_modules"]) ^ need))
check("modules_disabled varsayilan KAPALI (degismedi)", kd["hardening_kernel_modules_disabled"] is False)

tasks = load("roles/hardening_kernel/tasks/main.yml")
by = {t["name"]: t for t in tasks if isinstance(t, dict) and "name" in t}
names = [t.get("name") for t in tasks if isinstance(t, dict)]
rd = by["Read the loaded kernel modules (read-only)"]
check("lsmod SALT OKUNUR okunur (changed_when false, --check'te de, hata kosuyu durdurmaz)", rd.get("changed_when") is False and rd.get("check_mode") is False and rd.get("failed_when") is False and "lsmod" in rd["ansible.builtin.shell"]["cmd"])
wr = by["Preload the modules before the module lock (kernel.modules_disabled)"]
check("yazilan dosya /etc/modules-load.d/ altinda, yalniz secenek aciksa", wr["ansible.builtin.copy"]["dest"].startswith("/etc/modules-load.d/") and "hardening_kernel_modules_disabled" in str(wr.get("when")))
rm = by["Remove the module preload file (option off)"]
check("secenek kapaliyken dosya silinir", rm["ansible.builtin.file"]["state"] == "absent" and "not (hardening_kernel_modules_disabled" in str(rm.get("when")))
check("sira: lsmod oku -> dosyayi yaz", names.index("Read the loaded kernel modules (read-only)") < names.index("Preload the modules before the module lock (kernel.modules_disabled)"))

with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "60-hardening-preload.conf"
    cp = dict(wr); cp["ansible.builtin.copy"] = dict(wr["ansible.builtin.copy"], dest=str(f)); cp["ansible.builtin.copy"].pop("owner"); cp["ansible.builtin.copy"].pop("group"); cp.pop("when", None)
    fake = {"hardening_kernel_lsmod": {"stdout_lines": ["virtio_net", "nf_tables", "overlay", "br_netfilter", "virtio_net", " ", ""]}, "hardening_kernel_preload_modules": kd["hardening_kernel_preload_modules"]}
    rc, out = play([cp], vars_=fake)
    lines = [l for l in f.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")] if f.exists() else []
    check("dosya: yuklu modul + on yukleme listesi birlesimi, TEKRARSIZ, sirali, bos satir yok", lines == sorted(set(["virtio_net", "nf_tables", "overlay", "br_netfilter"]) | need, key=str.lower) and len(lines) == len(set(lines)), str(lines))
    check("yuklu modul (overlay, virtio_net, br_netfilter) korunur: kilit sonrasi Docker/sanal surucu bozulmaz", {"overlay", "virtio_net", "br_netfilter"} <= set(lines))
    rc, out = play([cp], vars_=fake)
    check("ikinci kosu changed=0", "changed=0" in out, out[-150:])
    f.write_text("x\n", encoding="utf-8")
    off = dict(rm); off["ansible.builtin.file"] = dict(rm["ansible.builtin.file"], path=str(f)); off.pop("when", None)
    play([off])
    check("dosya kaldirilir (secenek kapali)", not f.exists())

# ---- verify_access ----
vt = load("roles/hardening_verify_access/tasks/main.yml")[0]["block"]
vc = next(t for t in vt if t.get("name", "").startswith("Open a NEW SSH connection from the controller"))
argv_tpl = vc["ansible.builtin.command"]["argv"].strip()
expr = argv_tpl[2:-2].strip() if argv_tpl.startswith("{{") else None
check("argv bir Jinja ifadesi", expr is not None)


def argv_for(host_vars, extra_args=None):
    fake = {"hardening_verify_access_user": {"stdout": "ali"}}
    if extra_args is not None:
        fake["hardening_verify_access_ssh_extra_args"] = extra_args
    rc, out = play([{"ansible.builtin.debug": {"msg": "ARGV={{ (" + expr + ") | to_json }}"}}], vars_=fake, extra=host_vars)
    for line in out.splitlines():
        if "ARGV=" in line:
            return json.loads(line.split("ARGV=", 1)[1].strip().rstrip('",').replace('\\"', '"'))
    return None


a = argv_for({"ansible_host": "192.0.2.10", "ansible_user": "ali", "ansible_ssh_private_key_file": "/k/id1"})
check("ansible_ssh_private_key_file: -i <anahtar> ve IdentitiesOnly=yes", a is not None and a[a.index("-i") + 1] == "/k/id1" and "IdentitiesOnly=yes" in a, str(a))
a = argv_for({"ansible_host": "192.0.2.10", "ansible_user": "ali", "ansible_private_key_file": "/k/id2"})
check("ansible_private_key_file (takma ad) da ayni sekilde calisir", a is not None and a[a.index("-i") + 1] == "/k/id2" and "IdentitiesOnly=yes" in a, str(a))
a = argv_for({"ansible_host": "192.0.2.10", "ansible_user": "ali"})
check("anahtar dosyasi yoksa -i EKLENMEZ (ssh-agent kullanimi bozulmaz)", a is not None and "-i" not in a, str(a))
a = argv_for({"ansible_host": "192.0.2.10", "ansible_user": "ali"}, extra_args=["-o", "IdentityAgent=/tmp/agent.sock"])
check("hardening_verify_access_ssh_extra_args argv'ye eklenir, kullanici@sunucu'dan ONCE", a is not None and "IdentityAgent=/tmp/agent.sock" in a and a.index("IdentityAgent=/tmp/agent.sock") < a.index("ali@192.0.2.10") and a[-2:] == ["ali@192.0.2.10", "true"], str(a))
a = argv_for({"ansible_host": "192.0.2.10", "ansible_user": "ali", "ansible_ssh_common_args": "-o IdentitiesOnly=yes -i /k/id3"})
check("ansible_ssh_common_args da kullanilir (sshpocket tek anahtar verebilir)", a is not None and "/k/id3" in a and a[-2:] == ["ali@192.0.2.10", "true"], str(a))
check("her durumda BatchMode, coklama yok, publickey", a is not None and all(x in a for x in ("BatchMode=yes", "ControlMaster=no", "PreferredAuthentications=publickey")))

fm = next(t for t in load("roles/hardening_verify_access/tasks/main.yml")[0]["rescue"] if t.get("name") == "Stop with a clear message (önceki duruma dönüldü)")["ansible.builtin.fail"]["msg"]
for stderr, want in (("Received disconnect: Too many authentication failures", True), ("Permission denied (publickey).", False), ("", False)):
    rc, out = play([{"ansible.builtin.debug": {"msg": "OUT=" + fm}}], vars_={"hardening_verify_access_new_connection": {"stderr": stderr}})
    check(f"'Too many authentication failures' ipucu yalniz bu hatada ({stderr[:30]!r} -> {want})", ("İPUCU" in out) == want, out[-200:])
rc, out = play([{"ansible.builtin.debug": {"msg": "OUT=" + fm}}], vars_={})
check("new_connection tanimsizken (baska hata) mesaj yine uretilir", rc == 0 and "ÖNCEKİ DURUMA DÖNÜLDÜ" in out, out[-200:])

# ---- Proxmox'ta modul kilidi REDDEDILIR (sshpocket 0.8.1 turu: veth/KVM/bridge/softdog yuklenemez) ----
ref = by["Refuse the module lock on a Proxmox VE host"]
check("Proxmox reddi: sysctl yazilmadan ONCE", names.index("Refuse the module lock on a Proxmox VE host") < names.index("Apply sysctl hardening"))
for platform, is_pve, lock, ok in (("generic", False, True, True), ("generic", False, False, True), ("proxmox-host", True, False, True), ("proxmox-host", True, True, False), ("raspberry-pi", False, True, True), ("generic", True, True, False)):
    rc, out = play([ref], extra={"hardening_platform": platform, "hardening_is_proxmox": is_pve, "hardening_kernel_modules_disabled": lock})
    check(f"platform={platform} proxmox={is_pve} modul_kilidi={lock} -> {'kabul' if ok else 'RED'}", (rc == 0) == ok, out[-200:])
rc, out = play([ref], extra={"hardening_platform": "proxmox-host", "hardening_kernel_modules_disabled": True})
check("ret mesaji veth/softdog nedenini ve 'hicbir sey yazilmadi'yi soyler", rc != 0 and "softdog" in out and "veth" in out and "hiçbir şey yazılmadı" in out, out[-300:])

comp = load("component.yml")
cv = {v["name"]: v for v in comp["vars"] if isinstance(v, dict)}
check("component.yml: hardening_ssh_max_sessions min 1 max 10", (cv["hardening_ssh_max_sessions"].get("min"), cv["hardening_ssh_max_sessions"].get("max")) == (1, 10))
check("component.yml: hardening_auditd_backlog_limit min 0 (negatif olmaz)", cv["hardening_auditd_backlog_limit"].get("min") == 0)

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
