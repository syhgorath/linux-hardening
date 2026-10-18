#!/usr/bin/env python3
"""CIS grup 2 (davranışı değiştirenler, hepsi VARSAYILAN KAPALI): core dump, telnet/ftp kaldırma, kabuk TMOUT, parola INACTIVE.

Görevlerin kendi assert/when/içerik ifadeleri gerçek `ansible-playbook` ile çalıştırılır. Asıl güvence: varsayılan hiçbir şey yapmaz (kapalı), değer sınırları dışarıda kalır,
`apt` yalnızca `remove` yapar (purge/autoremove YOK), INACTIVE mevcut hesaplara DOKUNMAZ.
"""
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


def play(tasks, vars_=None):
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": vars_ or {}, "tasks": tasks}], allow_unicode=True), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


def runs(t, vars_, pre=None):
    """Görevin `when` ifadesi doğru mu? (aynı ifadeyle bir debug görevi)"""
    rc, out = play((pre or []) + [{"name": "probe", "ansible.builtin.debug": {"msg": "calisti"}, "when": t["when"]}], vars_)
    return "calisti" in out


# 1) varsayılanlar: HEPSİ KAPALI
check("varsayilan: core dump kapatma KAPALI", False, load("roles/hardening_kernel/defaults/main.yml")["hardening_disable_coredump"])
bd = load("roles/hardening_base/defaults/main.yml")
check("varsayilan: telnet/ftp kaldirma KAPALI", False, bd["hardening_remove_legacy_clients"])
ad = load("roles/hardening_auth/defaults/main.yml")
check("varsayilan: TMOUT 0 (kapali), INACTIVE 0 (kapali)", (0, 0), (ad["hardening_shell_timeout_seconds"], ad["hardening_password_inactive_days"]))
fd = load("roles/hardening_files/defaults/main.yml")
check("varsayilan: gunluk dosyasi izinleri KAPALI", False, fd["hardening_log_file_permissions"])

# 2) core dump
for n, var_ok in (("Disable core dumps (limits)", True), ("Ensure systemd-coredump drop-in directory", True), ("Disable systemd-coredump storage", True)):
    t = task("hardening_kernel", n)
    check(f"{n}: kendi degiskeniyle kapanir", True, "hardening_disable_coredump" in str(t["when"]))
lim = task("hardening_kernel", "Disable core dumps (limits)")["ansible.builtin.copy"]
check("limits: '* hard core 0', /etc/security/limits.d/ altinda", True, "* hard core 0" in lim["content"] and lim["dest"].startswith("/etc/security/limits.d/"))
cd = task("hardening_kernel", "Disable systemd-coredump storage")["ansible.builtin.copy"]
check("systemd-coredump: [Coredump] Storage=none ProcessSizeMax=0", True, all(x in cd["content"] for x in ("[Coredump]", "Storage=none", "ProcessSizeMax=0")))
check("sysctl'e core_pattern/suid_dumpable DISINDA dokunulmaz", True, "core_pattern" not in (ROOT / "roles/hardening_kernel/templates/sysctl.conf.j2").read_text(encoding="utf-8"))

# 3) telnet/ftp kaldırma
ap = task("hardening_base", "Remove legacy plaintext clients (telnet, ftp)")
a = ap["ansible.builtin.apt"]
check("apt: state absent, purge false, autoremove false (ayar dosyalarina ve bagimli paketlere dokunulmaz)", True, a["state"] == "absent" and a["purge"] is False and a["autoremove"] is False)
check("kendi degiskeniyle kapanir", True, "hardening_remove_legacy_clients" in str(ap["when"]))
pk = bd["hardening_legacy_client_packages"]
check("paket listesi yalniz telnet/ftp istemcileri (sshd, openssh vb. YOK)", True, set(pk) <= {"telnet", "telnet-ssl", "inetutils-telnet", "ftp", "ftp-ssl", "tnftp", "inetutils-ftp", "pftp", "ubuntu-standard"} and {"telnet", "ftp", "ftp-ssl", "telnet-ssl"} <= set(pk))
check("ubuntu-standard listede (yoksa apt bir istemciyi kaldirinca digerini kurar: ping-pong)", True, "ubuntu-standard" in pk)
check("apt gorevi paket adini listeden alir", True, a["name"] == "{{ hardening_legacy_client_packages }}")

