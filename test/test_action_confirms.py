#!/usr/bin/env python3
"""Eylem onay düzeyleri (component.yml + türetilmiş component.json).

`apply` bilinçli olarak evet/hayır ister (önizleme şartıyla); diğer değiştiren eylemler sunucu adını yazdırmaya devam eder.
Tablo tam eşleşir: yeni eylem eklenince onay düzeyi burada açıkça yazılmalı.
"""
import json
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


WANT = {
    "audit": "yes-no",
    "preview": "none",
    "apply": "yes-no",
    "pve_firewall_preview": "none",
    "pve_firewall_apply": "type-server-name",
    "rollback_status": "none",
    "rollback_disarm": "type-server-name",
    "rollback_now": "type-server-name",
    "kaldir_onizle": "none",
    "kaldir": "type-server-name",
    "kaldir_geri_yukle": "type-server-name",
}

for fname, comp in (
    ("component.yml", yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))),
    ("component.json", json.loads((ROOT / "component.json").read_text(encoding="utf-8"))),
):
    acts = comp["actions"]
    check(f"{fname}: eylem onaylari", WANT, {n: a.get("confirm") for n, a in acts.items()})
    check(f"{fname}: apply onizleme sarti ve uyarilar duruyor", (["preview"], True), (acts["apply"].get("requires"), bool(acts["apply"].get("warnings"))))

print("TAMAM" if not fails else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
