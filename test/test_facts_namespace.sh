#!/usr/bin/env bash
# ansible-core 2.24'te fact'ler üst düzey değişken olarak enjekte edilmez (INJECT_FACTS_AS_VARS=False olur).
# Bu test lib.sh'in zorladığı INJECT_FACTS_AS_VARS=False altında OS denetiminin ve getent kullanımının çalıştığını,
# ve kodda üst düzey fact adı kalmadığını doğrular (#36).
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"
PYBIN="$(command -v python3)"

run_pre() { # ansible_facts JSON
  ANSIBLE_CONFIG="$TESTDIR/ansible-test.cfg" ANSIBLE_ROLES_PATH="$ROOT/roles" \
    ansible-playbook -i "$TESTDIR/inventory-local.yml" "$TESTDIR/preflight_test.yml" \
    -e "ansible_python_interpreter=$PYBIN" -e "{\"ansible_facts\": $1}" 2>&1 </dev/null | cat
}
failed_of() { printf '%s' "$1" | grep -oE 'failed=[0-9]+' | head -1; }

echo "-- preflight: ansible_facts ile OS denetimi"
out=$(run_pre '{"distribution":"Ubuntu","distribution_version":"26.04"}')
expect_eq "Ubuntu 26.04 gecer" "failed=0" "$(failed_of "$out")"
expect_not_contains "  tanimsiz degisken yok" "$out" "undefined"
out=$(run_pre '{"distribution":"Ubuntu","distribution_version":"24.04"}')
expect_eq "Ubuntu 24.04 durur" "failed=1" "$(failed_of "$out")"
expect_contains "  mesaj sistemi soyler" "$out" "Desteklenmeyen sistem: Ubuntu 24.04"
out=$(run_pre '{"distribution":"Debian","distribution_version":"12"}')
expect_eq "Debian durur" "failed=1" "$(failed_of "$out")"
expect_contains "  mesaj" "$out" "Desteklenmeyen sistem: Debian 12"

echo "-- hardening_ssh: getent sonucu ansible_facts altindan okunur"
cat > "$TMP/ssh_role.yml" <<'Y'
- hosts: localhost
  connection: local
  gather_facts: false
  become: false
  tasks:
    - ansible.builtin.include_role:
        name: hardening_ssh
Y
out=$(ANSIBLE_CONFIG="$TESTDIR/ansible-test.cfg" ANSIBLE_ROLES_PATH="$ROOT/roles" \
  ansible-playbook -i "$TESTDIR/inventory-local.yml" "$TMP/ssh_role.yml" --check \
  -e "ansible_python_interpreter=$PYBIN" -e '{"hardening_ssh_allow_from":["10.0.0.0/8"]}' 2>&1 </dev/null | cat)
expect_not_contains "  getent_passwd tanimsiz degil" "$out" "is undefined"
expect_contains "  getent gorevi calisti" "$out" "Login user's real home directory"

echo "-- statik bekci: kodda ust duzey fact adi kalmamali"
# Fact adlari ansible_facts['...'] ile okunur. Yasak: ansible_<fact> ve getent_passwd (ansible_facts altindaki hali haric).
bad_pat='\bansible_(distribution[a-z_]*|os_family|hostname|fqdn|nodename|default_ipv[46]|pkg_mgr|service_mgr|architecture|machine|kernel[a-z_]*|virtualization_[a-z]+|memtotal_mb|processor[a-z_]*|date_time|env|mounts|user_id|user_uid|selinux|apparmor|lsb|system|all_ipv[46]_addresses|interfaces|dns)\b'
hits=$(grep -rnE "$bad_pat" "$ROOT/roles" "$ROOT/playbooks" "$ROOT/vars" "$ROOT/inventory" 2>/dev/null | grep -v "ansible_facts" || true)
if [ -z "$hits" ]; then ok "ust duzey fact adi yok (roles, playbooks, vars, inventory)"; else bad "ust duzey fact adi var:"; printf '%s\n' "$hits"; fi
hits=$(grep -rnE '(^|[^_.[:alnum:]'"'"'])getent_passwd' "$ROOT/roles" "$ROOT/playbooks" | grep -v "ansible_facts\['getent_passwd'\]" | grep -v "getent_passwd)" || true)
if [ -z "$hits" ]; then ok "getent_passwd yalnizca ansible_facts altindan"; else bad "ust duzey getent_passwd:"; printf '%s\n' "$hits"; fi
finish
