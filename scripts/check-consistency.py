#!/usr/bin/env python3
"""component.yml, VERSION, CHANGELOG, destek matrisi ve rol varsayılanları arasındaki tutarlılığı denetler.

Kullanım (repo kökünde, PyYAML'ın kurulu olduğu ortamda; ansible-core ile gelir):
    python3 -I scripts/check-consistency.py
Hata varsa çıkış kodu 1.

Profil eşleme kuralı (AÇIK):
  component.yml profile id'si "<dagitim>-<surum>" biçimindeyse (status: supported) şu eşlemeyle
  roles/hardening_preflight/defaults/main.yml içindeki hardening_supported_os ile karşılaştırılır:
      ubuntu-26.04  <->  hardening_supported_os: {Ubuntu: ["26.04"]}
  Dağıtım adı eşlemesi DISTRO_MAP içindedir (küçük harfli id öneki -> Ansible'ın ansible_distribution değeri).
  status: planned profiller hardening_supported_os içinde OLMAMALIDIR, ama docs/SUPPORT.md'de görünmelidir.
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DISTRO_MAP = {"ubuntu": "Ubuntu"}                       # id öneki -> ansible_distribution
SUPPORT_NAMES = {"ubuntu": "Ubuntu", "rpi": "Raspberry Pi", "proxmox": "Proxmox"}  # SUPPORT.md'de aranan ad

errors = []


def err(msg):
    errors.append(msg)


def load(path):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


comp = load("component.yml")
version_file = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

# 1) sürüm tutarlılığı
if comp.get("version") != version_file:
    err(f"VERSION ({version_file}) ile component.yml version ({comp.get('version')}) aynı değil")
changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
if not re.search(rf"^## \[{re.escape(version_file)}\]", changelog, re.M):
    err(f"CHANGELOG.md içinde '## [{version_file}]' başlığı yok")

# 2) profiller <-> hardening_supported_os
supported_os = load("roles/hardening_preflight/defaults/main.yml")["hardening_supported_os"]
want = set()
for ver_list_dist, vers in supported_os.items():
    for v in vers:
        want.add((ver_list_dist, str(v)))
have = set()
planned_ids = []
for prof in comp.get("profiles", []):
    pid, status = prof["id"], prof["status"]
    if status not in ("supported", "planned"):
        err(f"profil {pid}: bilinmeyen status {status!r}")
        continue
    if status == "planned":
        planned_ids.append(pid)
        continue
    m = re.fullmatch(r"([a-z]+)-([0-9][0-9.]*)", pid)
    if not m:
        err(f"supported profil id'si '<dagitim>-<surum>' biçiminde olmalı: {pid}")
        continue
    dist = DISTRO_MAP.get(m.group(1))
    if dist is None:
        err(f"profil {pid}: DISTRO_MAP'te '{m.group(1)}' yok")
        continue
    have.add((dist, m.group(2)))
for item in sorted(want - have):
    err(f"hardening_supported_os içinde {item} var ama component.yml'de supported profil yok")
for item in sorted(have - want):
    err(f"component.yml supported profil {item} hardening_supported_os içinde yok")

# 3) docs/SUPPORT.md satırları
# Tablo satırları: Dağıtım (1. sütun), Sürüm (2.), Durum (3.). Ad yalnızca 1. sütunda aranır; "Not"
# veya "Durum" sütunundaki rastlantısal kelimeler (örn. "test edildi (Proxmox VM)") eşleşmeyi bozmasın.
rows = []
for l in (ROOT / "docs/SUPPORT.md").read_text(encoding="utf-8").splitlines():
    if l.startswith("|") and not set(l) <= set("|- "):
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(cells) >= 3:
            rows.append(cells[:3])
for prof in comp.get("profiles", []):
    pid = prof["id"]
    key = pid.split("-")[0]
    name = SUPPORT_NAMES.get(key)
    if name is None:
        err(f"profil {pid}: SUPPORT_NAMES'te '{key}' yok")
        continue
    ver = pid.split("-", 1)[1] if re.fullmatch(r"[a-z]+-[0-9][0-9.]*", pid) else None
    hit = [r for r in rows if name in r[0] and (ver is None or ver in r[1])]
    if not hit:
        err(f"docs/SUPPORT.md içinde {pid} için satır yok")
        continue
    status_cell = hit[0][2].lower()
    if prof["status"] == "supported" and "desteklenir" not in status_cell:
        err(f"docs/SUPPORT.md: {pid} 'Desteklenir' görünmüyor")
    if prof["status"] == "planned" and "planlandı" not in status_cell:
        err(f"docs/SUPPORT.md: {pid} 'Planlandı' görünmüyor")

# 4) vars: gerçekten tanımlı mı (sözleşme yalan söylemesin)
defined = set()
for f in (ROOT / "roles").glob("*/defaults/main.yml"):
    defined |= set(yaml.safe_load(f.read_text(encoding="utf-8")) or {})
# hardening_scan_dir bir playbook değişkenidir (audit.yml), rol defaults'ında değil
playbook_text = (ROOT / "playbooks/audit.yml").read_text(encoding="utf-8")
for v in comp.get("vars", []):
    if v == "hardening_ssh_port":
        err("component.yml vars içinde hardening_ssh_port olmamalı (kaldırıldı)")
    if v not in defined and v not in playbook_text:
        err(f"component.yml vars: {v} hiçbir rol defaults'ında/audit.yml'de geçmiyor")

# 5) eylemler
for name, act in comp.get("actions", {}).items():
    for k in ("cmd", "effects", "requires_sudo"):
        if k not in act:
            err(f"actions.{name}: '{k}' yok")
    playbook = re.search(r"playbooks/\S+\.yml", act.get("cmd", ""))
    if playbook and not (ROOT / playbook.group(0)).exists():
        err(f"actions.{name}: {playbook.group(0)} yok")
    for req in act.get("requires", []):
        if req not in comp["actions"]:
            err(f"actions.{name}.requires: bilinmeyen eylem {req}")
    bad = set(act.get("effects", [])) - {"installs-package", "changes-config"}
    if bad:
        err(f"actions.{name}.effects geçersiz: {sorted(bad)}")

if errors:
    print("TUTARSIZLIK:")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print(f"OK: component.yml v{version_file}, {len(comp['profiles'])} profil, {len(comp['actions'])} eylem tutarlı")
