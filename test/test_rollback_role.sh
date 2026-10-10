#!/usr/bin/env bash
# hardening_rollback rolünün arm görevleri: zaman aşımı doğrulaması, kapalıyken uyarı, --check'te atlanma.
# (Gerçek kurulum kökü ve systemd gerektirir; burada yalnızca doğrulama/atlama davranışı sınanır.)
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"

cat > "$TMP/arm.yml" <<Y
- hosts: localhost
  connection: local
  gather_facts: false
  become: false
  tasks:
    - ansible.builtin.include_role:
        name: hardening_rollback
Y
run() { # ekstra argumanlar
  ap -i "$TESTDIR/inventory-local.yml" "$TMP/arm.yml" "$@"
}
failed_of() { printf '%s' "$1" | grep -oE 'failed=[0-9]+' | head -1; }

echo "-- zaman asimi dogrulamasi (30..3600)"
for bad in 5 29 3601 99999 abc -1; do
  out=$(run -e "hardening_rollback_timeout=$bad")
  expect_eq "timeout=$bad reddedilir" "failed=1" "$(failed_of "$out")"
  expect_contains "  mesaj" "$out" "bir tamsayı olmalı"
done
for good in 30 300 3600; do
  out=$(run -e "hardening_rollback_timeout=$good")
  expect_not_contains "timeout=$good zaman asimi hatasi VERMEZ" "$out" "bir tamsayı olmalı"
done

echo "-- kapaliyken uyari verir ve hicbir sey kurmaz"
out=$(run -e hardening_rollback_enabled=false)
expect_eq "kapali: basarili" "failed=0" "$(failed_of "$out")"
expect_contains "  uyari" "$out" "KAPALI"

echo "-- --check: atlanir (hicbir sey degismez)"
out=$(run --check -e hardening_rollback_timeout=5)
expect_eq "--check: zaman asimi 5 bile hata vermez (arm atlandi)" "failed=0" "$(failed_of "$out")"
finish
