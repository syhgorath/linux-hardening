#!/usr/bin/env python3
"""hardening_preflight: platform ve Proxmox VE koruması. Gerçek `stat` + `set_fact` + `fail`/`assert` görevleri yerel Ansible ile çalıştırılır.

Kurallar: (1) Proxmox VE hostu (/etc/pve ya da /usr/bin/pveversion) `generic` platformla HER DURUMDA reddedilir; `hardening_allow_unsupported` atlatamaz, `--check`'te de çalışır.
(2) `hardening_platform=proxmox-host` yalnızca GERÇEKTEN Proxmox olan hostta kabul edilir ve şimdilik yalnızca `--check` önizlemesi için. (3) Geçersiz platform reddedilir."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
fails = 0


def check(name, ok):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}")


tasks = yaml.safe_load((ROOT / "roles/hardening_preflight/tasks/main.yml").read_text(encoding="utf-8"))
defaults = yaml.safe_load((ROOT / "roles/hardening_preflight/defaults/main.yml").read_text(encoding="utf-8"))
names = [t.get("name") for t in tasks]
first = names.index("Check the platform setting")
last = names.index("Refuse real changes on a Proxmox VE host (only the --check preview is supported so far)")
guard = tasks[first:last + 1]
os_t = next(t for t in tasks if "ansible.builtin.assert" in t and t.get("name") == "Check distribution and version are supported")

check("sira: platform/Proxmox korumasi, OS/surum denetiminden ONCE", last < tasks.index(os_t))
check("korumalar allow_unsupported'a BAGLI DEGIL (atlatilamaz)", all("allow_unsupported" not in str(t.get("when", "")) for t in guard))
check("Proxmox isareti taramasi --check'te de calisir (check_mode: false)", next(t for t in guard if "ansible.builtin.stat" in t).get("check_mode") is False)
check("varsayilanlar: platform generic, bilinen [generic, proxmox-host], strict false, isaretler /etc/pve ve /usr/bin/pveversion",
      (defaults["hardening_platform"], defaults["hardening_platforms_known"], defaults["hardening_pve_strict"], defaults["hardening_proxmox_markers"]) == ("generic", ["generic", "proxmox-host", "raspberry-pi"], False, ["/etc/pve", "/usr/bin/pveversion"]))
check("OS denetimi hala allow_unsupported ile atlanir (Proxmox disinda davranis degismedi)", "hardening_allow_unsupported" in str(os_t.get("when")))


c0 = names.index("Look for the Proxmox cluster marker")
c1 = names.index("Refuse PermitRootLogin no on a Proxmox VE cluster node")
cluster = tasks[c0:c1 + 1]
check("kume denetimi: platform proxmox-host ile sinirli, --check'te de calisir, allow_unsupported'a bagli degil",
      cluster[0].get("check_mode") is False and "proxmox-host" in cluster[0]["when"] and all("allow_unsupported" not in str(t.get("when", "")) for t in cluster))
check("kume denetimi OS denetiminden ONCE", c1 < tasks.index(os_t))


def play(platform, markers, allow=False, check_mode=False, strict=False):
    with tempfile.TemporaryDirectory() as t:
        pb = Path(t) / "p.yml"
        vars_ = {"hardening_proxmox_markers": markers, "hardening_allow_unsupported": allow, "hardening_platform": platform,
                 "hardening_platforms_known": defaults["hardening_platforms_known"], "hardening_pve_strict": strict}
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": vars_,
                                       "tasks": guard + [{"ansible.builtin.debug": {"msg": "DEVAM-EDILDI relaxed={{ hardening_platform_relaxed }} proxmox={{ hardening_is_proxmox }} platform={{ hardening_platform }}"}}]}]), encoding="utf-8")
        cmd = ["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)] + (["--check"] if check_mode else [])
        r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


with tempfile.TemporaryDirectory() as t:
    pve = Path(t) / "pve"
    pve.mkdir()
    no = [str(Path(t) / "yok"), str(Path(t) / "yok2")]
    rc, out = play("generic", no)
    check("generic + Proxmox isareti YOK: devam eder (relaxed=False, proxmox=False)", rc == 0 and "DEVAM-EDILDI relaxed=False proxmox=False platform=generic" in out)
    for allow in (False, True):
        rc, out = play("generic", [str(pve)], allow=allow)
        check(f"generic + isaret VAR (allow_unsupported={allow}): DURUR, hangi isaret oldugunu soyler, --check onerisini verir", rc != 0 and "Bu sunucu bir Proxmox VE hostu" in out and str(pve) in out and "-e hardening_platform=proxmox-host" in out and "DEVAM-EDILDI" not in out)
    rc, out = play("generic", [str(pve)], check_mode=True)
    check("generic + isaret VAR, --check'te de DURUR", rc != 0 and "Bu sunucu bir Proxmox VE hostu" in out)
    f = Path(t) / "pveversion"
    f.write_text("x")
    rc, out = play("generic", [no[0], str(f)])
    check("ikinci isaret (pveversion dosyasi) de yeterli", rc != 0 and "Bu sunucu bir Proxmox VE hostu" in out)
    rc, out = play("proxmox-host", [str(pve)], check_mode=True)
    check("proxmox-host + isaret VAR + --check: KABUL, relaxed=True (strict degil)", rc == 0 and "DEVAM-EDILDI relaxed=True proxmox=True platform=proxmox-host" in out)
    rc, out = play("proxmox-host", [str(pve)], check_mode=True, strict=True)
    check("   hardening_pve_strict=true: relaxed=False", rc == 0 and "relaxed=False proxmox=True platform=proxmox-host" in out)
    for allow in (False, True):
        rc, out = play("proxmox-host", [str(pve)], allow=allow)
        check(f"proxmox-host + GERCEK KOSU (allow_unsupported={allow}): DURUR (yalniz --check destekli)", rc != 0 and "YALNIZCA önizleme (--check)" in out and "DEVAM-EDILDI" not in out)
    rc, out = play("proxmox-host", no, check_mode=True)
    check("proxmox-host ama Proxmox DEGIL: DURUR ('Proxmox VE değil')", rc != 0 and "Proxmox VE değil" in out)
    rc, out = play("baska-platform", no)
    check("gecersiz platform (baska-platform): DURUR ve gecerli degerleri soyler", rc != 0 and "hardening_platform geçersiz" in out and "generic, proxmox-host, raspberry-pi" in out)
    rc, out = play("", no)
    check("bos platform: DURUR", rc != 0 and "hardening_platform geçersiz" in out)


def play_cluster(platform, clustered, root_login=None, check_mode=True):
    with tempfile.TemporaryDirectory() as t:
        marker = Path(t) / "corosync.conf"
        if clustered:
            marker.write_text("totem {}")
        vars_ = {"hardening_platform": platform, "hardening_pve_cluster_marker": str(marker)}
        if root_login is not None:
            vars_["hardening_ssh_permit_root_login"] = root_login
        pb = Path(t) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": vars_,
                                       "tasks": cluster + [{"ansible.builtin.debug": {"msg": "DEVAM-EDILDI"}}]}]), encoding="utf-8")
        cmd = ["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)] + (["--check"] if check_mode else [])
        r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


rc, out = play_cluster("proxmox-host", True)
check("KUME + PermitRootLogin no (varsayilan): DURUR ve prohibit-password onerir", rc != 0 and "kümenin parçası" in out and "prohibit-password" in out and "DEVAM-EDILDI" not in out)
rc, out = play_cluster("proxmox-host", True, root_login="no")
check("KUME + acikca 'no': DURUR", rc != 0 and "kümenin parçası" in out)
rc, out = play_cluster("proxmox-host", True, root_login="prohibit-password")
check("KUME + prohibit-password: devam eder", rc == 0 and "DEVAM-EDILDI" in out)
rc, out = play_cluster("proxmox-host", False)
check("tek dugum + no: devam eder", rc == 0 and "DEVAM-EDILDI" in out)
rc, out = play_cluster("generic", True)
check("generic platformda kume denetimi hic calismaz (baska ortamlar etkilenmez)", rc == 0 and "DEVAM-EDILDI" in out)
sys.exit(1 if fails else 0)
