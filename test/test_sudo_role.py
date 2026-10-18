#!/usr/bin/env python3
"""hardening_sudo: sudoers drop-in güvenli yazılır (visudo ile doğrulanır, ana /etc/sudoers'a dokunulmaz), sonrasında become denenir, başarısızlıkta temizlenir ve durur.

Yanlış sudoers erişimi keser; bu yüzden hem yapı (statik) hem de ÜRETİLEN içerik gerçek `visudo -cf` ile doğrulanır (visudo yoksa o kısım atlanır ve söylenir).
"""
import os
import re
import shutil
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


tasks = yaml.safe_load((ROOT / "roles/hardening_sudo/tasks/main.yml").read_text(encoding="utf-8"))
defaults = yaml.safe_load((ROOT / "roles/hardening_sudo/defaults/main.yml").read_text(encoding="utf-8"))
raw = (ROOT / "roles/hardening_sudo/tasks/main.yml").read_text(encoding="utf-8")
wrapper = tasks[0]
inner = wrapper["block"]
mod = lambda t: next(k for k in t if k.startswith("ansible.builtin."))

check("varsayilan: rol acik, logfile /var/log/sudo.log", defaults == {"hardening_sudo_enabled": True, "hardening_sudo_logfile": "/var/log/sudo.log"}, f"defaults={defaults}")
check("tum gorevler hardening_sudo_enabled ile kapatilabilir", "hardening_sudo_enabled" in str(wrapper.get("when")))

cp = next(t for t in inner if "ansible.builtin.copy" in t)["ansible.builtin.copy"]
detect = next(t for t in inner if "ansible.builtin.command" in t and "visudo --version" in str(t["ansible.builtin.command"]))
check("sudo gerceklemesi visudo --version ile ALGILANIR (sudo-rs 'logfile' desteklemez: gercek VM'de goruldu)",
      detect.get("become") is False and detect.get("check_mode") is False and detect.get("failed_when") is False and detect.get("changed_when") is False)
check("algilama 'visudo-rs' metnine bakar", "visudo-rs" in raw)
check("sudoers dosyasi /etc/sudoers.d/ altina yazilir (ana /etc/sudoers'a degil)", cp["dest"].startswith("/etc/sudoers.d/") and cp["dest"] != "/etc/sudoers")
check("mod 0440, sahip root:root", (cp["mode"], cp["owner"], cp["group"]) == ("0440", "root", "root"), str(cp))
check("visudo -cf ile DOGRULANIR (validate)", "visudo -cf %s" in str(cp.get("validate")), str(cp.get("validate")))
check("/etc/sudoers dosyasina lineinfile/blockinfile/replace ile dokunulmaz", not re.search(r"(lineinfile|blockinfile|replace):[\s\S]{0,80}/etc/sudoers\b(?!\.d)", raw))

content = cp["content"]
for needle, why in (("Defaults use_pty", "CIS 5.2.2"), ("Defaults timestamp_timeout=15", "CIS 5.2.6 (en cok 15)")):
    check(f"icerik: {needle} ({why})", needle in content)
check("icerik: logfile yalniz klasik sudo'da (if not hardening_sudo_is_rs)", re.search(r"\{% if not hardening_sudo_is_rs %\}\s*Defaults logfile=.*\s*\{% endif %\}", content) is not None)
check("icerikte 'NOPASSWD'/'!authenticate' YOK (parolasiz sudo acilmaz)", "NOPASSWD" not in content and "!authenticate" not in content)
m = re.search(r"timestamp_timeout=(-?\d+)", content)
check("timestamp_timeout 0..15 araliginda (negatif = hic sormaz, 15'ten buyuk CIS'e aykiri)", bool(m) and 0 <= int(m.group(1)) <= 15)

names = [t.get("name") for t in inner]
probe = next(t for t in inner if "ansible.builtin.command" in t and "id -u" in str(t["ansible.builtin.command"]))
check("yazdiktan SONRA become denemesi var", names.index(probe["name"]) > 0 and probe.get("become") is True)
check("become denemesi basarisizsa gorev duser (failed_when)", "failed_when" in probe and "'0'" in str(probe["failed_when"]))
check("become denemesi --check'te atlanir, degisiklik saymaz", "ansible_check_mode" in str(probe.get("when")) and probe.get("changed_when") is False)
rescue = wrapper.get("rescue") or []
check("rescue: dosya silinmeye calisilir", any(t.get("ansible.builtin.file", {}).get("state") == "absent" and t["ansible.builtin.file"]["path"] == cp["dest"] for t in rescue))
check("rescue: silme basarisiz olsa bile mesaj gelir ve rol DURUR (fail)", any("ansible.builtin.fail" in t for t in rescue))
scan = next(t for t in inner if "ansible.builtin.shell" in t)
check("!authenticate taramasi salt okunur (grep), changed_when=false, --check'te de calisir", "grep" in str(scan["ansible.builtin.shell"]) and scan.get("changed_when") is False and scan.get("check_mode") is False)
check("!authenticate yalnizca UYARIR, sudoers'i degistirmez", not any("!authenticate" in str(t.get("ansible.builtin.lineinfile", "")) for t in inner))

play = yaml.safe_load((ROOT / "playbooks/harden.yml").read_text(encoding="utf-8"))[0]
roles = [r.get("role") for r in play["roles"] if isinstance(r, dict)]
entry = next((r for r in play["roles"] if isinstance(r, dict) and r.get("role") == "hardening_sudo"), None)
check("harden.yml'de rol var, etiketi `sudo`", entry is not None and entry.get("tags") == ["sudo"])
check("sudo, ssh'tan SONRA (en sonda)", roles.index("hardening_sudo") > roles.index("hardening_ssh"))

# Üretilen içerik (iki sudo türü için) gerçek visudo ile doğrulanır; sudo-rs içeriğinde `logfile` OLMAMALI
visudo = shutil.which("visudo") or ("/usr/sbin/visudo" if Path("/usr/sbin/visudo").exists() else None)
for is_rs in (False, True):
    label = "sudo-rs" if is_rs else "klasik sudo"
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {**defaults, "hardening_sudo_is_rs": is_rs},
                                       "tasks": [{"ansible.builtin.copy": {"dest": f"{d}/out", "content": content}}]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        check(f"{label}: icerik render edildi", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
        out = Path(f"{d}/out").read_text(encoding="utf-8") if Path(f"{d}/out").exists() else ""
        check(f"{label}: logfile satiri " + ("YOK" if is_rs else "VAR"), ("logfile" in out) == (not is_rs), out)
        check(f"{label}: use_pty ve timestamp_timeout=15 var", "Defaults use_pty" in out and "Defaults timestamp_timeout=15" in out)
        if visudo:
            ok = subprocess.run([visudo, "-cf", f"{d}/out"], capture_output=True, text=True)
            check(f"{label}: uretilen sudoers visudo -cf ile gecerli (bu makinenin visudo'su)", ok.returncode == 0, ok.stdout + ok.stderr)
            Path(f"{d}/bad").write_text(out + "Defaults bu_gecersiz_secenek_yok\n")
            bad = subprocess.run([visudo, "-cf", f"{d}/bad"], capture_output=True, text=True)
            check(f"{label}: visudo gecersiz icerigi gercekten reddeder (dogrulayici calisiyor)", bad.returncode != 0)
if not visudo:
    print("  --   visudo bulunamadi: uretilen icerik dogrulanmadi (atlandi)")

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
