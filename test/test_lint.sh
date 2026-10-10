#!/usr/bin/env bash
# Statik denetimler: sözdizimi, yamllint, ansible-lint. Araç yoksa ATLANMAZ, başarısız olur (sessiz geçiş yok).
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"
cd "$ROOT" || exit 1
need() { command -v "$1" >/dev/null 2>&1 || { bad "$1 bulunamadi (requirements-dev.txt kurulmali)"; finish; }; }
need ansible-playbook; need yamllint; need ansible-lint

for pb in harden audit; do
  out=$(ANSIBLE_CONFIG="$ROOT/ansible.cfg" ansible-playbook -i inventory/hosts.example.yml "playbooks/$pb.yml" --syntax-check 2>&1 </dev/null | cat)
  expect_contains "syntax-check playbooks/$pb.yml" "$out" "playbook: playbooks/$pb.yml"
done

if yamllint -c .yamllint --strict roles playbooks inventory vars component.yml test .github 2>&1; then ok "yamllint (strict) temiz"; else bad "yamllint bulgu var"; fi

out=$(ANSIBLE_CONFIG="$ROOT/ansible.cfg" ansible-lint --offline -p 2>&1 </dev/null | cat)
if printf '%s' "$out" | grep -q '^Passed: 0 failure(s), 0 warning(s)'; then ok "ansible-lint: 0 bulgu"; else bad "ansible-lint bulgu var"; printf '%s\n' "$out" | tail -15; fi

# Betik denetimi (scripts/, test/). CI'da (CI=true) arac yoksa BASARISIZ; yerelde yoksa not duser.
if command -v shellcheck >/dev/null 2>&1; then
  if shellcheck -x -s bash scripts/*.sh test/*.sh; then ok "shellcheck temiz"; else bad "shellcheck bulgu var"; fi
elif [ -n "${CI:-}" ]; then
  bad "shellcheck CI'da bulunamadi"
else
  echo "  not  shellcheck kurulu degil; atlandi (CI'da calisir)"
fi
finish
