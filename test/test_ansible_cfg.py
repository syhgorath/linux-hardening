#!/usr/bin/env python3
"""ansible.cfg: ölü bağlantıda koşunun takılmaması için ssh canlılık seçenekleri; Ansible'ın varsayılan ssh_args'ı (ControlMaster/ControlPersist) EZİLMEZ.

Gerçek vaka: kontrol makinesi ağ değiştirdi ve `ansible-playbook` 14 dakika takıldı (docs/verification-log.md madde 19). Mini labda sessiz paket düşürmeyle ölçüldü:
seçenek yokken ansible 153 sn sonra, varken 58 sn sonra pes etti (gerçek ağ değişiminde fark daha büyüktü).
"""
import configparser
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fails = 0


def check(name, want, got):
    global fails
    if want == got:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}: beklenen={want!r} gercek={got!r}")


cp = configparser.ConfigParser(interpolation=None)
cp.read(ROOT / "ansible.cfg", encoding="utf-8")
extra = cp.get("ssh_connection", "ssh_extra_args", fallback="")
m_i = re.search(r"ServerAliveInterval=(\d+)", extra)
m_c = re.search(r"ServerAliveCountMax=(\d+)", extra)
check("ssh_extra_args: ServerAliveInterval ve ServerAliveCountMax tanimli", (True, True), (bool(m_i), bool(m_c)))
if m_i and m_c:
    total = int(m_i.group(1)) * int(m_c.group(1))
    check("olu baglanti 120 sn'den kisa surede dusuyor (interval*count)", True, 0 < total <= 120)
    check("cok agresif degil: en az 30 sn (gecici ag takilmalarinda yanlis kopma olmasin)", True, total >= 30)
check("ssh_args EZILMIYOR (ControlMaster/ControlPersist varsayilani kalir)", False, cp.has_option("ssh_connection", "ssh_args"))

env = {**os.environ, "ANSIBLE_CONFIG": str(ROOT / "ansible.cfg")}
r = subprocess.run(["ansible-config", "dump", "-t", "connection", "ssh"], capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env, cwd=ROOT)
out = r.stdout + r.stderr
check("Ansible ayari gercekten okur (ssh_extra_args)", True, "ssh_extra_args(" in out and "ServerAliveInterval" in out)
check("Ansible'in etkin ssh_args'i hala ControlMaster/ControlPersist iceriyor", True, bool(re.search(r"ssh_args\(default\) = .*ControlMaster=auto.*ControlPersist", out)))

# test yapilandirmasi (become yok) ayri kalir ve bu ayardan etkilenmez
tcfg = (ROOT / "test/ansible-test.cfg").read_text(encoding="utf-8")
check("test/ansible-test.cfg ssh ayari icermez (testler yerel baglanti kullanir)", False, "ssh_connection" in tcfg)

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
