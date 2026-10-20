#!/usr/bin/env python3
"""hardening_files: /tmp ve /dev/shm nodev,nosuid,noexec UYGULAMA görevleri. Statik yapı + gerçek görev zinciri: plan betiği (sahte okuma çıktılarıyla) -> gerçek `copy`/`lineinfile`
(geçici dosyalara) -> ikinci koşuda değişiklik YOK. remount komutları gerçek sunucuda çalışır (VM'de denendi: verification-log); burada yalnızca koşulları sınanır."""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail}")


def eq(name, want, got):
    check(name, want == got, f"beklenen={want!r} gercek={got!r}")


def walk(ts):
    for t in ts or []:
        yield t
        yield from walk(t.get("block"))


tasks = yaml.safe_load((ROOT / "roles/hardening_files/tasks/main.yml").read_text(encoding="utf-8"))
defaults = yaml.safe_load((ROOT / "roles/hardening_files/defaults/main.yml").read_text(encoding="utf-8"))
blk = next(t for t in tasks if t.get("name") == "Harden the /tmp and /dev/shm mount options")
by = {t["name"]: t for t in walk(blk["block"]) if t.get("name")}
names = [t["name"] for t in walk(blk["block"]) if t.get("name")]
names_all = [t.get("name") for t in tasks]

eq("varsayilanlar: ikisi de ACIK", (True, True), (defaults["hardening_tmp_noexec"], defaults["hardening_shm_noexec"]))
check("blok iki degiskenle de kapatilabilir (biri aciksa calisir)", "hardening_tmp_noexec | bool" in blk["when"] and "hardening_shm_noexec | bool" in blk["when"] and " or " in blk["when"])
check("uygulama blogu RAPORDAN once (rapor sonucu yansitsin)", names_all.index(blk["name"]) < names_all.index("Temporary directory mount report (read-only)"))
reads = [by[n] for n in ("Read the mounts behind /tmp and /dev/shm for the plan", "Read whether tmp.mount manages /tmp", "Read the /dev/shm line of /etc/fstab", "Plan the mount option changes")]
check("okuma/plan gorevleri --check'te de calisir (check_mode: false)", all(t.get("check_mode") is False for t in reads))
check("okumalar basarisiz olursa rol durmaz", all(t.get("failed_when") is False for t in reads[:3]))
check("tmp.mount durumu `systemd` ile yalniz OKUNUR (state/enabled yok)", set(by["Read whether tmp.mount manages /tmp"]["ansible.builtin.systemd"]) == {"name"})
for n in ("Apply nodev,nosuid,noexec to /tmp now", "Apply nodev,nosuid,noexec to /dev/shm now"):
    t = by[n]
    check(f"{n}: --check'te CALISMAZ ve yalniz plan gerektiriyorsa", "not ansible_check_mode" in t["when"] and "remount" in t["when"])
check("remount komutlari tam: mount -o remount,nodev,nosuid,noexec <yol> (yalniz /tmp ve /dev/shm)", str(by["Apply nodev,nosuid,noexec to /tmp now"]["ansible.builtin.command"]).startswith("mount -o remount,nodev,nosuid,noexec /tmp") and str(by["Apply nodev,nosuid,noexec to /dev/shm now"]["ansible.builtin.command"]).startswith("mount -o remount,nodev,nosuid,noexec /dev/shm"))
check("drop-in yeniden yuklemesi yalniz drop-in DEGISINCE ve --check disinda", "is changed" in by["Reload systemd after the tmp.mount drop-in changed"]["when"] and "not ansible_check_mode" in by["Reload systemd after the tmp.mount drop-in changed"]["when"])
check("kalici yazimlar yalniz plan.persist iken", "tmp.persist" in str(by["Make /tmp nodev,nosuid,noexec persistent (tmp.mount drop-in)"]["when"]) and "shm.persist" in str(by["Make /dev/shm nodev,nosuid,noexec persistent (/etc/fstab)"]["when"]))
cp = by["Make /tmp nodev,nosuid,noexec persistent (tmp.mount drop-in)"]["ansible.builtin.copy"]
check("drop-in: [Mount] Options nosuid,nodev,noexec iceriyor, mod 0644 root", "[Mount]" in cp["content"] and re.search(r"^Options=.*nosuid.*nodev.*noexec", cp["content"], re.M) and cp["mode"] == "0644")
lf = by["Make /dev/shm nodev,nosuid,noexec persistent (/etc/fstab)"]["ansible.builtin.lineinfile"]
eq("fstab satiri tam (CIS bicimi)", "tmpfs /dev/shm tmpfs defaults,nodev,nosuid,noexec 0 0", lf["line"])
for k in ("hardening_tmp_noexec", "hardening_shm_noexec"):
    v = next(x for x in yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))["vars"] if isinstance(x, dict) and x["name"] == k)
    check(f"component.yml {k}: bool, varsayilan true, warn_if FALSE (zayiflatma uyarisi; varsayilana esit degil, #74)", v["type"] == "bool" and v["default"] is True and v.get("warn_if") is False)

