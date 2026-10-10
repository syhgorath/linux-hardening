#!/usr/bin/env python3
"""Her `notify:` değeri, aynı rolün handlers/main.yml içinde birebir bir handler adıyla eşleşmeli.

Handler yeniden adlandırılıp notify güncellenmezse Ansible handler'ı sessizce çalıştırmaz ya da hata verir.
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
fails = 0
total_notify = 0


def walk(tasks):
    for t in tasks or []:
        if not isinstance(t, dict):
            continue
        yield t
        for k in ("block", "rescue", "always"):
            yield from walk(t.get(k))


for role in sorted((ROOT / "roles").glob("hardening_*")):
    handlers_file = role / "handlers/main.yml"
    handlers = set()
    if handlers_file.exists():
        for h in yaml.safe_load(handlers_file.read_text(encoding="utf-8")) or []:
            handlers.add(h["name"])
            for lt in ([h.get("listen")] if isinstance(h.get("listen"), str) else (h.get("listen") or [])):
                handlers.add(lt)
    tasks_file = role / "tasks/main.yml"
    if not tasks_file.exists():
        continue
    for t in walk(yaml.safe_load(tasks_file.read_text(encoding="utf-8"))):
        n = t.get("notify")
        if n is None:
            continue
        for name in ([n] if isinstance(n, str) else n):
            total_notify += 1
            if name in handlers:
                print(f"  ok   {role.name}: notify '{name}'")
            else:
                fails += 1
                print(f"  FAIL {role.name}: notify '{name}' için handler yok (var: {sorted(handlers)})")

if total_notify == 0:
    fails += 1
    print("  FAIL hic notify bulunamadi (test bozuk olabilir)")
print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
