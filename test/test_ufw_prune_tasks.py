#!/usr/bin/env python3
"""hardening_ufw: eski SSH kuralı temizliğinin görev yapısı (statik). Silme, yanlışlıkla erişim kaybına yol açmamalı:
varsayılan kapalı, `--check`'te silmez, kontrol makinesi adresi/boş allow_from gibi durumlarda silmez, silmeden SONRA doğrulama
yapılır ve eksik kural varsa ufw ETKİNLEŞTİRİLMEDEN durulur.
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
tasks = yaml.safe_load((ROOT / "roles/hardening_ufw/tasks/main.yml").read_text(encoding="utf-8"))
defaults = yaml.safe_load((ROOT / "roles/hardening_ufw/defaults/main.yml").read_text(encoding="utf-8"))
fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail}")


def find(pred):
    return next((i for i, t in enumerate(tasks) if pred(t)), None)


def mod(t):
    return next((k for k in t if k.startswith("ansible.builtin.")), None)


check("varsayılan: hardening_ufw_prune_ssh=false (yalnızca uyarır)", defaults.get("hardening_ufw_prune_ssh") is False)

read_i = find(lambda t: mod(t) == "ansible.builtin.command" and t["ansible.builtin.command"] == "ufw show added" and "hardening_ufw_added" == t.get("register"))
find_i = find(lambda t: mod(t) == "ansible.builtin.script" and "stale_ssh_rules.py" in str(t["ansible.builtin.script"]) and t.get("register") == "hardening_ufw_stale_raw")
del_i = find(lambda t: mod(t) == "ansible.builtin.command" and "delete" in str(t["ansible.builtin.command"]))
vread_i = find(lambda t: t.get("register") == "hardening_ufw_added_after")
vrun_i = find(lambda t: t.get("register") == "hardening_ufw_verify_raw")
assert_i = find(lambda t: mod(t) == "ansible.builtin.assert" and "missing" in str(t))
enable_i = find(lambda t: mod(t) == "ansible.builtin.command" and "ufw --force enable" in str(t["ansible.builtin.command"]))
allow_i = find(lambda t: mod(t) == "ansible.builtin.command" and "ufw allow from" in str(t["ansible.builtin.command"]))

for name, i in (("kuralları okuma", read_i), ("eski kural bulma", find_i), ("silme", del_i), ("silme sonrası okuma", vread_i), ("silme sonrası doğrulama", vrun_i), ("eksikse durdurma (assert)", assert_i), ("ufw enable", enable_i)):
    check(f"görev var: {name}", i is not None)
if None in (read_i, find_i, del_i, vread_i, vrun_i, assert_i, enable_i, allow_i):
    sys.exit(1)

check("sıra: izinleri yaz -> oku -> bul -> sil -> yeniden oku -> doğrula -> assert -> ufw enable",
      allow_i < read_i < find_i < del_i < vread_i < vrun_i < assert_i < enable_i)

for label, i in (("okuma", read_i), ("bulma", find_i), ("silme sonrası okuma", vread_i), ("silme sonrası doğrulama", vrun_i)):
    t = tasks[i]
    check(f"salt okunur ve --check'te çalışır: {label}", t.get("changed_when") is False and t.get("check_mode") is False)

d = tasks[del_i]
w = str(d.get("when"))
check("silme: yalnızca hardening_ufw_prune_ssh true iken", "hardening_ufw_prune_ssh" in w)
check("silme: --check'te atlanır", "not ansible_check_mode" in w)
check("silme: betik hata verdiyse (error) atlanır", "error" in w and "== 0" in w.replace(" ", "") or "length == 0" in w)
argv = d["ansible.builtin.command"]["argv"]
check("silme: argv listesi (kabuk yok) ve --force", argv[:3] == ["ufw", "--force", "delete"], f"argv={argv}")
check("silme: yalnızca betiğin 'stale' listesini dolaşır", "hardening_ufw_stale.stale" in str(d.get("loop")))

for label, i in (("silme sonrası okuma", vread_i), ("silme sonrası doğrulama", vrun_i), ("assert", assert_i)):
    t = tasks[i]
    check(f"yalnızca silme açıkken ve --check dışında: {label}", "hardening_ufw_prune_ssh" in str(t.get("when")) and "not ansible_check_mode" in str(t.get("when")))

script = (ROOT / "roles/hardening_ufw/files/stale_ssh_rules.py").read_text(encoding="utf-8")
check("betik kendi başına silme yapmaz (yalnızca karar verir)", "subprocess" not in script and "os.system" not in script)
sys.exit(1 if fails else 0)
