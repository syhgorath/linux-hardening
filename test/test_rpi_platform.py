#!/usr/bin/env python3
"""hardening_preflight: Raspberry Pi platformu. Gerçek `stat` + `set_fact` + `fail`/`debug` görevleri yerel Ansible ile çalıştırılır (sahte işaret dosyalarıyla).

Kurallar: (1) `hardening_platform=raspberry-pi` yalnızca GERÇEK Pi'de kabul edilir, hardening_allow_unsupported atlatamaz; (2) Pi algılanır ama platform generic ise rol DURMAZ, yalnızca not düşer
(Proxmox'un aksine); (3) raspberry-pi platformu YALNIZCA usb-storage engelini gevşetir (hardening_platform_relaxed, yani rp_filter/noexec, DEĞİŞMEZ); hardening_rpi_strict geri açar."""
import os
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


tasks = yaml.safe_load((ROOT / "roles/hardening_preflight/tasks/main.yml").read_text(encoding="utf-8"))
defaults = yaml.safe_load((ROOT / "roles/hardening_preflight/defaults/main.yml").read_text(encoding="utf-8"))
names = [t.get("name") for t in tasks]
a, b = names.index("Look for Raspberry Pi markers"), names.index("Note a Raspberry Pi that is hardened with the generic platform")
pi = tasks[a:b + 1]
os_t = next(t for t in tasks if t.get("name") == "Check distribution and version are supported")
base = yaml.safe_load((ROOT / "roles/hardening_base/tasks/main.yml").read_text(encoding="utf-8"))
usb = next(t for t in base if t.get("name") == "Disable usb-storage")

check("Pi korumasi OS/surum denetiminden ONCE", b < tasks.index(os_t))
check("Pi isareti taramasi --check'te de calisir", pi[0].get("check_mode") is False)
check("raspberry-pi platform reddi allow_unsupported'a BAGLI DEGIL", all("allow_unsupported" not in str(t.get("when", "")) for t in pi))
check("varsayilanlar: bilinen platformlar, rpi_strict false, isaretler", (defaults["hardening_platforms_known"], defaults["hardening_rpi_strict"], defaults["hardening_rpi_markers"]) ==
      (["generic", "proxmox-host", "raspberry-pi"], False, ["/etc/rpi-issue", "/boot/firmware/config.txt"]))
check("usb-storage kosulu: rpi_relaxed ile gevsetilir, Proxmox kosulu da korunur", "hardening_rpi_relaxed" in usb["when"] and "hardening_platform_relaxed" in usb["when"])

pre = (ROOT / "roles/hardening_preflight/tasks/main.yml").read_text(encoding="utf-8")
check("Proxmox gevsetmesi (hardening_platform_relaxed) raspberry-pi'yi KAPSAMAZ (rp_filter/noexec Pi'de degismez)", "hardening_platform_relaxed: \"{{ hardening_platform == 'proxmox-host' and not (hardening_pve_strict | bool) }}\"" in pre)


def play(platform, markers, allow=False, strict=False):
    with tempfile.TemporaryDirectory() as t:
        pb = Path(t) / "p.yml"
        vars_ = {"hardening_rpi_markers": markers, "hardening_allow_unsupported": allow, "hardening_platform": platform,
                 "hardening_platforms_known": defaults["hardening_platforms_known"], "hardening_rpi_strict": strict}
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": vars_,
                                       "tasks": pi + [{"ansible.builtin.debug": {"msg": "DEVAM-EDILDI rpi={{ hardening_is_rpi }} relaxed={{ hardening_rpi_relaxed }}"}}]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


with tempfile.TemporaryDirectory() as t:
    fake = str(Path(t) / "rpi-issue")
    Path(fake).write_text("Raspberry Pi reference 2026-01-01\n", encoding="utf-8")
    missing = str(Path(t) / "yok")

    rc, out = play("raspberry-pi", [fake])
    check("gercek Pi + raspberry-pi -> devam, rpi=True relaxed=True", rc == 0 and "rpi=True relaxed=True" in out, out[-200:])
    rc, out = play("raspberry-pi", [missing])
    check("Pi olmayan host + raspberry-pi -> REDDEDILIR", rc != 0 and "bir Raspberry Pi değil" in out and "DEVAM-EDILDI" not in out, out[-200:])
    rc, out = play("raspberry-pi", [missing], allow=True)
    check("   hardening_allow_unsupported atlatamaz", rc != 0 and "DEVAM-EDILDI" not in out)
    rc, out = play("generic", [fake])
    check("Pi + generic -> DURMAZ, not dusulur, relaxed=False", rc == 0 and "NOT (raspberry-pi)" in out and "rpi=True relaxed=False" in out, out[-300:])
    rc, out = play("generic", [missing])
    check("Pi olmayan + generic -> sessiz, devam", rc == 0 and "NOT (raspberry-pi)" not in out and "rpi=False relaxed=False" in out)
    rc, out = play("raspberry-pi", [fake], strict=True)
    check("raspberry-pi + hardening_rpi_strict -> relaxed=False (usb-storage engeli geri)", rc == 0 and "relaxed=False" in out)
    rc, out = play("raspberry-pi", [fake, missing])
    check("birden cok isaretten biri yeter", rc == 0 and "rpi=True" in out)

# usb-storage gorevi gercekten gevsetilir (kosul degerlendirmesi)
def usb_runs(rpi_relaxed, pve_relaxed, disable=True):
    with tempfile.TemporaryDirectory() as t:
        pb = Path(t) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_disable_usb_storage": disable, "hardening_rpi_relaxed": rpi_relaxed, "hardening_platform_relaxed": pve_relaxed},
                                       "tasks": [{"ansible.builtin.debug": {"msg": "USB-ENGEL-UYGULANIR"}, "when": usb["when"]}]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return "USB-ENGEL-UYGULANIR" in r.stdout and "skipping" not in r.stdout


check("usb-storage: normal host -> uygulanir", usb_runs(False, False))
check("usb-storage: Pi (relaxed) -> UYGULANMAZ", not usb_runs(True, False))
check("usb-storage: Proxmox (relaxed) -> UYGULANMAZ (eski davranis korunur)", not usb_runs(False, True))
check("usb-storage: Pi + strict (relaxed=False) -> uygulanir", usb_runs(False, False))
check("usb-storage: hardening_disable_usb_storage=false -> hic uygulanmaz", not usb_runs(False, False, disable=False))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
