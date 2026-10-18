#!/usr/bin/env bash
# (1) --tags ile çalışırken preflight/korumalar ATLANMAMALI (PR-0e regresyonu)
# (2) hosts deseni: hardening / ubuntu / ikisi / hiçbiri (PR-B)
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"
PYBIN="$(command -v python3)"
HARDEN="$ROOT/playbooks/harden.yml"; AUDIT="$ROOT/playbooks/audit.yml"

# Yerel hedefte (macOS ya da CI'ın Ubuntu 24.04'ü) OS desteklenmez: preflight çalışırsa "Desteklenmeyen sistem" ile DURMALI.
runp() { # playbook tags...
  local pb="$1"; shift
  ANSIBLE_CONFIG="$TESTDIR/ansible-test.cfg" ANSIBLE_ROLES_PATH="$ROOT/roles" \
    ansible-playbook -i "$TESTDIR/inventory-local.yml" "$pb" --check "$@" \
    -e ansible_become=false -e "ansible_python_interpreter=$PYBIN" 2>&1 </dev/null | cat
}
echo "-- etiketli calistirmada preflight atlanmamali"
for tag in kernel ssh ufw base auth fail2ban auditd aide time files sudo docker; do
  out=$(runp "$HARDEN" --tags "$tag")
  expect_contains "harden.yml --tags $tag: preflight durdurdu" "$out" "Desteklenmeyen sistem"
done
out=$(runp "$HARDEN")
expect_contains "harden.yml (etiketsiz): preflight durdurdu" "$out" "Desteklenmeyen sistem"
out=$(runp "$AUDIT" --tags baska)
expect_contains "audit.yml --tags baska: preflight durdurdu" "$out" "Desteklenmeyen sistem"
out=$(runp "$AUDIT")
expect_contains "audit.yml (etiketsiz): preflight durdurdu" "$out" "Desteklenmeyen sistem"

echo "-- desteklenmeyen OS bayragiyla erisim korumalari etiketli calismada da calismali"
# Gecici vars dosyasi: desteklenmeyen OS'te 'Load OS/version vars' adimi icin (sonra silinir)
dist="$("$PYBIN" -c 'import platform;print(platform.system())')"
if [ "$dist" = "Linux" ]; then vf="ubuntu.yml"; else vf="macosx.yml"; fi
cleanup_vars() { rm -f "$ROOT/vars/$vf"; }
trap 'cleanup_vars; rm -rf "$TMP"' EXIT
[ -e "$ROOT/vars/$vf" ] || echo "hardening_ssh_service: ssh" > "$ROOT/vars/$vf"
export SSH_CONNECTION='10.1.2.3 5 10.9.9.9 22'
out=$(runp "$HARDEN" --tags ssh -e hardening_allow_unsupported=true)
expect_contains "--tags ssh: allow_from tanimsiz -> koruma calisti" "$out" "boş veya tanımsız"
out=$(runp "$HARDEN" --tags ufw -e hardening_allow_unsupported=true -e '{"hardening_ssh_allow_from":["192.168.1.0/24"]}')
expect_contains "--tags ufw: kaynak listede degil -> koruma calisti" "$out" "ufw enable bağlantıyı keserdi"
out=$(runp "$HARDEN" --tags kernel -e hardening_allow_unsupported=true -e '{"hardening_ssh_allow_from":[]}')
expect_contains "--tags kernel: kernel rolu gercekten calisti (bos gecis degil)" "$out" "hardening_kernel"
expect_not_contains "--tags kernel: erisim korumasi CALISMAZ (yalniz ufw/ssh icin)" "$out" "boş veya tanımsız"
unset SSH_CONNECTION
echo "-- geri alma guvenlik agi etiketle secilir (arm ufw/ssh ile, kernel ile DEGIL)"
export SSH_CONNECTION='10.1.2.3 5 10.9.9.9 22'
for tag in ufw ssh; do
  out=$(runp "$HARDEN" --tags "$tag" -e hardening_allow_unsupported=true -e '{"hardening_ssh_allow_from":["10.0.0.0/8"]}')
  expect_contains "--tags $tag: hardening_rollback gorevleri secildi" "$out" "TASK [hardening_rollback"
done
out=$(runp "$HARDEN" --tags kernel -e hardening_allow_unsupported=true -e '{"hardening_ssh_allow_from":["10.0.0.0/8"]}')
expect_not_contains "--tags kernel: hardening_rollback SECILMEDI" "$out" "TASK [hardening_rollback"
unset SSH_CONNECTION
cleanup_vars

echo "-- hosts deseni"
mkinv() { cat > "$TMP/$1.yml"; }
mkinv h <<'Y'
all:
  children:
    hardening:
      hosts:
        a: {ansible_host: 1.1.1.1}
Y
mkinv u <<'Y'
all:
  children:
    ubuntu:
      hosts:
        b: {ansible_host: 2.2.2.2}
Y
mkinv hu <<'Y'
all:
  children:
    hardening:
      hosts:
        a: {ansible_host: 1.1.1.1}
    ubuntu:
      hosts:
        a: {ansible_host: 1.1.1.1}
        b: {ansible_host: 2.2.2.2}
Y
mkinv none <<'Y'
all:
  children:
    web:
      hosts:
        c: {ansible_host: 3.3.3.3}
Y
hostlist() { # envanter adi -> ham cikti (uyarilar dahil)
  ANSIBLE_CONFIG="$TESTDIR/ansible-test.cfg" ANSIBLE_ROLES_PATH="$ROOT/roles" \
    ansible-playbook -i "$TMP/$1.yml" "$2" --list-hosts 2>&1 </dev/null | cat
}
count() { hostlist "$1" "$HARDEN" | grep -oE 'hosts \([0-9]+\)' | head -1; }
warns() { hostlist "$1" "$2" | grep -c 'Could not match supplied host pattern'; }
expect_eq "yalniz 'hardening' grubu -> 1" "hosts (1)" "$(count h)"
expect_eq "yalniz eski 'ubuntu' grubu -> 1" "hosts (1)" "$(count u)"
expect_eq "ikisi (kesisen) -> 2 (tekrarsiz)" "hosts (2)" "$(count hu)"
expect_eq "baska grup -> 0" "hosts (0)" "$(count none)"

echo "-- hosts deseni: olmayan grup icin uyari cikmaz (#35)"
for pb in harden audit rollback; do
  P="$ROOT/playbooks/$pb.yml"
  expect_eq "$pb.yml: yalniz 'hardening' -> uyari yok" "0" "$(warns h "$P")"
  expect_eq "$pb.yml: yalniz eski 'ubuntu' -> uyari yok" "0" "$(warns u "$P")"
  expect_eq "$pb.yml: ikisi -> uyari yok" "0" "$(warns hu "$P")"
  expect_eq "$pb.yml: hicbiri -> tek anlamli uyari" "1" "$(warns none "$P")"
done
expect_contains "  hicbiri: uyari 'hardening' der" "$(hostlist none "$HARDEN")" "ignoring: hardening"
finish
