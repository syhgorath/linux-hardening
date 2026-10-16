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

# Sonuc satiri: betik kurulu degilken sabit anahtarlar, YAML ciktisinda TEK (katlanmamis) satir
if [ ! -e /usr/local/sbin/hardening-rollback ]; then
  out=$(ANSIBLE_CALLBACK_RESULT_FORMAT=yaml ap -i "$TESTDIR/inventory-local.yml" "$PB" 2>&1)
  want="SSHPOCKET_RESULT linux-hardening.rollback_status installed=no armed=unknown timer=unknown remaining_seconds=unknown timeout_seconds=unknown"
  if printf '%s\n' "$out" | grep -qxE "[[:space:]]*$want"; then ok "kurulu degil: sonuc satiri tek satir (yaml)"; else bad "sonuc satiri bulunamadi/katlanmis"; fi
else
  ok "betik bu makinede kurulu: kurulu-degil satiri atlandi"
fi
finish
