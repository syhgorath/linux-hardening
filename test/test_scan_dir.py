#!/usr/bin/env python3
"""audit.yml'deki tarama dizini görevleri (YAML'dan çıkarılıp çalıştırılır): varsayılan KULLANICI klasörüdür, paket klasörü değil (#37).

Doğrulananlar: varsayılan yol (HOME, XDG_DATA_HOME), açık hardening_scan_dir, HOME/XDG yokken durma, varsayılan konumda
uygulama dizini ve scans/ için 0700, verilen özel yolun izinlerine dokunulmaması, paket (repo) klasörüne hiçbir şey yazılmaması.
"""
import os
import re
import stat
import subprocess
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


def play(d, create):
    pb = yaml.safe_load((ROOT / "playbooks/audit.yml").read_text(encoding="utf-8"))
    names = ("Scan directory must be resolvable", "Fix scan directory") + (("Create scan directories",) if create else ())
    tasks = [t for t in pb[0]["tasks"] if str(t.get("name", "")).startswith(names)]
    tasks.append({"name": "Report", "ansible.builtin.debug": {"msg": "SCAN_DIR={{ scan_dir | default('YOK') }}"}})
    p = Path(d) / "p.yml"
    p.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "tasks": tasks}],
                                allow_unicode=True), encoding="utf-8")
    return p, len(tasks) - 1


def run(d, env_extra, extra_args=(), create=True, unset=()):
    p, _ = play(d, create)
    env = {k: v for k, v in os.environ.items() if k not in ("HOME", "XDG_DATA_HOME") and k not in unset}
    env.update({"ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    env.update(env_extra)
    r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(p), *extra_args],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env)
    m = re.search(r'SCAN_DIR=([^"\s]+)', r.stdout)
    return r, (m.group(1) if m else None)


def mode(path):
    p = Path(path)
    return stat.S_IMODE(p.stat().st_mode) if p.exists() else None


repo_before = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "scans").rglob("*")) if (ROOT / "scans").exists() else []

# 1) varsayılan: HOME altında
with tempfile.TemporaryDirectory() as d:
    home = Path(d) / "home"
    home.mkdir()
    r, sd = run(d, {"HOME": str(home), "PATH": os.environ["PATH"]})
    check("varsayilan: ansible basarili", 0, r.returncode)
    want = re.compile(re.escape(str(home / ".local/share/linux-hardening/scans")) + r"/localhost/\d{8}-\d{6}$")
    check("varsayilan yol HOME/.local/share/linux-hardening/scans/<host>/<tarih>", True, bool(sd and want.match(sd)))
    check("varsayilan: tarih dizini olustu", True, bool(sd and Path(sd).is_dir()))
    app = home / ".local/share/linux-hardening"
    check("izin: uygulama dizini 0700", 0o700, mode(app))
    check("izin: scans/ 0700", 0o700, mode(app / "scans"))
    check("izin: host dizini 0700", 0o700, mode(app / "scans/localhost"))
    check("izin: tarih dizini 0700", 0o700, mode(Path(sd)))
    check("paket klasorune (repo) yazilmadi", repo_before,
          sorted(str(p.relative_to(ROOT)) for p in (ROOT / "scans").rglob("*")) if (ROOT / "scans").exists() else [])

# 2) XDG_DATA_HOME HOME'a tercih edilir
with tempfile.TemporaryDirectory() as d:
    xdg, home = Path(d) / "xdg", Path(d) / "home"
    xdg.mkdir()
    home.mkdir()
    r, sd = run(d, {"HOME": str(home), "XDG_DATA_HOME": str(xdg)})
    want = re.compile(re.escape(str(xdg / "linux-hardening/scans")) + r"/localhost/\d{8}-\d{6}$")
    check("XDG_DATA_HOME varsa o kullanilir", True, bool(sd and want.match(sd)))
    check("XDG: HOME altina yazilmadi", False, (home / ".local").exists())

# 3) açık hardening_scan_dir: verilen yolun kendi izinlerine dokunulmaz
with tempfile.TemporaryDirectory() as d:
    custom = Path(d) / "ozel"
    custom.mkdir()
    custom.chmod(0o755)
    r, sd = run(d, {"HOME": str(Path(d) / "home")}, extra_args=("-e", f"hardening_scan_dir={custom}"))
    want = re.compile(re.escape(str(custom)) + r"/localhost/\d{8}-\d{6}$")
    check("acik hardening_scan_dir kullanilir", True, bool(sd and want.match(sd)))
    check("ozel yolun kendi izni degismedi (0755)", 0o755, mode(custom))
    check("ozel yolda host dizini 0700", 0o700, mode(custom / "localhost"))
    check("ozel yolda tarih dizini 0700", 0o700, mode(Path(sd)))
    check("ozel yol icin HOME altina yazilmadi", False, (Path(d) / "home/.local").exists())

# 4) boş hardening_scan_dir varsayılan gibi davranır
with tempfile.TemporaryDirectory() as d:
    home = Path(d) / "home"
    home.mkdir()
    r, sd = run(d, {"HOME": str(home)}, extra_args=("-e", "hardening_scan_dir="), create=False)
    check("bos hardening_scan_dir -> varsayilan", True, bool(sd and sd.startswith(str(home / ".local/share/linux-hardening/scans"))))

# 5) HOME, XDG ve hardening_scan_dir yok: kökte /.local/... yazmak yerine DUR
with tempfile.TemporaryDirectory() as d:
    r, sd = run(d, {}, create=False)
    check("HOME/XDG/hardening_scan_dir yok: durur", True, r.returncode != 0)
    check("  mesaj nedeni soyler", True, "Tarama dizini belirlenemedi" in r.stdout + r.stderr)
    check("  dizin belirlenmedi", None, sd)

raise SystemExit(1 if fails else 0)
