#!/usr/bin/env python3
"""fail2ban ignoreip: YALNIZ hardening_fail2ban_ignoreip (otomatik adres yok) + bağlı adres için tek satırlık NOT. Gerçek Ansible, gerçek görev dosyası ve filtre."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "filter_plugins"))
from hardening_net import hardening_ignoreip_effective, hardening_ip_in_list  # noqa: E402

fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {str(detail)[-700:]}")


# --- filtre: efektif ignoreip (yerel adresler HER ZAMAN, kullanici degeri EKLENIR) ---
for name, extra, want in [
    ("bos: yalniz yerel adresler", "", "127.0.0.1/8 ::1"),
    ("None: yalniz yerel adresler", None, "127.0.0.1/8 ::1"),
    ("ek adresler yerel adreslerin ardindan (ezmez)", "10.1.10.0/24 10.99.0.0/24", "127.0.0.1/8 ::1 10.1.10.0/24 10.99.0.0/24"),
    ("virgul de ayirici, ciktida bosluk", "10.1.10.0/24,10.99.0.0/24", "127.0.0.1/8 ::1 10.1.10.0/24 10.99.0.0/24"),
    ("kullanici yerel adresi yazarsa tekrar yok", "127.0.0.1/8 ::1 192.0.2.9", "127.0.0.1/8 ::1 192.0.2.9"),
    ("ayni adres iki kez tek kez", "192.0.2.9 192.0.2.9", "127.0.0.1/8 ::1 192.0.2.9"),
    ("fazla bosluk/satir sonu", "  192.0.2.9 \n", "127.0.0.1/8 ::1 192.0.2.9"),
]:
    check(f"efektif: {name}", hardening_ignoreip_effective(extra) == want, hardening_ignoreip_effective(extra))

# --- filtre: CIDR üyeliği ---
for name, addr, lst, want in [
    ("adres listede (tam)", "10.99.0.4", "127.0.0.1/8 ::1 10.99.0.4", True),
    ("adres CIDR içinde", "10.99.0.4", "127.0.0.1/8 10.99.0.0/24", True),
    ("adres CIDR dışında", "10.1.10.190", "127.0.0.1/8 ::1 10.99.0.0/24", False),
    ("IPv6 CIDR içinde", "fd00::5", "::1 fd00::/8", True),
    ("IPv4 adresi IPv6 listesine uymaz", "10.1.2.3", "::1 fd00::/8", False),
    ("varsayilan: uzak adres muaf degil", "192.0.2.9", "127.0.0.1/8 ::1", False),
    ("bozuk girdi yok sayilir", "192.0.2.9", "ornek.test 10.0.0.1-10.0.0.9 file:/x", False),
    ("bozuk adres False", "yok", "127.0.0.1/8", False),
    ("bos liste", "192.0.2.9", "", False),
]:
    check(f"filtre: {name}", hardening_ip_in_list(addr, lst) is want, (addr, lst))


def run(conn, ignoreip="", extra=None):
    """Gerçek ignoreip_bilgi.yml'yi çalıştırır; SSH_CONNECTION conn ile verilir (None = tanımsız)."""
    base = Path(tempfile.mkdtemp())
    play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
             "vars": {"hardening_fail2ban_ignoreip": ignoreip, "hardening_fail2ban_maxretry": 5, "hardening_fail2ban_bantime": "10m", **(extra or {})},
             "tasks": [{"ansible.builtin.include_tasks": str(ROOT / "roles/hardening_fail2ban/tasks/ignoreip_bilgi.yml")}]}]
    (base / "t.yml").write_text(yaml.safe_dump(play), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k != "SSH_CONNECTION"}
    env.update({"ANSIBLE_CONFIG": str(ROOT / "ansible.cfg"), "ANSIBLE_BECOME": "False", "ANSIBLE_FILTER_PLUGINS": str(ROOT / "filter_plugins")})
    if conn is not None:
        env["SSH_CONNECTION"] = conn
    r = subprocess.run(["ansible-playbook", "-i", "localhost,", str(base / "t.yml")], capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env, cwd=base)
    return r, r.stdout + r.stderr


r, out = run("10.99.0.4 5555 10.99.0.9 22")
check("muaf olmayan adres: NOT satiri, adres ve ceza yazili", r.returncode == 0 and "NOT (fail2ban): Bağlı olduğun adres (10.99.0.4)" in out and "maxretry=5" in out and "bantime=10m" in out, out)
check("NOT satiri UYARI ile baslamaz (uyari sayisini artirmaz)", "UYARI" not in out, out)
check("NOT satiri tek satir", sum("fail2ban dan" in x or "Bağlı olduğun adres" in x for x in out.splitlines()) == 1, out)

r, out = run("127.0.0.1 5555 127.0.0.1 22")
check("yerel baglanti (varsayilan bos ignoreip): satir cikmaz", r.returncode == 0 and "Bağlı olduğun adres" not in out, out)

r, out = run("10.99.0.4 5555 10.99.0.9 22", ignoreip="10.99.0.0/24")
check("adres ignoreip CIDR'inde: satir cikmaz", r.returncode == 0 and "Bağlı olduğun adres" not in out, out)

r, out = run("10.99.0.4 5555 10.99.0.9 22", extra={"hardening_ssh_allow_from": ["10.99.0.0/24"]})
check("hardening_ssh_allow_from ignoreip'e otomatik girmez: satir yine cikar", "Bağlı olduğun adres (10.99.0.4)" in out, out)

r, out = run(None)
check("SSH_CONNECTION yok: satir yok, rol durmaz", r.returncode == 0 and "Bağlı olduğun adres" not in out, out)

# --- şablon: ignoreip yalnız değişkenden ---
tmpl = (ROOT / "roles/hardening_fail2ban/templates/sshd.local.j2").read_text(encoding="utf-8")
check("sablon efektif ignoreip suzgecini kullanir, allow_from yok", "hardening_fail2ban_ignoreip | hardening_ignoreip_effective" in tmpl and "allow_from" not in tmpl, tmpl)
main = (ROOT / "roles/hardening_fail2ban/tasks/main.yml").read_text(encoding="utf-8")
check("rol ignoreip'i hesaplamaz (set_fact yok)", "ignoreip_effective" not in main and "hardening_fail2ban_ignoreip" not in main.replace("ignoreip_bilgi", ""), main)
dflt = yaml.safe_load((ROOT / "roles/hardening_fail2ban/defaults/main.yml").read_text(encoding="utf-8"))
check("varsayilan ignoreip bos (yerel adresler koddan), bantime 10m", dflt["hardening_fail2ban_ignoreip"] == "" and dflt["hardening_fail2ban_bantime"] == "10m", dflt)

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