FSTAB = "UUID=abc / ext4 defaults 0 1\n/swap.img none swap sw 0 0\n"
T = "/tmp: /tmp tmpfs rw,nosuid,nodev,size=1k"
S = "/dev/shm: /dev/shm tmpfs rw,nosuid,nodev,inode64"


def chain(d, fstab_text, mounts, shm_line=""):
    fstab = Path(d) / "fstab"; fstab.write_text(fstab_text, encoding="utf-8")
    dropdir = Path(d) / "tmp.mount.d"
    ev = dict(by["Plan the mount option changes"]["ansible.builtin.script"])
    ev["cmd"] = re.sub(r"^tmp_plan\.py", str(ROOT / "roles/hardening_files/files/tmp_plan.py"), ev["cmd"].strip())
    c2 = dict(cp); c2["dest"] = str(dropdir / "50-hardening.conf"); c2.pop("owner"); c2.pop("group")
    l2 = dict(lf); l2["path"] = str(fstab)
    play = [{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_tmp_noexec": True, "hardening_shm_noexec": True},
             "tasks": [
                 {"ansible.builtin.set_fact": {"hardening_tmpm_mounts": {"stdout_lines": mounts}, "hardening_tmpm_unit": {"status": {"ActiveState": "active"}}, "hardening_tmpm_fstab": {"stdout": shm_line}}},
                 {"ansible.builtin.script": ev, "register": "hardening_tmpm_raw", "changed_when": False},
                 {"ansible.builtin.set_fact": {"hardening_tmpm_plan": by["Parse the mount plan"]["ansible.builtin.set_fact"]["hardening_tmpm_plan"]}},
                 {"ansible.builtin.file": {"path": str(dropdir), "state": "directory", "mode": "0755"}, "when": by["Create the tmp.mount drop-in directory"]["when"]},
                 {"ansible.builtin.copy": c2, "when": by["Make /tmp nodev,nosuid,noexec persistent (tmp.mount drop-in)"]["when"]},
                 {"ansible.builtin.lineinfile": l2, "when": by["Make /dev/shm nodev,nosuid,noexec persistent (/etc/fstab)"]["when"]},
             ]}]
    pb = Path(d) / "p.yml"
    pb.write_text(yaml.safe_dump(play), encoding="utf-8")
    r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    return r, fstab, dropdir / "50-hardening.conf"


with tempfile.TemporaryDirectory() as d:
    r, fstab, drop = chain(d, FSTAB, [T, S])
    check("zincir 1: kosu basarili", r.returncode == 0, r.stdout[-300:] + r.stderr[-200:])
    eq("   fstab'a /dev/shm satiri EKLENDI, eski satirlar korundu", (1, True, True), (fstab.read_text().count("/dev/shm"), "UUID=abc / ext4" in fstab.read_text(), "/swap.img" in fstab.read_text()))
    check("   tmp.mount drop-in yazildi", drop.exists() and "noexec" in drop.read_text())
    before = (fstab.read_text(), drop.read_text())
    r2, _, _ = chain(d, fstab.read_text(), [T.replace("nosuid,nodev", "nosuid,nodev,noexec"), S.replace("nosuid,nodev", "nosuid,nodev,noexec")], "tmpfs /dev/shm tmpfs defaults,nodev,nosuid,noexec 0 0")
    check("   ikinci kosu: changed=0, dosyalar ayni (idempotent)", "changed=0" in r2.stdout and (fstab.read_text(), drop.read_text()) == before, r2.stdout[-200:])
with tempfile.TemporaryDirectory() as d:
    own = FSTAB + "tmpfs /dev/shm tmpfs defaults,size=2g 0 0\n"
    r, fstab, drop = chain(d, own, [T, S], "tmpfs /dev/shm tmpfs defaults,size=2g 0 0")
    eq("zincir 2: kullanicinin size=2g /dev/shm satiri DEGISMEZ", own, fstab.read_text())
    check("   ama /tmp drop-in'i yine yazilir", drop.exists())
with tempfile.TemporaryDirectory() as d:
    r, fstab, drop = chain(d, FSTAB, ["/tmp: / ext4 rw,relatime", S])
    check("zincir 3: /tmp ayri baglama degil -> drop-in YAZILMAZ (yonetilmeyen dizine dokunulmaz)", not drop.exists())
sys.exit(1 if fails else 0)
