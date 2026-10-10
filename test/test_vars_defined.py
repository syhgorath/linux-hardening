#!/usr/bin/env python3
"""Rollerde/playbooklarda kullanılan her hardening_* değişkeninin tanımlı olduğunu denetler (group_vars OLMADAN).

Tanım kaynakları: roles/*/defaults/main.yml, vars/*.yml, register:, set_fact:, görev `vars:` blokları.
Bunun amacı: sshpocket gibi bir araç `-i /tmp/x.yml` ile çalıştırınca değişkenlerin tanımsız kalmamasıdır.
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PAT = re.compile(r"\bhardening_[a-z0-9_]+\b")

used, defined = {}, set()
files = [p for p in list(ROOT.glob("roles/**/*")) + list(ROOT.glob("playbooks/*.yml")) if p.is_file()]
for p in files:
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    for m in PAT.findall(text):
        used.setdefault(m, set()).add(str(p.relative_to(ROOT)))
    for m in re.findall(r"register:\s*(hardening_[a-z0-9_]+)", text):
        defined.add(m)
    # set_fact / vars: blok anahtarlari (girintili "hardening_x:" tanimlari)
    for m in re.findall(r"^\s+(hardening_[a-z0-9_]+):", text, re.M):
        defined.add(m)
for p in ROOT.glob("roles/*/defaults/main.yml"):
    defined |= set(yaml.safe_load(p.read_text(encoding="utf-8")) or {})
for p in ROOT.glob("vars/*.yml"):
    defined |= set(yaml.safe_load(p.read_text(encoding="utf-8")) or {})
role_names = {p.name for p in ROOT.glob("roles/hardening_*")}
# ifade icinde gecen ama deger olmayanlar (dosya/rol adlari, yorumlardaki kavramlar)
# hardening_index: Lynis rapor alanı adı (değişken değil; audit.yml yorum/regex'inde geçer)
ignore = role_names | {"hardening_profile", "hardening_index"}

missing = {k: v for k, v in used.items() if k not in defined and k not in ignore}
# bilerek tanimsiz birakilanlar: kullanicinin vermesi beklenen/opsiyonel
# - hardening_ssh_port: kaldirildi; yalniz 'is defined' uyarisinda gecer
# - hardening_scan_dir: opsiyonel; audit.yml `| default(playbook_dir ~ '/../scans')` ile okur
allowed_optional = {"hardening_ssh_port", "hardening_scan_dir"}
missing = {k: v for k, v in missing.items() if k not in allowed_optional}
if missing:
    print("TANIMSIZ degiskenler:")
    for k, v in sorted(missing.items()):
        print(f"  - {k}  ({', '.join(sorted(v))})")
    sys.exit(1)
print(f"  ok   {len(used)} degisken kullaniliyor, hepsi tanimli")

# kaldirilan degisken geri gelmesin (varsayilan olarak)
for p in ROOT.glob("roles/*/defaults/main.yml"):
    if "hardening_ssh_port" in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}):
        print(f"  FAIL hardening_ssh_port varsayilan olarak geri gelmis: {p}")
        sys.exit(1)
print("  ok   hardening_ssh_port varsayilan olarak tanimli degil")

# guvenlik varsayilanlari: allow_from BOS olmali (kilitlenme korumasi, PR-A); kbd/forwarding guvenli
merged = {}
for p in sorted(ROOT.glob("roles/*/defaults/main.yml")):
    merged.update(yaml.safe_load(p.read_text(encoding="utf-8")) or {})
expect = {
    "hardening_ssh_allow_from": [],
    "hardening_ssh_disable_password": True,
    "hardening_ssh_kbdinteractive": False,
    "hardening_ssh_allow_tcp_forwarding": "no",
    "hardening_fail2ban_ignoreip": "127.0.0.1/8 ::1",
    "hardening_allow_unsupported": False,
    "hardening_rollback_enabled": True,
    "hardening_rollback_timeout": 300,
}
bad = False
for k, want in expect.items():
    if merged.get(k) != want:
        print(f"  FAIL guvenli varsayilan degismis: {k} = {merged.get(k)!r} (beklenen {want!r})")
        bad = True
    else:
        print(f"  ok   varsayilan {k} = {want!r}")
if bad:
    sys.exit(1)
print("TAMAM")
