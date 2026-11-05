#!/usr/bin/env python3
"""GRUB parolasi (hardening_grub_password_hash, varsayilan KAPALI): doğrulayici (grub_check.py) ve rolun gercek Ansible gorevleri, gecici kok + sahte `update-grub` ile.

Fixture `test/fixtures/grub-ubuntu2604-parolali.cfg` GERCEK `grub-mkconfig` (GRUB 2.14, Ubuntu 26.04) ciktisidir. Gercek LAB koşusunda gorulen tuzaklar burada sinanir:
  1) CLASS yamasi recovery girdilerini de kilitsiz yapar (parolasiz kok kabugu) -> recovery kapatilmali;
  2) /etc/grub.d icinde kalan yedek dosya menuyu CIFT uretir -> yedek disarida tutulur;
  3) os-prober'in buldugu baska isletim sistemi girdileri kilitli KALIR (hata degil);
  4) dogrulama basarisizsa degisiklikler GERI ALINIR.
Gercek GRUB ile onyukleme DENENMEDI (yalnizca grub-mkconfig ciktisi dogrulandi)."""
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "roles/hardening_files/files/grub_check.py"
FIXTURE = (ROOT / "test/fixtures/grub-ubuntu2604-parolali.cfg").read_text(encoding="utf-8")
HASH = "grub.pbkdf2.sha512.10000.AAAA.BBBB"
fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {str(detail)[-600:]}")


def verify(text, unrestricted=True, user="grubadmin", pw_hash=HASH):
    with tempfile.TemporaryDirectory() as d:
        cfg = Path(d) / "grub.cfg"
        cfg.write_text(text, encoding="utf-8")
        r = subprocess.run(["python3", str(CHECK), json.dumps({"cfg": str(cfg), "user": user, "hash": pw_hash, "unrestricted": unrestricted})], capture_output=True, text=True)
    return json.loads(r.stdout)


# ---- dogrulayici (gercek cikti uzerinde) ----
o = verify(FIXTURE)
check("gercek grub-mkconfig ciktisi KABUL edilir", o["ok"] and o["entries"] == 1, o)
check("   parola/kullanici yanlissa reddedilir", not verify(FIXTURE, user="baska")["ok"] and not verify(FIXTURE, pw_hash="grub.pbkdf2.sha512.1.AA.BB")["ok"])
no_unres = re.sub(r" --unrestricted", "", FIXTURE)
o = verify(no_unres)
check("ana girdi kilitliyse (normal acilis parola ister) REDDEDILIR", not o["ok"] and "unrestricted" in " ".join(o["errors"]), o)
check("   ama unrestricted=false iken ayni cikti KABUL edilir (yalniz parola)", verify(no_unres, unrestricted=False)["ok"])
rec = FIXTURE.replace("\n}\n", "\n}\nmenuentry 'GNU/Linux, with Linux 6.8.0-1-generic (recovery mode)' --class gnu-linux --unrestricted $menuentry_id_option 'gnulinux-6.8.0-1-generic-recovery-x' {\n  true\n}\n", 1)
o = verify(rec)
check("KILITSIZ recovery girdisi REDDEDILIR (parolasiz kok kabugu)", not o["ok"] and "recovery" in " ".join(o["errors"]).lower(), o)
locked_rec = rec.replace("--unrestricted $menuentry_id_option 'gnulinux-6.8.0-1-generic-recovery-x'", "$menuentry_id_option 'gnulinux-6.8.0-1-generic-recovery-x'")
check("   kilitli recovery girdisi sorun degil", verify(locked_rec)["ok"])
osp = FIXTURE + "menuentry 'Baska OS (on /dev/sdb1)' --class gnu-linux --class gnu --class os $menuentry_id_option 'osprober-gnulinux-simple-x' {\n  true\n}\n"
check("os-prober'in buldugu BASKA isletim sistemi girdisi kilitli kalir, hata DEGIL", verify(osp)["ok"])
dup = FIXTURE + [ln for ln in FIXTURE.split("\n") if ln.startswith("menuentry ")][0] + " {\n  true\n}\n"
o = verify(dup)
check("ana girdi YINELENIRSE (yedek betik /etc/grub.d'de kalmis) REDDEDILIR", not o["ok"] and "yinelenmi" in " ".join(o["errors"]), o)
check("parola satiri yoksa REDDEDILIR", not verify(re.sub(r"password_pbkdf2.*\n", "", FIXTURE))["ok"] and not verify(re.sub(r'set superusers=.*\n', "", FIXTURE))["ok"])
bad_in = json.loads(subprocess.run(["python3", str(CHECK), "{bozuk"], capture_output=True, text=True).stdout)
check("okunamayan girdi: ok=false (cokmez)", bad_in["ok"] is False and bad_in["entries"] == 0, bad_in)

