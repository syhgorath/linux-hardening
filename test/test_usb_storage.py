#!/usr/bin/env python3
"""hardening_disable_usb_storage: varsayılan true (bugünkü davranış); false iken kural dosyası SİLİNİR ve USB depolama tekrar kullanılabilir.

Görevler gerçek `ansible-playbook` ile, hedef yolu geçici dizine çevrilerek çalıştırılır.
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


tasks = yaml.safe_load((ROOT / "roles/hardening_base/tasks/main.yml").read_text(encoding="utf-8"))
off = next(t for t in tasks if t.get("name") == "Disable usb-storage")
on = next(t for t in tasks if t.get("name") == "Allow usb-storage (remove this role's rule file)")
defaults = yaml.safe_load((ROOT / "roles/hardening_base/defaults/main.yml").read_text(encoding="utf-8"))
check("varsayilan: usb-storage KAPALI (engelli), yani bugunku davranis", True, defaults["hardening_disable_usb_storage"])
check("iki gorev ayni dosyayi yonetir", off["ansible.builtin.copy"]["dest"], on["ansible.builtin.file"]["path"])
comp = yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))
v = next((x for x in comp["vars"] if isinstance(x, dict) and x["name"] == "hardening_disable_usb_storage"), None)
check("component.yml: bool, varsayilan true", True, bool(v) and v["type"] == "bool" and v["default"] is True)


def run(d, flag):
    cp = dict(off["ansible.builtin.copy"]); cp["dest"] = f"{d}/60-hardening-usb.conf"; cp.pop("owner"); cp.pop("group")
    fl = dict(on["ansible.builtin.file"]); fl["path"] = f"{d}/60-hardening-usb.conf"
    pb = Path(d) / "p.yml"
    pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_disable_usb_storage": flag},
                                   "tasks": [{"ansible.builtin.copy": cp, "when": off["when"]}, {"ansible.builtin.file": fl, "when": on["when"]}]}]), encoding="utf-8")
    r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    return r.returncode, r.stdout


with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "60-hardening-usb.conf"
    rc, _ = run(d, True)
    check("true: kural dosyasi yazilir (install + blacklist)", True, f.exists() and "install usb-storage /bin/false" in f.read_text() and "blacklist usb-storage" in f.read_text())
    rc, out = run(d, True)
    check("true: ikinci kosu changed=0 (idempotent)", True, "changed=0" in out)
    rc, out = run(d, False)
    check("false: kural dosyasi SILINIR (USB depolama tekrar kullanilabilir)", False, f.exists())
    rc, out = run(d, False)
    check("false: ikinci kosu changed=0, dosya yokken hata yok", (0, True), (rc, "changed=0" in out))
    rc, _ = run(d, True)
    check("tekrar true: dosya geri yazilir", True, f.exists())

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
