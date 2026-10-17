#!/usr/bin/env python3
"""component.yml (ve ondan türetilen component.json), VERSION, CHANGELOG, destek matrisi ve rol varsayılanları arasındaki tutarlılığı denetler.

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
import json
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

# 4) vars: gerçekten tanımlı mı; üst veri (tür, varsayılan, aralık) rol varsayılanlarıyla tutarlı mı
VAR_TYPES = {"string", "bool", "int", "path", "cidr", "enum"}
defaults = {}
for f in (ROOT / "roles").glob("*/defaults/main.yml"):
    defaults.update(yaml.safe_load(f.read_text(encoding="utf-8")) or {})
# hardening_scan_dir bir playbook değişkenidir (audit.yml), rol defaults'ında değil
playbook_text = (ROOT / "playbooks/audit.yml").read_text(encoding="utf-8")
seen_vars = set()
for v in comp.get("vars", []):
    meta = v if isinstance(v, dict) else {"name": v}      # eski biçim (yalnızca ad) kabul edilir
    name = meta.get("name")
    if name in seen_vars:
        err(f"component.yml vars: {name} birden çok kez yazılmış")
    seen_vars.add(name)
    if name == "hardening_ssh_port":
        err("component.yml vars içinde hardening_ssh_port olmamalı (kaldırıldı)")
    in_roles = name in defaults
    if not in_roles and name not in playbook_text:
        err(f"component.yml vars: {name} hiçbir rol defaults'ında/audit.yml'de geçmiyor")
    if not isinstance(v, dict):
        continue
    vtype = meta.get("type", "")
    base = vtype[5:-1] if vtype.startswith("list[") and vtype.endswith("]") else vtype
    if base not in VAR_TYPES:
        err(f"component.yml vars: {name} türü geçersiz: {vtype!r}")
    if not str(meta.get("description", "")).strip():
        err(f"component.yml vars: {name} için description yok")
    if "default" in meta:
        if not in_roles:
            err(f"component.yml vars: {name} default taşıyor ama rol defaults'ında yok")
        elif defaults[name] != meta["default"]:
            err(f"component.yml vars: {name} default ({meta['default']!r}) rol varsayılanından ({defaults[name]!r}) farklı")
        if meta.get("required"):
            err(f"component.yml vars: {name} hem required hem default taşıyor")
    elif in_roles and not meta.get("required") and defaults[name] not in ([], "", None):
        err(f"component.yml vars: {name} rol varsayılanı {defaults[name]!r} ama default yazılmamış")
    if meta.get("required") and in_roles and defaults[name] not in ([], "", None):
        err(f"component.yml vars: {name} required ama rol varsayılanı boş değil ({defaults[name]!r})")
    lo, hi = meta.get("min"), meta.get("max")
    if (lo is not None or hi is not None) and vtype != "int":
        err(f"component.yml vars: {name} min/max yalnızca int için")
    if lo is not None and hi is not None and lo > hi:
        err(f"component.yml vars: {name} min > max")
    dv = meta.get("default")
    if isinstance(dv, int) and not isinstance(dv, bool):
        if (lo is not None and dv < lo) or (hi is not None and dv > hi):
            err(f"component.yml vars: {name} default ({dv}) min/max aralığı dışında")
    if "warn_if" in meta and vtype != "bool":
        err(f"component.yml vars: {name} warn_if yalnızca bool için")

# 5) eylemler
for name, act in comp.get("actions", {}).items():
    for k in ("cmd", "effects", "requires_sudo"):
        if k not in act:
            err(f"actions.{name}: '{k}' yok")
    playbook = re.search(r"playbooks/\S+\.yml", act.get("cmd", ""))
    if playbook and not (ROOT / playbook.group(0)).exists():
        err(f"actions.{name}: {playbook.group(0)} yok")
    # cmd'deki `--tags a,b` degerleri o playbook'ta gercekten bir etiket olarak gecmeli
    tag_m = re.search(r"--tags\s+(\S+)", act.get("cmd", ""))
    if tag_m and playbook and (ROOT / playbook.group(0)).exists():
        pb_text = (ROOT / playbook.group(0)).read_text(encoding="utf-8")
        for tag in tag_m.group(1).split(","):
            if not re.search(rf"tags:\s*\[[^\]]*\b{re.escape(tag)}\b", pb_text):
                err(f"actions.{name}: --tags {tag} {playbook.group(0)} icinde bir etiket olarak yok")
    for req in act.get("requires", []):
        if req not in comp["actions"]:
            err(f"actions.{name}.requires: bilinmeyen eylem {req}")
    bad = set(act.get("effects", [])) - {"installs-package", "changes-config"}
    if bad:
        err(f"actions.{name}.effects geçersiz: {sorted(bad)}")

# 5b) paket standardı v1: runner, confirm, warnings (sshpocket asgari kuralı: effects boş değilse en az yes-no)
CONFIRMS = ["none", "yes-no", "type-server-name"]
if comp.get("sshpocket_api") != 1:
    err(f"component.yml sshpocket_api 1 olmalı (paket standardı v1): {comp.get('sshpocket_api')!r}")
if comp.get("runner") != "ansible":
    err(f"component.yml runner 'ansible' olmalı: {comp.get('runner')!r}")
for name, act in comp.get("actions", {}).items():
    confirm = act.get("confirm")
    if confirm not in CONFIRMS:
        err(f"actions.{name}: confirm {confirm!r} geçersiz ({'|'.join(CONFIRMS)})")
    elif act.get("effects") and CONFIRMS.index(confirm) < 1:
        err(f"actions.{name}: effects boş değilken confirm en az yes-no olmalı")
    warns = act.get("warnings")
    if not isinstance(warns, list) or not warns or any(not str(w).strip() for w in warns):
        err(f"actions.{name}: warnings boş olmayan bir metin listesi olmalı")
# -i/--inventory, --limit/-l, -e/--extra-vars çalıştırıcıya aittir (sshpocket ekler): cmd'de ya da invoke.append'de yazılmamalı
RUNNER_FLAG = re.compile(r"^(-i|--inventory|--limit|-l|-e|--extra-vars)(=.*)?$")
for name, act in comp.get("actions", {}).items():
    for tok in str(act.get("cmd", "")).split():
        if RUNNER_FLAG.match(tok):
            err(f"actions.{name}: cmd çalıştırıcıya ait bayrak içeriyor ({tok}); sshpocket -i/--limit/-e'yi kendisi ekler")
for item in comp.get("invoke", {}).get("append", []):
    if RUNNER_FLAG.match(str(item.get("arg", ""))):
        err(f"invoke.append {item.get('arg')}: çalıştırıcıya ait bayrak yazılmamalı (sshpocket ekler, paket standardı §14)")
for item in comp.get("invoke", {}).get("append", []):
    val = str(item.get("value", ""))
    if val and not re.fullmatch(r"<[a-z0-9_ -]{1,40}>|[A-Za-z0-9_./:@=,+-]{1,200}", val):
        err(f"invoke.append {item.get('arg')}: value {val!r} sshpocket doğrulayıcısının biçimine uymuyor")

# 5c) component.json, component.yml'den türetilmiş ve ona eşit olmalı (pakete component.json girer)
cj_path = ROOT / "component.json"
if not cj_path.exists():
    err("component.json yok: python3 -I scripts/make-component-json.py")
else:
    if json.loads(cj_path.read_text(encoding="utf-8")) != comp:
        err("component.json, component.yml ile aynı değil: python3 -I scripts/make-component-json.py")

# 5d) hardening_ssh_allow_from "yalnızca VPN yazma" uyarısı (#39): apply/preview uyarılarında, değişken açıklamasında ve belgelerde olmalı
for name in ("preview", "apply"):
    warns = comp.get("actions", {}).get(name, {}).get("warnings", [])
    if not any("hardening_ssh_allow_from" in str(w) and "VPN" in str(w) for w in warns):
        err(f"actions.{name}: warnings içinde hardening_ssh_allow_from + VPN uyarısı yok (tüm bağlantı ağlarını yaz)")
for v in comp.get("vars", []):
    if isinstance(v, dict) and v.get("name") == "hardening_ssh_allow_from" and "VPN" not in str(v.get("description", "")):
        err("component.yml vars: hardening_ssh_allow_from açıklamasında VPN uyarısı yok")
for doc in ("README.md", "README.en.md", "HOWTO.md", "docs/component-vars.md"):
    if not re.search(r"hardening_ssh_allow_from[\s\S]{0,1500}VPN", (ROOT / doc).read_text(encoding="utf-8")):
        err(f"{doc}: hardening_ssh_allow_from için 'yalnızca VPN yazma' uyarısı yok")

# 6) rollback_status çıktı sözleşmesi: bildirilen anahtarlar betiğin ve playbook'un yazdığı satırla aynı olmalı
outs = comp.get("actions", {}).get("rollback_status", {}).get("outputs")
if outs:
    prefix = outs.get("prefix", "")
    keys = outs.get("keys", [])
    for label, path in (("betik", "roles/hardening_rollback/templates/hardening-rollback.sh.j2"),
                        ("playbook", "playbooks/rollback.yml")):
        text = (ROOT / path).read_text(encoding="utf-8")
        m = re.search(rf'(?:msg: |echo )"{re.escape(prefix)}((?: [a-z_]+=\S+)+)', text)
        if not m:
            err(f"rollback_status outputs.prefix '{prefix}' {path} ({label}) içinde bulunamadı")
            continue
        found = [kv.split("=")[0] for kv in m.group(1).split()]
        if found != keys:
            err(f"rollback_status outputs.keys {keys} ile {label} satırındaki anahtarlar {found} aynı değil")

if errors:
    print("TUTARSIZLIK:")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print(f"OK: component.yml v{version_file}, {len(comp['profiles'])} profil, {len(comp['actions'])} eylem tutarlı")