# ---- rol gorevleri (gecici kok + sahte update-grub) ----
CLASS_LINE = 'CLASS="--class gnu-linux --class gnu --class os"'


def make_root(d, with_grub=True, class_line=CLASS_LINE):
    r = Path(d) / "kok"
    for sub in ("etc/default", "etc/grub.d", "boot/grub", "bin"):
        (r / sub).mkdir(parents=True, exist_ok=True)
    if with_grub:
        (r / "etc/default/grub").write_text('GRUB_DEFAULT=0\nGRUB_TIMEOUT=5\n#GRUB_DISABLE_RECOVERY="true"\n', encoding="utf-8")
        (r / "etc/grub.d/10_linux").write_text("#!/bin/sh\n" + class_line + "\nexit 0\n", encoding="utf-8")
        os.chmod(r / "etc/grub.d/10_linux", 0o755)
    else:
        shutil.rmtree(r / "etc/default"); (r / "etc/default").mkdir()
    fake = r / "bin/update-grub"
    # Sahte update-grub: GERCEK ciktidan turetir; 10_linux yamali degilse --unrestricted yok, recovery acik degilse recovery girdisi var, 40 betigi yoksa parola yok.
    fake.write_text('#!/usr/bin/env python3\nimport re, sys, os\nR = %r\nfx = open(%r, encoding="utf-8").read()\n'
                    'lin = open(R + "/etc/grub.d/10_linux").read()\ndef_ = open(R + "/etc/default/grub").read()\n'
                    'if "--unrestricted" not in lin: fx = fx.replace(" --unrestricted", "")\n'
                    'if not re.search(r"^GRUB_DISABLE_RECOVERY=.true.", def_, re.M):\n'
                    '    fx = fx.replace("\\n}\\n", "\\n}\\nmenuentry \'x (recovery mode)\' --class gnu-linux %%s $menuentry_id_option \'gnulinux-r\' {\\n  true\\n}\\n" %% ("--unrestricted" if "--unrestricted" in lin else ""), 1)\n'
                    'if os.path.exists(R + "/etc/grub.d/40_hardening_password"):\n'
                    '    sc = open(R + "/etc/grub.d/40_hardening_password").read()\n'
                    '    fx = re.sub(r"set superusers=.*\\n|password_pbkdf2.*\\n", "", fx)\n'
                    '    fx += "\\n".join(l for l in sc.split("\\n") if l.startswith("set superusers") or l.startswith("password_pbkdf2")) + "\\n"\n'
                    'else:\n    fx = re.sub(r"set superusers=.*\\n|password_pbkdf2.*\\n", "", fx)\n'
                    'if os.path.exists(R + "/KIR"): fx = re.sub(r"password_pbkdf2.*\\n", "", fx)\n'
                    'if os.path.exists(R + "/etc/grub.d/10_linux.orig"): fx += open(R + "/etc/grub.d/10_linux.orig").read()\n'
                    'open(R + "/boot/grub/grub.cfg", "w").write(fx)\n' % (str(r), str(ROOT / "test/fixtures/grub-ubuntu2604-parolali.cfg")), encoding="utf-8")
    os.chmod(fake, 0o755)
    return r


def play(r, extra, platform=None):
    v = {"hardening_files_root": str(r), "hardening_files_enabled": False, "hardening_tmp_noexec": False, "hardening_shm_noexec": False,
         "hardening_grub_update_cmd": str(r / "bin/update-grub"), "hardening_grub_backup_dir": "/yedek",
         "hardening_files_owner": str(os.getuid()), "hardening_files_group": str(os.getgid()), **extra}
    if platform:
        v["hardening_platform"] = platform
    pb = r.parent / "p.yml"
    pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": v, "roles": ["hardening_files"]}]), encoding="utf-8")
    p = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg"), "ANSIBLE_ROLES_PATH": str(ROOT / "roles")})
    return p.returncode, p.stdout + p.stderr


