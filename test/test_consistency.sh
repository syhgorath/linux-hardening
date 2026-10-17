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
mutate "vars'a ssh_port eklendi"   component.yml           's/name: hardening_scan_dir/name: hardening_ssh_port/' "hardening_ssh_port olmamalı"
mutate "vars default rolden farkli (int)"  component.yml    's/default: 300/default: 301/'        "rol varsayılanından"
mutate "vars default rolden farkli (bool)" component.yml    's/default: true/default: false/'     "rol varsayılanından"
mutate "vars min > max"            component.yml           's/min: 30/min: 4000/'                "min > max"
mutate "vars bilinmeyen tur"       component.yml           's/type: list\[cidr\]/type: ip/'      "türü geçersiz"
mutate "vars aciklama yok"         component.yml           '/Lynis raporları/d'                  "description yok"
mutate "vars yinelenen ad"         component.yml           's/name: hardening_scan_dir/name: hardening_rollback_timeout/' "birden çok kez"
mutate "bilinmeyen effect"         component.yml           's/effects: \[\]/effects: [yikar]/'   "effects geçersiz"
mutate "eylemin --tags degeri playbook'ta yok" component.yml 's/--tags disarm/--tags yok-boyle-etiket/' "bir etiket olarak yok"
mutate "bilinmeyen playbook" component.yml 's#playbooks/rollback.yml"$#playbooks/yok.yml"#' "yok"
# shellcheck disable=SC2016  # $TIMEOUT_SECONDS sed kalibinda, kabuk genislemesi istenmiyor
mutate "rollback_status anahtari betikte yok" roles/hardening_rollback/templates/hardening-rollback.sh.j2 's/ timeout_seconds=\$TIMEOUT_SECONDS//' "anahtarlar"
mutate "rollback_status anahtari playbook'ta farkli" playbooks/rollback.yml 's/remaining_seconds=unknown/kalan=unknown/' "anahtarlar"
mutate "component.json eski (yml'den farkli)" component.json 's/"runner": "ansible"/"runner": "script"/' "component.json, component.yml ile aynı değil"
mutate "runner yanlis"             component.yml           's/^runner: ansible/runner: script/'  "runner 'ansible' olmalı"
mutate "confirm eksik"             component.yml           '/confirm: none/d'                    "confirm None geçersiz"
mutate "effects dolu iken confirm none" component.yml      's/confirm: yes-no/confirm: none/'    "en az yes-no"
mutate "warnings eksik"            component.yml           '/Salt okunur: yalnızca/d'            "warnings boş olmayan"
mutate "invoke yer tutucusu dogrulayiciya uymuyor" component.yml 's/{ arg: "--ask-become-pass", required: true/{ arg: "--ask-become-pass", value: "<üretilen envanter>", required: true/' "doğrulayıcısının biçimine"
mutate "invoke.append'de -i"       component.yml           's/arg: "--ask-become-pass"/arg: "-i"/'      "çalıştırıcıya ait bayrak yazılmamalı"
mutate "invoke.append'de --limit"  component.yml           's/arg: "--ask-become-pass"/arg: "--limit"/' "çalıştırıcıya ait bayrak yazılmamalı"
mutate "invoke.append'de -e"       component.yml           's/arg: "--ask-become-pass"/arg: "-e"/'      "çalıştırıcıya ait bayrak yazılmamalı"
mutate "cmd'ye --limit eklendi"    component.yml           's#cmd: "ansible-playbook playbooks/audit.yml"#cmd: "ansible-playbook playbooks/audit.yml --limit=x"#' "çalıştırıcıya ait bayrak içeriyor"
mutate "apply allow_from VPN uyarisi yok" component.yml    '/hardening_ssh_allow_from.a sunucuya BAĞLANABİLECEĞİN/d' "actions.apply: warnings içinde hardening_ssh_allow_from + VPN"
mutate "preview allow_from VPN uyarisi yok" component.yml  '/hardening_ssh_allow_from eksikse bunu/d'             "actions.preview: warnings içinde hardening_ssh_allow_from + VPN"
mutate "README allow_from VPN uyarisi yok" README.md       's/VPN/AG/g'                                         "README.md: hardening_ssh_allow_from"
mutate "HOWTO allow_from VPN uyarisi yok" HOWTO.md         's/VPN/AG/g'                                         "HOWTO.md: hardening_ssh_allow_from"
mutate "SUPPORT.md durumu yanlis"  docs/SUPPORT.md         's/Desteklenir/Bilinmiyor/'           "Desteklenir"
mutate "README EN 'Ne yapmaz' satiri eksik" README.en.md '/^| fail2ban | Limited/d' "TR 20 satır, EN 19 satır"
mutate "README TR 'Ne yapmaz' satiri eksik" README.md '/^| AppArmor profilleri/d' "TR 19 satır, EN 20 satır"
mutate "README EN 'Ne yapmaz' bolumu yok" README.en.md 's/^## What it does not do/## Other/' "'## What it does not do' bölümü yok"

# component.json uretici: gercek depoda guncel; component.yml degisirse --check yakalar
out=$("$PY" -I scripts/make-component-json.py --check 2>&1); rc=$?
expect_eq "component.json guncel (--check)" "0" "$rc"
rm -rf "$TMP/m" && mkdir -p "$TMP/m" && git archive HEAD | tar -x -C "$TMP/m" && cp -R scripts "$TMP/m/"
sed -i.bak 's/^name: "Linux sertleştirme"/name: "Baska ad"/' "$TMP/m/component.yml" && rm -f "$TMP/m/component.yml.bak"
out=$(cd "$TMP/m" && "$PY" -I scripts/make-component-json.py --check 2>&1); rc=$?
expect_eq "component.yml degisince --check yakalar" "1" "$rc"
expect_contains "  mesaj" "$out" "güncel değil"
# json yalnizca stdlib ile okunur ve id/version dosyayla ayni
out=$(python3 -I -c 'import json; d = json.load(open("component.json")); print(d["id"], d["version"])')
expect_eq "component.json stdlib ile okunur (id version)" "linux-hardening $(tr -d '[:space:]' < VERSION)" "$out"

# Gecis: eski bicim (yalnizca ad listesi) kabul edilir
rm -rf "$TMP/m" && mkdir -p "$TMP/m" && git archive HEAD | tar -x -C "$TMP/m" && cp -R scripts "$TMP/m/"
"$PY" - "$TMP/m/component.yml" <<'PYEOF'
import re, sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
a = s.index("vars:\n"); b = s.index("# sshpocket'in yukarıdaki cmd")
s = s[:a] + "vars: [hardening_ssh_allow_from, hardening_scan_dir, hardening_rollback_enabled, hardening_rollback_timeout]\n\n" + s[b:]
open(p, "w", encoding="utf-8").write(s)
PYEOF
(cd "$TMP/m" && "$PY" -I scripts/make-component-json.py >/dev/null)
o=$(cd "$TMP/m" && "$PY" -I scripts/check-consistency.py 2>&1); rc=$?
expect_eq "eski bicim (ad listesi) kabul" "0" "$rc"
finish
