#!/usr/bin/env bash
# Repo hijyeni: gizli bilgi, anahtar, gerçek inventory/tarama çıktısı, sürüm biçimi, paket içeriği.
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"
cd "$ROOT" || exit 1
files=$(git ls-files)

echo "-- gizli bilgi / anahtar"
hits=$(git grep -nIE 'BEGIN (OPENSSH|RSA|EC|DSA|PGP) PRIVATE KEY|AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{30,}|xox[baprs]-[A-Za-z0-9-]{10,}' -- . ':!test/test_repo_hygiene.sh' || true)
expect_eq "ozel anahtar/token deseni yok" "" "$hits"
keyfiles=$(printf '%s\n' "$files" | grep -E '(^|/)(id_(rsa|ed25519|ecdsa|dsa)[^/]*|.*\.pem|.*\.key|.*\.p12)$' || true)
expect_eq "anahtar dosyasi takip edilmiyor" "" "$keyfiles"
expect_eq "key/ klasoru takip edilmiyor" "" "$(printf '%s\n' "$files" | grep -E '^key/' || true)"

echo "-- gercek envanter / tarama"
expect_eq "inventory/hosts.yml takip edilmiyor" "" "$(printf '%s\n' "$files" | grep -E '^inventory/hosts\.yml$' || true)"
scans=$(printf '%s\n' "$files" | grep -E '^scans/' | grep -v '^scans/\.gitkeep$' || true)
expect_eq "scans/ icinde .gitkeep disinda dosya yok" "" "$scans"

echo "-- sürüm"
v=$(tr -d '[:space:]' < VERSION)
if printf '%s' "$v" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then ok "VERSION anlamsal surum ($v)"; else bad "VERSION gecersiz: $v"; fi
expect_eq "VERSION == component.yml version" "$v" "$(grep -E '^version:' component.yml | sed -E 's/^version:[[:space:]]*([0-9.]+).*/\1/')"

echo "-- paket icerigi (git archive)"
tar_list=$(git archive --format=tar --prefix=linux-hardening-"$v"/ HEAD | tar -t)
for must in VERSION component.yml CHANGELOG.md LICENSE requirements.txt requirements.in playbooks/harden.yml playbooks/audit.yml roles/hardening_ssh/tasks/main.yml docs/SUPPORT.md; do
  if printf '%s\n' "$tar_list" | grep -qx "linux-hardening-$v/$must"; then ok "pakette var: $must"; else bad "pakette EKSIK: $must"; fi
done
for mustnot in '\.gitattributes' '\.gitignore' '\.ansible-lint' '\.github/' 'scripts/' 'scans/' 'test/' 'docs/RELEASING\.md' 'requirements-dev'; do
  if printf '%s\n' "$tar_list" | grep -qE "^linux-hardening-$v/$mustnot"; then bad "pakette OLMAMALI: $mustnot"; else ok "pakette yok: $mustnot"; fi
done
roots=$(printf '%s\n' "$tar_list" | cut -d/ -f1 | sort -u)
expect_eq "tek kok dizin" "linux-hardening-$v" "$roots"
finish