def changed_of(out):
    m = re.findall(r"changed=(\d+)", out)
    return int(m[-1]) if m else -1


ON = {"hardening_grub_password_hash": HASH}
with tempfile.TemporaryDirectory() as d:
    r = make_root(d)
    rc, out = play(r, {})
    check("ozet BOS (varsayilan): hicbir sey yazilmaz", rc == 0 and not (r / "etc/grub.d/40_hardening_password").exists() and CLASS_LINE in (r / "etc/grub.d/10_linux").read_text(), out)
with tempfile.TemporaryDirectory() as d:
    r = make_root(d)
    rc, out = play(r, ON)
    check("uygula: basarili", rc == 0 and "failed=0" in out, out)
    script = (r / "etc/grub.d/40_hardening_password").read_text() if (r / "etc/grub.d/40_hardening_password").exists() else ""
    check("   40_hardening_password: superusers + parola ozeti, mod 0700", 'set superusers="grubadmin"' in script and f"password_pbkdf2 grubadmin {HASH}" in script and oct((r / "etc/grub.d/40_hardening_password").stat().st_mode & 0o777) == "0o700", script)
    check("   10_linux CLASS satirina --unrestricted eklendi", 'CLASS="--class gnu-linux --class gnu --class os --unrestricted"' in (r / "etc/grub.d/10_linux").read_text())
    check("   GRUB_DISABLE_RECOVERY=\"true\" yazildi (yorumlu satir yerine)", re.search(r'^GRUB_DISABLE_RECOVERY="true"$', (r / "etc/default/grub").read_text(), re.M) is not None)
    check("   yedekler /etc/grub.d DISINDA (yoksa menu cift uretilir)", (r / "yedek/10_linux.orig").exists() and (r / "yedek/grub.orig").exists() and sorted(p.name for p in (r / "etc/grub.d").iterdir()) == ["10_linux", "40_hardening_password"], sorted(p.name for p in (r / "etc/grub.d").iterdir()))
    rc, out = play(r, ON)
    check("   ikinci koşu: changed=0 (idempotent)", rc == 0 and changed_of(out) == 0, out)
    rc, out = play(r, {**ON, "hardening_grub_unrestricted_boot": False})
    check("   unrestricted_boot=false'a donus: CLASS yamasi geri alinir, parola kalir", rc == 0 and "--unrestricted" not in (r / "etc/grub.d/10_linux").read_text() and "password_pbkdf2" in (r / "boot/grub/grub.cfg").read_text(), out)
with tempfile.TemporaryDirectory() as d:
    r = make_root(d)
    rc, out = play(r, {**ON, "hardening_grub_unrestricted_boot": False})
    check("unrestricted_boot=false: yalniz parola yazilir (CLASS ve recovery DEGISMEZ)", rc == 0 and "--unrestricted" not in (r / "etc/grub.d/10_linux").read_text() and re.search(r'^GRUB_DISABLE_RECOVERY=', (r / "etc/default/grub").read_text(), re.M) is None and (r / "etc/grub.d/40_hardening_password").exists(), out)
with tempfile.TemporaryDirectory() as d:
    r = make_root(d, with_grub=False)
    rc, out = play(r, ON)
    check("GRUB yok (Pi/LXC/systemd-boot): ATLANIR, not yazar, hicbir sey degismez, hata YOK", rc == 0 and "ATLANDI" in out and not (r / "etc/grub.d/40_hardening_password").exists(), out)
with tempfile.TemporaryDirectory() as d:
    r = make_root(d)
    (r / "KIR").write_text("x")  # sahte update-grub parola satirini uretmez -> dogrulama basarisiz olmali
    before = ((r / "etc/default/grub").read_text(), (r / "etc/grub.d/10_linux").read_text())
    rc, out = play(r, ON)
    check("dogrulama BASARISIZ: playbook duser ve GERI ALIR", rc != 0 and "GERİ ALINDI" in out, out)
    check("   40 betigi silindi, 10_linux ve default/grub ESKI haline dondu", not (r / "etc/grub.d/40_hardening_password").exists() and ((r / "etc/default/grub").read_text(), (r / "etc/grub.d/10_linux").read_text()) == before)
