#!/usr/bin/env bash
# playbooks/rollback.yml: varsayılan koşu YALNIZCA status; disarm/now açıkça --tags ile istenmeden ÇALIŞMAZ.
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"
PB="$ROOT/playbooks/rollback.yml"

list() { # ek argumanlar -> secilen gorev adlari
  ap -i "$TESTDIR/inventory-local.yml" "$PB" --list-tasks "$@" | grep -E '^\s+(Check|Say|Read|Show|Disarm|Restore)' | sed -E 's/^\s+//; s/\s+TAGS:.*$//'
}
all_default=$(list)
expect_contains "varsayilan: status okunur" "$all_default" "Read status"
expect_contains "varsayilan: durum gosterilir" "$all_default" "Show status"
expect_not_contains "varsayilan: DISARM CALISMAZ" "$all_default" "Disarm"
expect_not_contains "varsayilan: RESTORE CALISMAZ" "$all_default" "Restore previous state"

dis=$(list --tags disarm)
expect_contains "--tags disarm: disarm calisir" "$dis" "Disarm"
expect_not_contains "--tags disarm: restore CALISMAZ" "$dis" "Restore previous state"

now=$(list --tags now)
expect_contains "--tags now: restore calisir" "$now" "Restore previous state"
expect_not_contains "--tags now: disarm CALISMAZ" "$now" "Disarm"

st=$(list --tags status)
expect_contains "--tags status: status" "$st" "Read status"

# Koruma/preflight YOK (kontrol kaybindan sonra da calisabilmeli)
text=$(cat "$PB")
expect_not_contains "preflight gerektirmez" "$text" "hardening_preflight"
finish
