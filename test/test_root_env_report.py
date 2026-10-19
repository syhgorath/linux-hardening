#!/usr/bin/env python3
"""hardening_auth: `roles/hardening_auth/files/root_env_report.py` (CIS 5.4.2.5 root PATH bütünlüğü, 5.4.2.6 root umask; SALT OKUNUR, hiçbir şeyi DEĞİŞTİRMEZ).

Karar mantığı tek betikte olduğu için gerçek bir sunucu gerekmeden denenir. Girdi biçimi test VM'inde (Ubuntu 26.04) alınan gerçek çıktıdır: `stat -L -c '%a %U %n'`, login.defs UMASK 027, pam_umask etkin.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "roles/hardening_auth/files/root_env_report.py"
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


PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin"
DIRS = ["755 root /usr/local/sbin", "755 root /usr/local/bin", "755 root /usr/sbin", "755 root /usr/bin", "755 root /sbin", "755 root /bin", "755 root /snap/bin"]
OK = {"path": PATH, "dirs": DIRS, "login_defs_umask": "027", "pam_umask": True, "file_umasks": []}


def msgs(o):
    return " ".join(o.get("messages", []))


rc, o = run(OK)
check("1) gerçek VM çıktısı: ok", ("ok", 0, []), (o.get("status"), rc, o.get("messages")))
check("   özet: 7 dizin, umask 027", True, "7 dizin" in o.get("summary", "") and "027" in o.get("summary", ""))

rc, o = run({**OK, "path": PATH + ":."})
check("2) PATH'te '.' : warn", ("warn", True), (o.get("status"), "`.`" in msgs(o)))
rc, o = run({**OK, "path": "::" + PATH})
check("3) boş girdi (baştaki ::) : warn", ("warn", True), (o.get("status"), "boş girdi" in msgs(o)))
rc, o = run({**OK, "path": PATH + ":"})
check("   sondaki ':' da boş girdi", True, "boş girdi" in msgs(o))
rc, o = run({**OK, "path": PATH + ":/yok/dizin", "dirs": DIRS + ["MISSING - /yok/dizin"]})
check("4) olmayan dizin: warn ve yol söylenir", ("warn", True), (o.get("status"), "/yok/dizin" in msgs(o)))
rc, o = run({**OK, "dirs": DIRS[:-1] + ["775 root /snap/bin"]})
check("5) grup yazılabilir (775): warn", ("warn", True), (o.get("status"), "YAZILABİLİR" in msgs(o) and "/snap/bin" in msgs(o)))
rc, o = run({**OK, "dirs": DIRS[:-1] + ["757 root /snap/bin"]})
check("   diğer yazılabilir (757): warn", "warn", o.get("status"))
rc, o = run({**OK, "dirs": DIRS[:-1] + ["755 alice /snap/bin"]})
check("6) root'a ait değil: warn", ("warn", True), (o.get("status"), "root'a ait değil" in msgs(o) and "alice" in msgs(o)))
rc, o = run({**OK, "dirs": DIRS[:-1] + ["1777 root /snap/bin"]})
check("   yapışkan bitli 1777 de yazılabilir sayılır", "warn", o.get("status"))
rc, o = run({**OK, "dirs": DIRS + DIRS})
check("   aynı dizin iki kez listelense tek kez raporlanır/ok", "ok", o.get("status"))
rc, o = run({**OK, "dirs": DIRS[:-1] + ["775 root /snap/bin", "775 root /snap/bin"]})
check("   aynı sorun iki kez yazılmaz", 1, msgs(o).count("/snap/bin"))
rc, o = run({**OK, "path": ""})
check("7) PATH boş: warn", "warn", o.get("status"))

# umask
rc, o = run({**OK, "login_defs_umask": "022"})
check("8) login.defs UMASK 022: warn", ("warn", True), (o.get("status"), "022" in msgs(o) and "login.defs" in msgs(o)))
rc, o = run({**OK, "login_defs_umask": "077"})
check("   077 daha kısıtlayıcı: ok", "ok", o.get("status"))
rc, o = run({**OK, "login_defs_umask": "0027"})
check("   0027 (dört haneli): ok", "ok", o.get("status"))
rc, o = run({**OK, "login_defs_umask": "026"})
check("   026 (diğer okuma+yazma kapalı ama grup yazma açık değil, ama 027'den gevşek: 026&027=026): warn", "warn", o.get("status"))
rc, o = run({**OK, "login_defs_umask": "007"})
check("   007 (grup yazma/okuma AÇIK, diğer kapalı): 027'den gevşek -> warn", "warn", o.get("status"))
rc, o = run({**OK, "login_defs_umask": "017"})
check("   017 (grup yazma açık): warn", "warn", o.get("status"))
rc, o = run({**OK, "login_defs_umask": "037"})
check("   037 (027'den kısıtlayıcı): ok", "ok", o.get("status"))
rc, o = run({**OK, "file_umasks": ["/root/.bashrc:umask 022"]})
check("9) /root/.bashrc umask 022: warn ve dosya adı söylenir", ("warn", True), (o.get("status"), "/root/.bashrc" in msgs(o)))
rc, o = run({**OK, "file_umasks": ["/etc/profile:umask 027", "/root/.profile:umask 077"]})
check("   dosyalarda 027 ve 077: ok", "ok", o.get("status"))
rc, o = run({**OK, "file_umasks": ["/root/.bashrc:umask u=rwx,g=rx,o="]})
check("10) sembolik umask: ayrıştırılmaz, 'Elle bakın' denir (warn)", ("warn", True), (o.get("status"), "Elle bakın" in msgs(o)))
rc, o = run({**OK, "login_defs_umask": "", "file_umasks": []})
check("11) hiçbir yerde umask yok: warn", ("warn", True), (o.get("status"), "Hiçbir yerde umask" in msgs(o)))
rc, o = run({**OK, "pam_umask": False})
check("12) login.defs 027 ama pam_umask etkin değil: warn", ("warn", True), (o.get("status"), "pam_umask" in msgs(o)))
rc, o = run({**OK, "pam_umask": False, "file_umasks": ["/root/.profile:umask 027"]})
check("    ama root'un kendi dosyasında 027 varsa pam_umask şart değil: ok", "ok", o.get("status"))
rc, o = run({**OK, "path": PATH + ":.", "login_defs_umask": "022"})
check("13) hem PATH hem umask sorunu: ikisi de raporlanır", (True, True), ("`.`" in msgs(o), "022" in msgs(o)))
check("    path_issues / umask_issues ayrı alanlarda", (1, 1), (len(o.get("path_issues", [])), len(o.get("umask_issues", []))))

# bozuk girdi
rc, o = run("bu json degil")
check("14) girdi okunamazsa unknown + hata, çıkış 0", (0, "unknown", True), (rc, o.get("status"), bool(o.get("error"))))
rc, o = run({"dirs": []})
check("    path yoksa unknown", "unknown", o.get("status"))
rc, o = run({**OK, "dirs": ["bozuk satir", "", "755 root"]})
check("    bozuk dizin satırları atlanır, çökme yok", (0, "ok"), (rc, o.get("status")))

sys.exit(1 if fails else 0)
