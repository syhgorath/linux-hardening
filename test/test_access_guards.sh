#!/usr/bin/env bash
# Erişim kaybı korumaları: allow_from boş/geçersiz/kaynak dışı, SSH_CONNECTION yok, root.
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"
PYBIN="$(command -v python3)"
mkdir -p "$TMP/fakebin"; printf '#!/bin/sh\necho root\n' > "$TMP/fakebin/id"; chmod +x "$TMP/fakebin/id"

# run <ssh_connection|-> <allow_from_json|-> [fake_id]  -> cikti
run() {
  local conn="$1" allow="$2" fake="${3:-}" args=(-e "ansible_python_interpreter=$PYBIN")
  [ "$allow" != "-" ] && args+=(-e "{\"hardening_ssh_allow_from\": $allow}")
  local envs=()
  if [ "$conn" = "-" ]; then envs=(-u SSH_CONNECTION); else envs=("SSH_CONNECTION=$conn"); fi
  [ -n "$fake" ] && envs+=("PATH=$TMP/fakebin:$PATH")
  env "${envs[@]}" ANSIBLE_CONFIG="$TESTDIR/ansible-test.cfg" ANSIBLE_ROLES_PATH="$ROOT/roles" \
    ansible-playbook -i "$TESTDIR/inventory-local.yml" "$TESTDIR/access_test.yml" "${args[@]}" 2>&1 </dev/null | cat
}
failed_of() { printf '%s' "$1" | grep -oE 'failed=[0-9]+' | head -1; }

CONN='10.1.2.3 5555 10.9.9.9 22'
out=$(run "$CONN" '[]');                          expect_eq "allow_from=[] durur" "failed=1" "$(failed_of "$out")"; expect_contains "  mesaj" "$out" "boş veya tanımsız"
out=$(run "$CONN" -);                              expect_eq "allow_from tanimsiz durur" "failed=1" "$(failed_of "$out")"
out=$(run "$CONN" '["10.0.0.0/8"]');               expect_eq "IPv4 listede gecer" "failed=0" "$(failed_of "$out")"
out=$(run "$CONN" '["192.168.1.0/24"]');           expect_eq "IPv4 listede degil durur" "failed=1" "$(failed_of "$out")"; expect_contains "  mesaj kaynak adres" "$out" "10.1.2.3"
out=$(run "$CONN" '["abc"]');                      expect_eq "gecersiz CIDR durur" "failed=1" "$(failed_of "$out")"; expect_contains "  mesaj gecersiz" "$out" "geçersiz değer"
out=$(run "-" '["10.0.0.0/8"]');                   expect_eq "SSH_CONNECTION yok durur" "failed=1" "$(failed_of "$out")"; expect_contains "  mesaj" "$out" "SSH_CONNECTION okunamadı"
out=$(run "fd00::5 5555 fd00::9 22" '["fd00::/8"]'); expect_eq "IPv6 listede gecer" "failed=0" "$(failed_of "$out")"
out=$(run "fd00::5 5555 fd00::9 22" '["10.0.0.0/8"]'); expect_eq "IPv6 kaynak, IPv4 liste durur" "failed=1" "$(failed_of "$out")"
out=$(run "$CONN" '["10.0.0.0/8"]' fake);          expect_eq "kullanici root durur" "failed=1" "$(failed_of "$out")"; expect_contains "  mesaj" "$out" "root olarak bağlanıyor"
out=$(run "$CONN" '["10.1.2.3/32"]');              expect_eq "/32 tam eslesme gecer" "failed=0" "$(failed_of "$out")"
out=$(run "$CONN" '["10.1.2.4/32","10.1.2.3/32"]'); expect_eq "coklu liste gecer" "failed=0" "$(failed_of "$out")"
finish