with tempfile.TemporaryDirectory() as d:
    r = make_root(d, class_line='CLASS="--class gnu-linux"')
    rc, out = play(r, ON)
    check("10_linux beklenen biciminde DEGIL: yamalanamaz -> GERI ALINIR ve durur", rc != 0 and not (r / "etc/grub.d/40_hardening_password").exists() and 'CLASS="--class gnu-linux"' in (r / "etc/grub.d/10_linux").read_text(), out)
with tempfile.TemporaryDirectory() as d:
    r = make_root(d)
    for bad in ("duz-parola", "grub.pbkdf2.sha512.x.AA.BB", "grub.pbkdf2.sha1.10000.AA.BB"):
        rc, out = play(r, {"hardening_grub_password_hash": bad})
        check(f"gecersiz ozet reddedilir ve hicbir sey yazilmaz: {bad}", rc != 0 and "DÜZ PAROLA".lower() in out.lower() or (rc != 0 and not (r / "etc/grub.d/40_hardening_password").exists()), out)
    rc, out = play(r, {**ON, "hardening_grub_superuser": "Admin Kullanici"})
    check("gecersiz kullanici adi reddedilir", rc != 0 and not (r / "etc/grub.d/40_hardening_password").exists(), out)
with tempfile.TemporaryDirectory() as d:
    r = make_root(d)
    (r / "sys/firmware").mkdir(parents=True); (r / "sys/firmware/efi").mkdir()
    fb = r / "bin/findmnt"
    fb.write_text("#!/bin/sh\necho zfs\n"); os.chmod(fb, 0o755)
    env = {**os.environ, "PATH": f"{r}/bin:{os.environ['PATH']}"}
    old = os.environ.get("PATH"); os.environ["PATH"] = env["PATH"]
    try:
        rc, out = play(r, ON, platform="proxmox-host")
        check("Proxmox + kok ZFS + UEFI: ATLANIR (proxmox-boot-tool systemd-boot kullanir), hicbir sey yazilmaz", rc == 0 and "ATLANDI" in out and not (r / "etc/grub.d/40_hardening_password").exists(), out)
        (r / "sys/firmware/efi").rmdir()
        rc, out = play(r, ON, platform="proxmox-host")
        check("Proxmox + ZFS ama UEFI YOK (BIOS/GRUB): uygulanir", rc == 0 and (r / "etc/grub.d/40_hardening_password").exists(), out)
        shutil.rmtree(r / "etc/grub.d/40_hardening_password", ignore_errors=True)
    finally:
        os.environ["PATH"] = old
with tempfile.TemporaryDirectory() as d:
    r = make_root(d)
    pb_vars = {"hardening_files_root": str(r), "hardening_files_enabled": False, "hardening_grub_password_hash": HASH, "hardening_grub_update_cmd": str(r / "bin/update-grub"), "hardening_grub_backup_dir": "/yedek",
               "hardening_files_owner": str(os.getuid()), "hardening_files_group": str(os.getgid())}
    pb = r.parent / "p.yml"
    pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": pb_vars, "roles": ["hardening_files"]}]), encoding="utf-8")
    p = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb), "--check"], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg"), "ANSIBLE_ROLES_PATH": str(ROOT / "roles")})
    check("--check: onizleme yazar, hicbir dosya degismez", p.returncode == 0 and "Önizleme (GRUB parolası)" in p.stdout and not (r / "etc/grub.d/40_hardening_password").exists() and not (r / "yedek").exists(), p.stdout[-500:])

# ---- manifest ----
cv = {v["name"]: v for v in yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))["vars"]}
check("component.yml: ozet varsayilan BOS (kapali), kullanici grubadmin, unrestricted_boot true", cv["hardening_grub_password_hash"]["default"] == "" and cv["hardening_grub_superuser"]["default"] == "grubadmin" and cv["hardening_grub_unrestricted_boot"]["default"] is True)
check("   varsayilan rol degerleri component.yml ile ayni", yaml.safe_load((ROOT / "roles/hardening_files/defaults/main.yml").read_text(encoding="utf-8"))["hardening_grub_password_hash"] == "")

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
raise SystemExit(1 if fails else 0)
