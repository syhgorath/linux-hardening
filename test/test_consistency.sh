#!/usr/bin/env bash
# scripts/check-consistency.py: gerçek depoda OK vermeli; kasıtlı bozulmaları YAKALAMALI.
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"
cd "$ROOT" || exit 1
out=$("$PY" -I scripts/check-consistency.py 2>&1); rc=$?
expect_eq "gercek depo tutarli (cikis 0)" "0" "$rc"
expect_contains "  mesaj" "$out" "OK:"

# Kasitli bozmalar: depoyu gecici bir kopyada boz
mutate() { # ad, dosya, sed-ifadesi, beklenen-metin
  rm -rf "$TMP/m" && mkdir -p "$TMP/m" && git archive HEAD | tar -x -C "$TMP/m"
  cp -R scripts "$TMP/m/" 2>/dev/null
  sed -i.bak "$3" "$TMP/m/$2" && rm -f "$TMP/m/$2.bak"
  local o rc; o=$(cd "$TMP/m" && "$PY" -I scripts/check-consistency.py 2>&1); rc=$?
  expect_eq "bozma yakalandi: $1" "1" "$rc"
  expect_contains "  beklenen mesaj: $1" "$o" "$4"
}
mutate "VERSION farkli"            VERSION                 's/.*/9.9.9/'                         "aynı değil"
mutate "profil surumu yanlis"      component.yml           's/ubuntu-26.04/ubuntu-24.04/'        "hardening_supported_os"
mutate "vars'a ssh_port eklendi"   component.yml           's/^vars: \[.*\]/vars: [hardening_ssh_port]/' "hardening_ssh_port olmamalı"
mutate "bilinmeyen effect"         component.yml           's/effects: \[\]/effects: [yikar]/'   "effects geçersiz"
mutate "SUPPORT.md durumu yanlis"  docs/SUPPORT.md         's/Desteklenir/Bilinmiyor/'           "Desteklenir"
finish
