#!/usr/bin/env python3
"""hardening_auditd: auditd'den ÖNCE başlamış süreçleri bulan salt okunur görev (docs/design/auditd-kapsam.md P1, seçenek 1c).

Görevin kabuk betiği YAML'dan çıkarılıp sahte `ps` ve `systemctl` ile çalıştırılır (gerçek bir sunucu gerekmez). Denetlenenler:
auditd'den eski süreçler listelenir; daha genç olanlar, çekirdek iş parçacıkları ve eşik içindekiler listelenmez; auditd çalışmıyorsa çıktı boştur.
Ayrıca görev salt okunurdur ve `--check`'te de çalışır; uyarı görevi hiçbir şeyi başarısız kılmaz.
"""
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
tasks = yaml.safe_load((ROOT / "roles/hardening_auditd/tasks/main.yml").read_text(encoding="utf-8"))
fails = 0


def check(name, want, got):
    global fails
    if want == got:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}: beklenen={want!r} gercek={got!r}")


finder = [t for t in tasks if "ansible.builtin.shell" in t and "etimes" in str(t["ansible.builtin.shell"])]
check("süreçleri listeleyen shell görevi var", 1, len(finder))
if not finder:
    sys.exit(1)
task = finder[0]
script = task["ansible.builtin.shell"]["cmd"]
check("salt okunur: changed_when false", False, task.get("changed_when"))
check("`--check`'te de çalışır: check_mode false", False, task.get("check_mode"))
check("pipefail kullanılıyor", True, "set -o pipefail" in script)
warn = [t for t in tasks if "ansible.builtin.debug" in t and "unaudited" in str(t.get("when", ""))]
check("uyarı görevi (debug) var, başarısız kılmıyor (fail değil)", 1, len(warn))
check("hiçbir görev bu uyarı yüzünden fail etmiyor", 0, len([t for t in tasks if "ansible.builtin.fail" in t]))
if warn:
    msg = str(warn[0]["ansible.builtin.debug"]["msg"])
    check("mesaj yeniden başlatmanın her şeyi çözdüğünü İDDİA ETMİYOR (doğrulanmadı notu var)", True, "doğrulanmadı" in msg or "doğrulanmad" in msg)

PS_TABLE = """\
5000 0 1 systemd
4000 1 700 sshd
4000 1 701 cron
4000 2 40 kworker/0:1
4000 0 2 kthreadd
  50 1 800 chronyd
 100 1 900 auditd
 105 1 910 sinirda
 106 1 911 hemen-ustu
4000 1 702 tmux: server
"""


def run(mainpid, auditd_etimes):
    with tempfile.TemporaryDirectory() as d:
        b = Path(d)
        (b / "systemctl").write_text(f'#!/bin/sh\nif [ "$1" = show ]; then echo "{mainpid}"; fi\n', encoding="utf-8")
        (b / "ps").write_text(
            "#!/bin/sh\n"
            'case "$*" in\n'
            f'  *-p*) printf "%s\\n" "   {auditd_etimes}";;\n'
            f'  *) cat <<"EOF"\n{PS_TABLE}EOF\n;;\n'
            "esac\n",
            encoding="utf-8")
        for n in ("systemctl", "ps"):
            (b / n).chmod((b / n).stat().st_mode | stat.S_IXUSR)
        r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env={**os.environ, "PATH": f"{d}:{os.environ['PATH']}"})
        return r.returncode, [l for l in r.stdout.splitlines() if l.strip()]


rc, out = run(1234, 100)
check("çıkış 0", 0, rc)
check("auditd'den eski süreçler listelenir (sıralı, tekrarsız)", ["cron", "hemen-ustu", "sshd", "systemd", "tmux: server"], out)
check("daha genç süreç (chronyd) listelenmez", False, "chronyd" in out)
check("eşik içindeki (<= auditd+5 sn) listelenmez", False, "sinirda" in out)
check("çekirdek iş parçacıkları listelenmez", False, "kworker/0:1" in out or "kthreadd" in out)
check("auditd'in kendisi listelenmez", False, "auditd" in out)
rc, out = run(0, 100)
check("auditd çalışmıyorsa (MainPID=0) çıktı boş, çıkış 0", (0, []), (rc, out))
rc, out = run("", 100)
check("MainPID alınamazsa çıktı boş, çıkış 0", (0, []), (rc, out))
rc, out = run(1234, "")
check("auditd süresi okunamazsa çıktı boş, çıkış 0", (0, []), (rc, out))
sys.exit(1 if fails else 0)
