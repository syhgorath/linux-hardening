#!/usr/bin/env bash
# Alan anahtarları (hardening_<alan>_enabled): kapatılan rol HİÇ çalışmaz, varsayılanda çalışır; ufw+ssh ikisi de kapalıyken
# erişim korumaları / geri alma güvenlik ağı / yeni bağlantı doğrulaması atlanır, biri açıksa çalışır.
# Yerel hedefte (desteklenmeyen OS) --check ile gerçek playbook koşusu; görev çıktısına bakılır (test_tags_and_hosts.sh ile aynı kurgu).
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"
PYBIN="$(command -v python3)"
HARDEN="$ROOT/playbooks/harden.yml"

dist="$("$PYBIN" -c 'import platform;print(platform.system())')"
if [ "$dist" = "Linux" ]; then vf="ubuntu.yml"; else vf="macosx.yml"; fi
created=0
[ -e "$ROOT/vars/$vf" ] || { echo "hardening_ssh_service: ssh" > "$ROOT/vars/$vf"; created=1; }
trap '[ "$created" = 1 ] && rm -f "$ROOT/vars/$vf"' EXIT
export SSH_CONNECTION='10.1.2.3 5 10.9.9.9 22'

runh() { # etiket, -e ...
  local tag="$1"; shift
  ANSIBLE_CONFIG="$TESTDIR/ansible-test.cfg" ANSIBLE_ROLES_PATH="$ROOT/roles" \
    ansible-playbook -i "$TESTDIR/inventory-local.yml" "$HARDEN" --check --tags "$tag" \
    -e hardening_allow_unsupported=true -e '{"hardening_ssh_allow_from":["10.0.0.0/8"]}' \
    -e ansible_become=false -e "ansible_python_interpreter=$PYBIN" "$@" 2>&1 </dev/null | cat
}
# Bir rolün görevlerinden kaç tanesi ATLANMADI (ok/changed/failed/fatal/included)? 0 = rol hiç çalışmadı.
ran() { # rol, çıktı
  printf '%s\n' "$2" | awk -v role="$1" '
    /^TASK \[/ { cur = ($0 ~ "^TASK \\[" role " : ") ? 1 : 0; next }
    cur && /^(ok|changed|fatal|failed|included):/ { n++ }
    END { print n + 0 }'
}

echo "-- alan anahtarı: varsayılanda rol çalışır, kapalıyken HİÇ çalışmaz"
for pair in base:hardening_base auth:hardening_auth kernel:hardening_kernel apparmor:hardening_apparmor \
            auditd:hardening_auditd fail2ban:hardening_fail2ban aide:hardening_aide ssh:hardening_ssh; do
  tag="${pair%%:*}"; role="${pair##*:}"
  on=$(ran "$role" "$(runh "$tag")")
  off=$(ran "$role" "$(runh "$tag" -e "hardening_${tag}_enabled=false")")
  if [ "$tag" = apparmor ]; then ok "apparmor: yerel hedefte görevleri atlanır (rol when'i aşağıdaki statik denetimde)"
  elif [ "$on" -gt 0 ]; then ok "$tag: varsayılanda rol çalıştı ($on görev)"; else bad "$tag: varsayılanda rol çalışmadı (test anlamsız)"; fi
  expect_eq "$tag: hardening_${tag}_enabled=false -> rol çalışmadı" "0" "$off"
done
# ufw: Proxmox dışı platformda çalışır
on=$(ran hardening_ufw "$(runh ufw)")
off=$(ran hardening_ufw "$(runh ufw -e hardening_ufw_enabled=false)")
[ "$on" -gt 0 ] && ok "ufw: varsayılanda rol çalıştı ($on görev)" || bad "ufw: varsayılanda rol çalışmadı"
expect_eq "ufw: hardening_ufw_enabled=false -> rol çalışmadı" "0" "$off"
# pveproxy: genel platformda rol kendi içinde de atlar; kapalıyken görev çalışmamalı
off=$(ran hardening_pve_pveproxy "$(runh pveproxy -e hardening_pve_pveproxy_enabled=false)")
expect_eq "pveproxy: hardening_pve_pveproxy_enabled=false -> rol çalışmadı" "0" "$off"

echo "-- bir alanı kapatmak başkasını kapatmaz"
out=$(runh kernel,ssh -e hardening_kernel_enabled=false)
expect_eq "kernel kapalı: ssh hâlâ çalışır" "1" "$([ "$(ran hardening_ssh "$out")" -gt 0 ] && echo 1 || echo 0)"
expect_eq "kernel kapalı: kernel çalışmadı" "0" "$(ran hardening_kernel "$out")"

echo "-- ufw ve ssh kapalı: erişim korumaları, geri alma ve doğrulama atlanır"
export HARDEN_EMPTY='{"hardening_ssh_allow_from":[]}'
out=$(runh ufw,ssh -e "$HARDEN_EMPTY" -e hardening_ufw_enabled=false -e hardening_ssh_enabled=false)
expect_not_contains "ikisi kapalı: allow_from şartı atlandı" "$out" "boş veya tanımsız"
out=$(runh ufw,ssh -v -e "$HARDEN_EMPTY" -e hardening_ufw_enabled=false -e hardening_ssh_enabled=false)
expect_contains "ikisi kapalı: rollback/doğrulama alan penceresi nedeniyle atlandı" "$out" '"false_condition": "hardening_run_rollback_window | bool"'
expect_contains "ikisi kapalı: erişim korumaları alan nedeniyle atlandı" "$out" '"false_condition": "hardening_run_access_guards | bool"' 

echo "-- yalnız biri kapalı: korumalar ve geri alma YİNE çalışır"
out=$(runh ufw,ssh -e "$HARDEN_EMPTY" -e hardening_ufw_enabled=false)
expect_contains "ufw kapalı, ssh açık: allow_from şartı çalıştı" "$out" "boş veya tanımsız"
out=$(runh ufw,ssh -e "$HARDEN_EMPTY" -e hardening_ssh_enabled=false)
expect_contains "ssh kapalı, ufw açık: allow_from şartı çalıştı" "$out" "boş veya tanımsız"
out=$(runh ssh -v -e hardening_ufw_enabled=false)
expect_not_contains "ufw kapalı, ssh açık: rollback penceresi atlanmadı" "$out" "hardening_run_rollback_window"
out=$(runh ufw -v -e hardening_ssh_enabled=false)
expect_not_contains "ssh kapalı, ufw açık: rollback penceresi atlanmadı" "$out" "hardening_run_rollback_window"

echo "-- varsayılanlar ve tanım tutarlılığı"
ROOT="$ROOT" "$PY" - <<'PY' || bad "alan anahtarı tanımları"
import os, sys
from pathlib import Path
import yaml
root = Path(os.environ["ROOT"])
comp = {v["name"]: v for v in yaml.safe_load((root / "component.yml").read_text(encoding="utf-8"))["vars"]}
harden = (root / "playbooks/harden.yml").read_text(encoding="utf-8")
areas = {  # alan -> (rol, varsayılan, harden.yml'de when var mı)
    "base": ("hardening_base", True, True), "auth": ("hardening_auth", True, True), "kernel": ("hardening_kernel", True, True),
    "apparmor": ("hardening_apparmor", True, True), "auditd": ("hardening_auditd", True, True), "fail2ban": ("hardening_fail2ban", True, True),
    "aide": ("hardening_aide", True, True), "ufw": ("hardening_ufw", True, True), "ssh": ("hardening_ssh", True, True),
    "pve_pveproxy": ("hardening_pve_pveproxy", True, True),
    "files": ("hardening_files", True, False), "sudo": ("hardening_sudo", True, False),
    "docker": ("hardening_docker", False, False), "rollback": ("hardening_rollback", True, False),
}
bad = []
for a, (role, default, gated) in areas.items():
    n = f"hardening_{a}_enabled"
    c = comp.get(n)
    if not c: bad.append(f"{n}: component.yml'de yok"); continue
    if c.get("type") != "bool" or c.get("default") is not default: bad.append(f"{n}: tür/varsayılan beklenen değil ({c.get('type')}, {c.get('default')})")
    if not c.get("group"): bad.append(f"{n}: group yok")
    d = yaml.safe_load((root / "roles" / role / "defaults/main.yml").read_text(encoding="utf-8")) or {}
    if d.get(n) is not default: bad.append(f"{n}: rol varsayılanı component.yml ile aynı değil")
    if gated and f"{n} | default(true) | bool" not in harden: bad.append(f"{n}: harden.yml'de rol when'i yok")
    if default and "SİLİNMEZ" not in c["description"] and a not in ("files", "sudo", "rollback"):
        bad.append(f"{n}: açıklama silinmeme kuralını söylemiyor")
for a in ("ufw", "ssh", "files", "sudo", "rollback"):
    if comp[f"hardening_{a}_enabled"].get("warn_if") is not False: bad.append(f"hardening_{a}_enabled: warn_if: false olmalı")
if "Alanlar" not in {c.get("group") for c in comp.values()}: bad.append("Alanlar grubu yok")
if bad:
    print("\n".join("  FAIL " + b for b in bad)); sys.exit(1)
print(f"  ok   {len(areas)} alan anahtarı: tür, varsayılan, group, rol varsayılanı, harden.yml when, warn_if")
PY
finish
