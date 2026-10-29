#!/usr/bin/env bash
# scripts/*.sh ve test/*.sh çalıştırılabilir olmalı (git'te 100755): `bash` yazmadan doğrudan çalışsın.
# (Yerelde core.fileMode=false ise `git update-index --chmod=+x` gerekir; test dosya iznine bakar, git arşivi izni korur.)
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"
n=0
for f in "$ROOT"/scripts/*.sh "$ROOT"/test/*.sh; do
  [ -e "$f" ] || continue
  n=$((n+1))
  if [ -x "$f" ]; then ok "çalıştırılabilir: ${f#"$ROOT"/}"; else bad "çalıştırılamaz (chmod +x ve git update-index --chmod=+x): ${f#"$ROOT"/}"; fi
done
[ "$n" -gt 0 ] || bad "hiç betik bulunamadı"
finish
