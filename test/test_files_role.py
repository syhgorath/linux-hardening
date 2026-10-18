#!/usr/bin/env python3
"""hardening_files: dosya izinleri yalnızca SIKILAŞIR, mevcut olmayan dosya oluşturulmaz, sembolik bağ izlenmez, `--check` değiştirmez, ikinci koşu changed=0.

Rol gerçek `ansible-playbook` ile geçici bir ağaçta çalışır (hardening_files_root öneki, sahip/grup = mevcut kullanıcı). Varsayılan hedef listesine ayrıca statik bakılır:
modlar sembolik ve yalnızca `-` (izin kaldırır), sahip root, yollar mutlak.
"""
import grp
import json
import os
import pwd
import re
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


# 1) varsayılan hedef listesi (statik)
d = yaml.safe_load((ROOT / "roles/hardening_files/defaults/main.yml").read_text(encoding="utf-8"))
targets = d["hardening_files_targets"]
paths = [t["path"] for t in targets]
check("varsayilan: rol acik", True, d["hardening_files_enabled"])
check("varsayilan: yol oneki bos, dinamik sahip/grup root", ("", "root", "root"), (d["hardening_files_root"], d["hardening_files_owner"], d["hardening_files_group"]))
check("yollar mutlak ve tekrarsiz", True, all(p.startswith("/") for p in paths) and len(paths) == len(set(paths)))
check("modlar sembolik ve yalnizca izin KALDIRIR (rakam yok, '+'/'=' yok)", [], [t["path"] for t in targets if re.search(r"[0-9+=]", t["mode"]) or "-" not in t["mode"]])
check("sahip hep root", [], [t["path"] for t in targets if t["owner"] != "root"])
for must in ("/etc/passwd", "/etc/shadow", "/etc/gshadow", "/etc/group", "/etc/ssh/sshd_config", "/etc/ssh/sshd_config.d", "/etc/crontab", "/etc/cron.d", "/boot/grub/grub.cfg"):
    check(f"hedef var: {must}", True, must in paths)
check("cron.allow/at.allow yalnizca VARSA sikilastirilir; rol dosya OLUSTURMAZ", True,
      "state: touch" not in (ROOT / "roles/hardening_files/tasks/main.yml").read_text(encoding="utf-8")
      and "touch" not in (ROOT / "roles/hardening_files/tasks/main.yml").read_text(encoding="utf-8").replace("# ", ""))

