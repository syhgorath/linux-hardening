#!/usr/bin/env python3
"""hardening_files: `roles/hardening_files/files/tmp_report.py` (/tmp ve /dev/shm bağlama seçenekleri, CIS 1.1.2; SALT OKUNUR, hiçbir şeyi DEĞİŞTİRMEZ).

Girdi biçimi gerçek `findmnt -n -o TARGET,FSTYPE,OPTIONS --target <yol>` çıktısıdır (test VM'i ve mini lab konteyneri).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "roles/hardening_files/files/tmp_report.py"
fails = 0


def check(name, want, got):
    global fails
    if want == got:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}: beklenen={want!r} gercek={got!r}")


def run(cfg):
    arg = cfg if isinstance(cfg, str) else json.dumps(cfg)
    r = subprocess.run([sys.executable, str(SCRIPT), arg], capture_output=True, text=True)
    try:
        return r.returncode, json.loads(r.stdout)
    except ValueError:
        return r.returncode, {"_ham": r.stdout, "_err": r.stderr}


TMP = "/tmp: /tmp tmpfs rw,nosuid,nodev,size=1740124k,nr_inodes=1048576,inode64,usrquota"
SHM = "/dev/shm: /dev/shm tmpfs rw,nosuid,nodev,inode64,usrquota"
BASE = {"mounts": [TMP, SHM], "remote_tmp": "~/.ansible/tmp"}


def text(o):
    return " ".join(o.get("warnings", []) + o.get("notes", []))


rc, o = run(BASE)
check("1) Ubuntu varsayilani (nosuid,nodev var, noexec yok): UYARI YOK (ok), iki not", (0, "ok", [], 3), (rc, o.get("status"), o.get("warnings"), len(o.get("notes", []))))
check("   notlar noexec'i ve rapor degistirmez bilgisini soyler", (True, True), ("/tmp bağlamasında noexec yok" in text(o), "DEĞİŞTİRMEZ" in text(o)))
rc, o = run({**BASE, "mounts": [TMP.replace("nosuid,", "nosuid,noexec,"), SHM.replace("nosuid,", "nosuid,noexec,")]})
check("2) iki dizinde de noexec var: ok, not YOK, ozet var", ("ok", [], True), (o.get("status"), o.get("notes"), "noexec" in o.get("summary", "")))
rc, o = run({**BASE, "mounts": [TMP, "/dev/shm: /dev/shm tmpfs rw,nosuid,nodev,noexec,relatime,size=65536k,inode64"]})
check("3) yalniz /dev/shm noexec (mini lab konteyneri): yalniz /tmp notu", 1, len([n for n in o.get("notes", []) if "noexec yok" in n]))
rc, o = run({**BASE, "mounts": ["/tmp: / ext4 rw,relatime", SHM]})
check("4) /tmp ayri baglama degil: UYARI", ("warn", True), (o.get("status"), "ayrı bir bağlama değil" in text(o) and "/tmp" in text(o)))
rc, o = run({**BASE, "mounts": ["/tmp:", SHM]})
check("   findmnt bos dondu (satir '/tmp:'): ayri degil sayilir, cokme yok", ("warn", 0), (o.get("status"), rc))
rc, o = run({**BASE, "mounts": [TMP.replace("nosuid,nodev,", ""), SHM]})
check("5) /tmp'de nodev ve nosuid yok: UYARI ikisini de soyler", ("warn", True), (o.get("status"), "nodev/nosuid" in text(o)))
rc, o = run({**BASE, "mounts": [TMP.replace("nosuid,", ""), SHM]})
check("   yalniz nosuid yok: UYARI nosuid'i soyler, nodev'i degil", (True, False), ("nosuid yok" in text(o) or "nosuid" in text(o), "nodev/" in text(o)))
rc, o = run({**BASE, "mounts": [TMP, SHM.replace("nodev,", "")]})
check("   /dev/shm'de nodev yok: UYARI", ("warn", True), (o.get("status"), "/dev/shm" in text(o) and "nodev" in text(o)))

for rt, expect in (("/tmp/.ansible", True), ("/tmp", True), ("/dev/shm/ans", True), ("~/.ansible/tmp", False), ("/var/tmp/x", False), ("", False), ("/tmpfoo", True)):
    rc, o = run({**BASE, "remote_tmp": rt})
    check(f"6) remote_tmp={rt!r}: uyari={expect}", expect, "uzak geçici dizini" in text(o))
rc, o = run({"mounts": [TMP, SHM]})
check("   remote_tmp hic verilmemis: cokme yok, uyari yok", (0, "ok"), (rc, o.get("status")))

rc, o = run({"mounts": []})
check("7) bilgi yok: unknown + hata, cikis 0", (0, "unknown", True), (rc, o.get("status"), bool(o.get("error"))))
rc, o = run({"mounts": ["bozuk satir", "", "/home: / ext4 rw"]})
check("   bozuk/ilgisiz satirlar: unknown", "unknown", o.get("status"))
rc, o = run("bu json degil")
check("8) girdi okunamazsa unknown + hata, cikis 0", (0, "unknown", True), (rc, o.get("status"), bool(o.get("error"))))
sys.exit(1 if fails else 0)
