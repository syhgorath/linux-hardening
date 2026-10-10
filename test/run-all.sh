#!/usr/bin/env bash
# Tüm testleri çalıştırır. Gereksinim: PATH'te ansible-playbook, yamllint (opsiyonel), python3 + PyYAML.
# Kullanım: test/run-all.sh [desen]     örn: test/run-all.sh summary
cd "$(dirname "$0")/.." || exit 1
pattern="${1:-}"
total=0; failed=0; failed_names=()
for t in test/test_*.sh test/test_*.py; do
  [ -e "$t" ] || continue
  case "$t" in *"$pattern"*) ;; *) continue ;; esac
  total=$((total+1))
  echo "=== $t"
  case "$t" in
    *.py) "${PYTHON:-python3}" -I "$t" ;;
    *)    bash "$t" ;;
  esac
  rc=$?
  if [ $rc -ne 0 ]; then failed=$((failed+1)); failed_names+=("$t"); fi
done
echo
echo "Toplam: $total test dosyası, başarısız: $failed"
for n in "${failed_names[@]}"; do echo "  - $n"; done
[ "$failed" -eq 0 ]