# 2) işlevsel: geçici ağaç
me = pwd.getpwuid(os.getuid()).pw_name
mygrp = grp.getgrgid(os.getgid()).gr_name
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "root"
    for sub in ("etc/ssh/sshd_config.d", "etc/cron.d", "etc/security"):
        (root / sub).mkdir(parents=True)
    def mk(rel, mode, text="x\n"):
        p = root / rel
        p.write_text(text)
        p.chmod(mode)
        return p
    mk("etc/passwd", 0o666)
    mk("etc/group", 0o600)                       # zaten daha kisitli: GEVSEMEMELI
    mk("etc/shadow", 0o644)
    mk("etc/ssh/sshd_config", 0o644)
    mk("etc/ssh/sshd_config.d/00-a.conf", 0o644)
    mk("etc/ssh/sshd_config.d/50-b.conf", 0o600)
    mk("etc/ssh/sshd_config.d/notes.txt", 0o644)  # .conf degil: dokunulmamali
    mk("etc/ssh/ssh_host_rsa_key", 0o640)
    mk("etc/ssh/ssh_host_rsa_key.pub", 0o666)
    mk("etc/ssh/ssh_host_rsa_key.bak", 0o666)     # desene uymaz: dokunulmamali
    (root / "etc/cron.d").chmod(0o755)
    real = mk("etc/real_motd_target", 0o666)
    (root / "etc/motd").symlink_to(real)         # sembolik bag: izlenmemeli, hedef degismemeli
    # /etc/shadow- , /etc/crontab, /etc/cron.allow ... YOK: olusturulmamali

    def tg(path, mode, **kw):
        return {"path": path, "mode": mode, "owner": me, "group": mygrp, **kw}
    vars_ = {
        "hardening_files_root": str(root), "hardening_files_owner": me, "hardening_files_group": mygrp,
        "hardening_files_targets": [
            tg("/etc/passwd", "u-x,go-wx"), tg("/etc/group", "u-x,go-wx"),
            tg("/etc/shadow", "u-x,g-wx,o-rwx", group="nogroup", group_ok=[mygrp]),
            tg("/etc/shadow-", "u-x,g-wx,o-rwx"), tg("/etc/crontab", "og-rwx"), tg("/etc/cron.allow", "u-x,g-wx,o-rwx"),
            tg("/etc/ssh/sshd_config", "u-x,og-rwx"), tg("/etc/cron.d", "og-rwx"), tg("/etc/motd", "u-x,go-wx"),
        ],
    }
    pb = Path(tmp) / "p.yml"
    pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "roles": ["hardening_files"]}]), encoding="utf-8")
    vf = Path(tmp) / "v.json"
    vf.write_text(json.dumps(vars_))
    env = {**os.environ, "ANSIBLE_ROLES_PATH": str(ROOT / "roles"), "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")}

    def run(*extra):
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb), "-e", f"@{vf}", *extra],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env)
        m = re.search(r"changed=(\d+)\s+unreachable=(\d+)\s+failed=(\d+)", r.stdout)
        return r.returncode, (tuple(int(x) for x in m.groups()) if m else None), r.stdout + r.stderr

    def mode(rel):
        return stat.S_IMODE((root / rel).stat().st_mode)

    rc, (chg, _, fail), out = run("--check")
    check("--check: hata yok", (0, 0), (rc, fail))
    check("--check: hicbir dosya degismedi", (0o666, 0o644), (mode("etc/passwd"), mode("etc/shadow")))
    rc, res, out = run()
    check("gercek kosu: hata yok", 0, rc)
    check("passwd 0666 -> 0644 (grup/diger yazma kalkar)", 0o644, mode("etc/passwd"))
    check("group 0600 GEVSEMEZ (zaten daha kisitli)", 0o600, mode("etc/group"))
    check("shadow 0644 -> 0640 (diger okuma kalkar, grup okuma kalir)", 0o640, mode("etc/shadow"))
    check("sshd_config 0644 -> 0600", 0o600, mode("etc/ssh/sshd_config"))
    check("sshd drop-in .conf 0644 -> 0600", 0o600, mode("etc/ssh/sshd_config.d/00-a.conf"))
    check("sshd drop-in 0600 ayni", 0o600, mode("etc/ssh/sshd_config.d/50-b.conf"))
    check(".conf olmayan dosyaya dokunulmaz (notes.txt 0644)", 0o644, mode("etc/ssh/sshd_config.d/notes.txt"))
    check("ozel ana bilgisayar anahtari 0640 -> 0600", 0o600, mode("etc/ssh/ssh_host_rsa_key"))
    check("acik anahtar 0666 -> 0644", 0o644, mode("etc/ssh/ssh_host_rsa_key.pub"))
    check("desene uymayan dosyaya dokunulmaz (.bak 0666)", 0o666, mode("etc/ssh/ssh_host_rsa_key.bak"))
    check("cron.d dizini 0755 -> 0700", 0o700, mode("etc/cron.d"))
    check("sembolik bag izlenmez: hedef 0666 kalir", 0o666, mode("etc/real_motd_target"))
    check("olmayan dosyalar OLUSTURULMAZ (shadow-, crontab, cron.allow)", [], [n for n in ("etc/shadow-", "etc/crontab", "etc/cron.allow") if (root / n).exists()])
    rc, res, out = run()
    check("ikinci kosu: changed=0 (idempotent)", (0, 0, 0), res)
    rc, res, out = run("-e", "hardening_files_enabled=false")
    check("hardening_files_enabled=false: rol bir sey yapmaz", 0, rc)
    (root / "etc/passwd").chmod(0o666)
    rc, res, out = run("-e", "hardening_files_enabled=false")
    check("kapaliyken izin duzeltilmez", 0o666, mode("etc/passwd"))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
