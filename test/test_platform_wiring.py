#!/usr/bin/env python3
"""Platform baglantisi (Proxmox VE): hangi roller/gorevler `hardening_platform=proxmox-host` iken NE YAPMALI. `when` ifadeleri gercek Ansible ile degerlendirilir.

Kesin yasaklar (Proxmox'ta HICBIR ayarla calismaz): MTA degisimi (postfix kaldirmak pve-manager ve proxmox-ve'yi kaldirir) ve ufw (guvenlik duvari pve-firewall'dur).
Politika (hardening_pve_strict ile acilir): /tmp ve /dev/shm noexec, usb-storage engeli. AIDE dislamalari yalniz proxmox-host'ta."""
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


def runs(when, vars_):
    """`when` ifadesi bu degiskenlerle TRUE mu (gorev calisir mi)."""
    with tempfile.TemporaryDirectory() as t:
        pb = Path(t) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": vars_,
                                       "tasks": [{"ansible.builtin.debug": {"msg": "CALISTI"}, "when": when}]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    if r.returncode != 0:
        raise RuntimeError(r.stdout + r.stderr)
    return "CALISTI" in r.stdout


def load(p):
    return yaml.safe_load((ROOT / p).read_text(encoding="utf-8"))


base = {t["name"]: t for t in load("roles/hardening_base/tasks/main.yml") if t.get("name")}
dma, purge, usb = base["Install dma (sadece giden mail, port dinlemez)"], base["Purge listening MTAs (postfix, courier)"], base["Disable usb-storage"]
for label, t in (("dma kurulumu", dma), ("postfix/courier kaldirma", purge)):
    w = t["when"]
    check(f"{label}: platform TANIMSIZKEN calisir (tek basina rol/testler)", runs(w, {}))
    check(f"   generic: calisir", runs(w, {"hardening_platform": "generic"}))
    check(f"   proxmox-host: HICBIR ayarla CALISMAZ (strict dahil)", not runs(w, {"hardening_platform": "proxmox-host"}) and not runs(w, {"hardening_platform": "proxmox-host", "hardening_pve_strict": True}))

wu = usb["when"]
V = {"hardening_disable_usb_storage": True}
check("usb-storage: tanimsiz/generic calisir; kapaliysa calismaz", runs(wu, V) and runs(wu, {**V, "hardening_platform_relaxed": False}) and not runs(wu, {"hardening_disable_usb_storage": False}))
check("   proxmox-host (relaxed=True): CALISMAZ; strict (relaxed=False): calisir", not runs(wu, {**V, "hardening_platform_relaxed": True}) and runs(wu, {**V, "hardening_platform_relaxed": False}))

files = {t["name"]: t for t in load("roles/hardening_files/tasks/main.yml") if t.get("name")}
wn = files["Harden the /tmp and /dev/shm mount options"]["when"]
N = {"hardening_tmp_noexec": True, "hardening_shm_noexec": True}
check("noexec: tanimsiz platformda calisir, ikisi de kapaliysa calismaz", runs(wn, N) and not runs(wn, {"hardening_tmp_noexec": False, "hardening_shm_noexec": False}))
check("   proxmox-host (relaxed=True): CALISMAZ; strict: calisir", not runs(wn, {**N, "hardening_platform_relaxed": True}) and runs(wn, {**N, "hardening_platform_relaxed": False}))
check("   salt okunur /tmp raporu platformdan bagimsiz (Proxmox'ta da calisir)", "relaxed" not in str(files["Temporary directory mount report (read-only)"]["when"]))

pb = load("playbooks/harden.yml")[0]
ufw = next(r for r in pb["roles"] if isinstance(r, dict) and r["role"] == "hardening_ufw")
check("ufw rolu: tanimsiz/generic calisir; proxmox-host'ta CALISMAZ", runs(ufw["when"], {}) and runs(ufw["when"], {"hardening_platform": "generic"}) and not runs(ufw["when"], {"hardening_platform": "proxmox-host"}))
check("ufw rolunun etiketi korunur (ufw)", ufw["tags"] == ["ufw"])

aide = {t["name"]: t for t in load("roles/hardening_aide/tasks/main.yml") if t.get("name")}
names = list(aide)
for n in ("Make sure the AIDE config drop-in directory exists (Proxmox VE)", "Exclude Proxmox VE state and guest storage from AIDE"):
    w = aide[n]["when"]
    check(f"AIDE '{n[:40]}...': yalniz proxmox-host", runs(w, {"hardening_platform": "proxmox-host"}) and not runs(w, {"hardening_platform": "generic"}) and not runs(w, {}))
check("AIDE dislamalari veritabani ILK uretilmeden ONCE yazilir", names.index("Exclude Proxmox VE state and guest storage from AIDE") < names.index("Initialize AIDE database (ilk seferde dakikalar sürebilir)"))
ex = load("roles/hardening_aide/defaults/main.yml")["hardening_aide_pve_excludes"]
check("AIDE dislama listesi: /etc/pve, VM deposu ve kume veritabani var", {"/etc/pve", "/var/lib/vz", "/var/lib/pve-cluster"} <= set(ex))
content = aide["Exclude Proxmox VE state and guest storage from AIDE"]["ansible.builtin.copy"]["content"]
check("AIDE drop-in dosya adi aide.conf.d kalibina uyar (harf/rakam/_/-)", aide["Exclude Proxmox VE state and guest storage from AIDE"]["ansible.builtin.copy"]["dest"].rsplit("/", 1)[1].replace("_", "").replace("-", "").isalnum())

pre = load("roles/hardening_preflight/tasks/main.yml")
sf = next(t for t in pre if t.get("name") == "Remember whether this is a Proxmox VE host")["ansible.builtin.set_fact"]
check("preflight platformu KALICI fact olarak yayinlar (varsayilan yalniz preflight'a gorunur)", "hardening_platform" in sf and "hardening_platform_relaxed" in sf and "hardening_is_proxmox" in sf)
sys.exit(1 if fails else 0)