# 4) kabuk TMOUT
va = task("hardening_auth", "Validate shell timeout")["ansible.builtin.assert"]
for val, ok in ((0, True), (1, True), (600, True), (900, True), (901, False), (-1, False), ("abc", False)):
    rc, _ = play([{"ansible.builtin.assert": va}], {"hardening_shell_timeout_seconds": val})
    check(f"TMOUT {val!r}: " + ("kabul" if ok else "REDDEDILIR"), ok, rc == 0)
tm = task("hardening_auth", "Idle shell timeout (TMOUT)")
check("TMOUT 0 iken dosya yazilmaz", False, runs(tm, {"hardening_shell_timeout_seconds": 0}))
check("TMOUT 300 iken dosya yazilir", True, runs(tm, {"hardening_shell_timeout_seconds": 300}))
with tempfile.TemporaryDirectory() as d:
    cp = dict(tm["ansible.builtin.copy"]); cp["dest"] = f"{d}/tmout.sh"
    rc, _ = play([{"ansible.builtin.copy": cp}], {"hardening_shell_timeout_seconds": 600})
    body = Path(f"{d}/tmout.sh").read_text(encoding="utf-8")
    check("TMOUT icerigi: readonly TMOUT=600 ve export", True, "readonly TMOUT=600\n" in body and "export TMOUT" in body)
    sh = subprocess.run(["bash", "-c", f". {d}/tmout.sh; echo $TMOUT; TMOUT=1 2>&1; echo rc=$?"], capture_output=True, text=True)
    check("kabukta TMOUT=600 ve readonly (kullanici gevsetemez)", True, sh.stdout.splitlines()[0] == "600" and "readonly" in (sh.stderr + sh.stdout))

# 5) parola INACTIVE
vi = task("hardening_auth", "Validate password inactive days")["ansible.builtin.assert"]
for val, ok in ((0, True), (45, True), (365, True), (366, False), (-1, False), ("x", False)):
    rc, _ = play([{"ansible.builtin.assert": vi}], {"hardening_password_inactive_days": val})
    check(f"INACTIVE {val!r}: " + ("kabul" if ok else "REDDEDILIR"), ok, rc == 0)
setd = task("hardening_auth", "Set the default INACTIVE for new accounts")
def reg(out):
    return [{"ansible.builtin.set_fact": {"hardening_auth_inactive_now": {"stdout": out}}}]
check("INACTIVE kapaliyken (0) hicbir sey yapilmaz", False, runs(setd, {"hardening_password_inactive_days": 0}, reg("GROUP=100\nINACTIVE=-1\n")))
check("INACTIVE=-1 iken 45 hedefi: useradd -D calisir", True, runs(setd, {"hardening_password_inactive_days": 45}, reg("GROUP=100\nINACTIVE=-1\nEXPIRE=\n")))
check("INACTIVE zaten 45 iken calismaz (idempotent)", False, runs(setd, {"hardening_password_inactive_days": 45}, reg("GROUP=100\nINACTIVE=45\nEXPIRE=\n")))
check("useradd -D YALNIZ varsayilani degistirir (mevcut hesaplara chage/usermod YOK)", True, "chage" not in str(setd) and "usermod" not in str(setd))
lst = task("hardening_auth", "List existing accounts whose INACTIVE differs (read-only)")
check("mevcut hesap listesi salt okunur, --check'te de calisir", True, lst.get("changed_when") is False and lst.get("check_mode") is False)
with tempfile.TemporaryDirectory() as d:
    shadow = Path(d) / "shadow"
    shadow.write_text("root:*:20000:0:99999:7:::\nalice:$y$j9T$abc:20000:0:99999:7:45::\nbob:$y$j9T$def:20000:0:99999:7:::\ncarol:$6$salt$hash:20000:0:99999:7:30::\nlocked:!:20000:0:99999:7:::\nnologinuser:!$6$x:20000:0:99999:7:::\n", encoding="utf-8")
    rc, out = play([lst | {"register": "res"}, {"ansible.builtin.debug": {"msg": "LISTE={{ res.stdout_lines | join(',') }}"}}] if False else
                   [{"ansible.builtin.shell": lst["ansible.builtin.shell"], "register": "res"}, {"ansible.builtin.debug": {"msg": "LISTE={{ res.stdout_lines | join(',') }}"}}],
                   {"hardening_password_inactive_days": 45, "hardening_auth_shadow_path": str(shadow)})
    line = next((l for l in out.splitlines() if "LISTE=" in l), "")
    check("INACTIVE farkli hesaplar: yalniz parolasi OLAN (hash) ve degeri 45 olmayanlar (bob, carol)", True, "LISTE=bob,carol" in line.replace(" ", ""))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
