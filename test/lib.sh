#!/usr/bin/env bash
# Test yardımcıları. Her test betiği bunu `. "$(dirname "$0")/lib.sh"` ile alır; 0 ile çıkarsa geçer.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TESTDIR="$ROOT/test"
FAILS=0
PY="${PYTHON:-python3}"
export PY
# ansible-core 2.24'te fact'ler artık üst düzey değişken olarak enjekte edilmez (INJECT_FACTS_AS_VARS=False varsayılan olacak).
# Testler bunu şimdiden zorlar: ansible_distribution gibi üst düzey fact'e dokunan kod burada kırılır (#36).
export ANSIBLE_INJECT_FACT_VARS=False   # ansible-core 2.21 env adı (ini: inject_facts_as_vars)

ok()  { printf '  ok   %s\n' "$1"; }
bad() { printf '  FAIL %s\n' "$1"; FAILS=$((FAILS+1)); }

expect_eq() {        # ad, beklenen, gercek
  if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (beklenen='$2' gercek='$3')"; fi
}
expect_contains() {  # ad, metin, aranan
  if printf '%s' "$2" | grep -qF -- "$3"; then ok "$1"; else bad "$1 ('$3' bulunamadi)"; fi
}
expect_not_contains() {
  if printf '%s' "$2" | grep -qF -- "$3"; then bad "$1 ('$3' bulundu, olmamaliydi)"; else ok "$1"; fi
}
finish() {
  if [ "$FAILS" -eq 0 ]; then echo "TAMAM"; exit 0; else echo "BASARISIZ: $FAILS"; exit 1; fi
}
# ansible-playbook'u test yapilandirmasiyla calistirir (stderr'i birlestirir; <&- ile tty'ye bagimlilik yok).
ap() {
  ANSIBLE_CONFIG="$TESTDIR/ansible-test.cfg" ANSIBLE_ROLES_PATH="$ROOT/roles" \
    ansible-playbook "$@" 2>&1 </dev/null | cat
}
# Gecici dizin (cikista silinir)
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
