#!/usr/bin/env python3
"""audit.yml içindeki özet/izin görevlerini (YAML'dan çıkarılıp çalıştırılır) sentetik Lynis raporuyla sınar."""
import json
import os
import shutil
import stat
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


def run(report_text, label):
    pb = yaml.safe_load((ROOT / "playbooks/audit.yml").read_text(encoding="utf-8"))
    names = ("Create scan directories", "Restrict fetched", "Summary:")
    tasks = [t for t in pb[0]["tasks"] if str(t.get("name", "")).startswith(names)]
    check(f"{label}: audit.yml'den 5 gorev cikarildi", 5, len(tasks))
    with tempfile.TemporaryDirectory() as d:
        scan = Path(d) / "scans" / "ornek-host" / "20260101-000000"
        scan.mkdir(parents=True)
        (scan / "lynis-report.dat").write_text(report_text, encoding="utf-8")
        (scan / "lynis.log").write_text("", encoding="utf-8")
        play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
                 "vars": {"inventory_hostname_override": "x"}, "tasks": tasks}]
        p = Path(d) / "p.yml"
        p.write_text(yaml.safe_dump(play, allow_unicode=True), encoding="utf-8")
        r = subprocess.run(
            ["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(p), "-e", f"scan_dir={scan}"],
            capture_output=True, text=True, stdin=subprocess.DEVNULL,
            env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        if r.returncode != 0:
            print(r.stdout + r.stderr)
        check(f"{label}: ansible basarili", 0, r.returncode)
        sj = scan / "summary.json"
        check(f"{label}: summary.json var", True, sj.exists())
        data = json.loads(sj.read_text(encoding="utf-8")) if sj.exists() else {}
        modes = {
            "scan dizini": stat.S_IMODE(scan.stat().st_mode),
            "host dizini": stat.S_IMODE(scan.parent.stat().st_mode),
            "rapor": stat.S_IMODE((scan / "lynis-report.dat").stat().st_mode),
            "log": stat.S_IMODE((scan / "lynis.log").stat().st_mode),
            "summary": stat.S_IMODE(sj.stat().st_mode) if sj.exists() else None,
        }
        return data, modes, sj.read_text(encoding="utf-8") if sj.exists() else ""


base = (ROOT / "test/fixtures/lynis-report.dat").read_text(encoding="utf-8")

# 1) tam rapor
data, modes, raw = run(base, "tam rapor")
check("hardening_index", 62, data.get("hardening_index"))
check("tests_performed", 6, data.get("tests_performed"))
check("warnings", 2, data.get("warnings"))
check("suggestions", 3, data.get("suggestions"))
check("host alani envanter adi (hostname degil)", "localhost", data.get("host"))
check("date ISO-8601 UTC", True, isinstance(data.get("date"), str) and data["date"].endswith("Z") and "T" in data["date"])
check("alan kumesi tam", {"date", "hardening_index", "host", "suggestions", "tests_performed", "warnings"}, set(data))
check("izin: scan dizini 0700", 0o700, modes["scan dizini"])
check("izin: host dizini 0700", 0o700, modes["host dizini"])
check("izin: rapor 0600", 0o600, modes["rapor"])
check("izin: log 0600", 0o600, modes["log"])
check("izin: summary 0600", 0o600, modes["summary"])
check("rapordaki hostname ozete SIZMAZ", False, "ornek-host" in raw)

# 2) eksik alanlar -> null (0 degil)
partial = "\n".join(l for l in base.splitlines() if not l.startswith(("hardening_index=", "tests_executed=")))
data, _, _ = run(partial, "eksik alanli")
check("eksik hardening_index -> null", None, data.get("hardening_index"))
check("eksik tests_executed -> null", None, data.get("tests_performed"))
check("warnings yine sayilir", 2, data.get("warnings"))

# 3) uyari/oneri hic yok -> 0
none_ = "\n".join(l for l in base.splitlines() if not l.startswith(("warning[]=", "suggestion[]=")))
data, _, _ = run(none_, "uyarisiz")
check("uyari yok -> 0", 0, data.get("warnings"))
check("oneri yok -> 0", 0, data.get("suggestions"))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
