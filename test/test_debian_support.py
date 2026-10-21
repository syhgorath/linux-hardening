#!/usr/bin/env python3
"""Debian 13 desteği (yapısal): Debian'a özgü üç fark yakalanır.
(1) Debian'da ansible_facts['distribution_version'] alt sürüm içerir ("13.7"): ANA sürüm anahtarı kullanılır (davranış testi: test_facts_namespace.sh).
(2) apt modülü `--check`'te python3-apt ister; yoksa ANLAŞILIR mesajla durulur (gerçek koşuda modül kendisi kurar).
(3) ufw Debian'da varsayılan kurulu değil: `ufw show added` okuması `--check`'te komut yokken düşmemeli."""
import sys
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


pre = yaml.safe_load((ROOT / "roles/hardening_preflight/tasks/main.yml").read_text(encoding="utf-8"))
by = {t.get("name"): t for t in pre}
d = yaml.safe_load((ROOT / "roles/hardening_preflight/defaults/main.yml").read_text(encoding="utf-8"))
check("desteklenen OS: Ubuntu 26.04 ve Debian 13", d["hardening_supported_os"] == {"Ubuntu": ["26.04"], "Debian": ["13"]}, str(d["hardening_supported_os"]))
check("vars/debian-13.yml var ve sshd servis adi ssh", yaml.safe_load((ROOT / "vars/debian-13.yml").read_text(encoding="utf-8")) == {"hardening_ssh_service": "ssh"})
comp = yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))
check("component.yml: debian-13 supported profil", {"id": "debian-13", "status": "supported"} in comp["profiles"])

vk = by["Work out the version key used for the support check and OS variables"]["ansible.builtin.set_fact"]["hardening_os_version"]
check("sürüm anahtari: Debian icin distribution_major_version, digerleri icin distribution_version", "distribution_major_version" in vk and "== 'Debian'" in vk and "distribution_version" in vk)
names = [t.get("name") for t in pre]
check("sürüm anahtari, destek denetiminden ve vars yuklemesinden ONCE hesaplanir", names.index("Work out the version key used for the support check and OS variables") < names.index("Check distribution and version are supported") < names.index("Load OS/version specific variables"))
check("destek denetimi ve vars secimi ham distribution_version KULLANMAZ (alt surum yuzunden Debian'da hep reddederdi)",
      "distribution_version" not in str(by["Check distribution and version are supported"]["ansible.builtin.assert"]["that"]) and "distribution_version" not in str(by["Load OS/version specific variables"]))

pa = by["Check that the apt module can run in check mode (python3-apt)"]
check("python3-apt denetimi: yalniz --check + Debian ailesi, --check'te de calisir, basarisizlik sessiz (karari sonraki gorev verir)",
      "ansible_check_mode" in pa["when"] and "'Debian'" in pa["when"] and pa.get("check_mode") is False and pa.get("failed_when") is False and "import apt_pkg" in pa["ansible.builtin.command"])
st = by["Stop the preview when python3-apt is missing"]
w = " ".join(st["when"])
check("python3-apt yoksa DUR: yalniz --check + Debian ailesi + rc != 0", "ansible_check_mode" in w and "'Debian'" in w and "rc | default(0) != 0" in w)
check("mesaj cozumu soyler (apt-get install python3-apt)", "apt-get install -y python3-apt" in st["ansible.builtin.fail"]["msg"])

ufw = yaml.safe_load((ROOT / "roles/hardening_ufw/tasks/main.yml").read_text(encoding="utf-8"))
sa = next(t for t in ufw if t.get("name") == "Read ufw rules added so far")
check("`ufw show added`: komut yokken --check'te DUSMEZ (Debian'da ufw kurulu degil), gercek koşuda hata sayilir", "not ansible_check_mode" in sa["failed_when"] and "rc != 0" in sa["failed_when"] and sa.get("check_mode") is False)
sys.exit(1 if fails else 0)
