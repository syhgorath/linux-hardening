#!/usr/bin/env python3
"""hardening_aide: günlük kontrol zamanlayıcısı (CIS 6.3.2). Yalnızca zamanlayıcıyı açık tutar; AIDE'nin yaptığı işi (COMMAND=update, veritabanı) DEĞİŞTİRMEZ."""
import sys
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


tasks = load("roles/hardening_aide/tasks/main.yml")
t = next((x for x in tasks if "systemd" in " ".join(x) or "ansible.builtin.systemd" in x), None)
check("zamanlayici gorevi var", True, t is not None)
m = t["ansible.builtin.systemd"]
check("dailyaidecheck.timer: enabled + started", ("dailyaidecheck.timer", True, "started"), (m["name"], m["enabled"], m["state"]))
check("kendi degiskeniyle kapanir", True, "hardening_aide_scheduled_check" in str(t["when"]))
check("varsayilan ACIK (paket zaten acik kurar, changed=0)", True, load("roles/hardening_aide/defaults/main.yml")["hardening_aide_scheduled_check"])
src = (ROOT / "roles/hardening_aide/tasks/main.yml").read_text(encoding="utf-8")
check("AIDE isi degismez: /etc/default/aide ve aide.conf'a dokunulmaz", False, "/etc/default/aide" in src or "lineinfile" in src or "aide.conf" in src)
v = next((x for x in load("component.yml")["vars"] if isinstance(x, dict) and x["name"] == "hardening_aide_scheduled_check"), None)
check("component.yml: bool, varsayilan true, warn_if YOK (#74)", True, bool(v) and v["type"] == "bool" and v["default"] is True and "warn_if" not in v)
check("--check + paket kurulacaksa (birim yok) zamanlayici gorevi ATLANIR", True, "ansible_check_mode" in str(t["when"]) and "hardening_aide_install" in str(t["when"]))
inst = next(x for x in tasks if "ansible.builtin.apt" in x)
check("kurulum sonucu kaydedilir (register)", "hardening_aide_install", inst.get("register"))
print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
