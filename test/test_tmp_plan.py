#!/usr/bin/env python3
"""hardening_files: `roles/hardening_files/files/tmp_plan.py` (/tmp ve /dev/shm için nodev,nosuid,noexec UYGULAMA PLANI; betik hiçbir şeyi değiştirmez).

Yanlış bağlamaya dokunmak sunucuyu bozar: yalnızca AYRI ve tmpfs olan dizin yönetilir; /tmp için tmp.mount etkin olmalı; /etc/fstab'daki mevcut /dev/shm satırı ÜSTÜNE YAZILMAZ.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "roles/hardening_files/files/tmp_plan.py"
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
OK = {"mounts": [TMP, SHM], "tmp_mount_active": "active", "shm_fstab": "", "want_tmp": True, "want_shm": True}


def p(o, k):
    return (o[k]["manage"], o[k]["persist"], o[k]["remount"])


rc, o = run(OK)
check("1) Ubuntu varsayilani: ikisi de yonetilir, kalici yazilir, remount gerekir", (0, (True, True, True), (True, True, True), []), (rc, p(o, "tmp"), p(o, "shm"), o.get("warnings")))
rc, o = run({**OK, "mounts": [TMP.replace("nosuid,nodev,", "nosuid,nodev,noexec,"), SHM.replace("nosuid,nodev,", "nosuid,nodev,noexec,")]})
check("2) zaten noexec: remount GEREKMEZ (idempotent), kalici yazim yine garanti", ((True, True, False), (True, True, False)), (p(o, "tmp"), p(o, "shm")))
rc, o = run({**OK, "mounts": [TMP.replace("nosuid,", ""), SHM]})
check("3) /tmp'de nosuid eksik: remount gerekir (noexec olsa bile)", True, run({**OK, "mounts": [TMP.replace("nosuid,nodev,", "nodev,noexec,"), SHM]})[1]["tmp"]["remount"])
rc, o = run({**OK, "want_tmp": False, "want_shm": False})
check("4) istenmediyse HICBIR sey yapilmaz", ((False, False, False), (False, False, False), []), (p(o, "tmp"), p(o, "shm"), o.get("warnings")))
rc, o = run({**OK, "want_tmp": False})
check("   yalniz shm istenir: tmp'ye dokunulmaz", ((False, False, False), (True, True, True)), (p(o, "tmp"), p(o, "shm")))
rc, o = run({**OK, "mounts": ["/tmp: / ext4 rw,relatime", SHM]})
check("5) /tmp ayri baglama degil: YONETILMEZ ve uyarilir (kok dosya sistemi remount edilmez)", ((False, False, False), True), (p(o, "tmp"), any("ayrı bir bağlama değil" in w for w in o["warnings"])))
rc, o = run({**OK, "mounts": ["/tmp: /tmp ext4 rw,relatime", SHM]})
check("6) /tmp ayri ama tmpfs degil (ext4 bolum): yonetilmez, uyari", ((False, False, False), True), (p(o, "tmp"), any("tmpfs değil" in w for w in o["warnings"])))
rc, o = run({**OK, "tmp_mount_active": "inactive"})
check("7) tmp.mount etkin degil (fstab ile baglanmis): /tmp yonetilmez, uyari; /dev/shm yine yonetilir", ((False, False, False), True, True), (p(o, "tmp"), any("tmp.mount ile yönetilmiyor" in w for w in o["warnings"]), o["shm"]["manage"]))
rc, o = run({**OK, "tmp_mount_active": ""})
check("   tmp.mount durumu okunamadi: /tmp yonetilmez", False, o["tmp"]["manage"])
rc, o = run({**OK, "shm_fstab": "tmpfs /dev/shm tmpfs defaults,nodev,nosuid,noexec 0 0"})
check("8) fstab'da /dev/shm satiri zaten tam: YENIDEN YAZILMAZ ama remount edilir", (True, False, True), p(o, "shm"))
rc, o = run({**OK, "shm_fstab": "tmpfs /dev/shm tmpfs defaults,size=2g 0 0"})
check("9) fstab'da kullanicinin size=2g satiri var: UZERINE YAZILMAZ, yonetilmez, uyari", ((False, False, False), True), (p(o, "shm"), any("üstüne yazılmadı" in w for w in o["warnings"])))
rc, o = run({**OK, "shm_fstab": "tmpfs /dev/shm tmpfs defaults,nodevx,nosuidx,noexecx 0 0"})
check("   benzer ama farkli jetonlar (nodevx...) sayilmaz: yazilmaz, uyari", (False, True), (o["shm"]["manage"], bool(o["warnings"])))
rc, o = run({**OK, "mounts": [TMP]})
check("10) /dev/shm bilgisi okunamadi: yonetilmez, uyari, cokme yok", (0, False, True), (rc, o["shm"]["manage"], any("okunamadı" in w for w in o["warnings"])))
rc, o = run({"mounts": [], "want_tmp": True, "want_shm": True})
check("11) hicbir bilgi yok: ikisi de yonetilmez (guvenli taraf)", (False, False), (o["tmp"]["manage"], o["shm"]["manage"]))
rc, o = run("bu json degil")
check("12) girdi okunamazsa hata alani, yonetilmez, cikis 0", (0, True, False, False), (rc, bool(o.get("error")), o["tmp"]["manage"], o["shm"]["manage"]))
sys.exit(1 if fails else 0)
