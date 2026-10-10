#!/usr/bin/env bash
# scripts/release.sh: gerçek (tek kullanımlık) bir anahtarla imzalar+doğrular; hatalı durumlarda REDDEDER.
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"
command -v ssh-keygen >/dev/null || { bad "ssh-keygen yok"; finish; }
command -v git >/dev/null || { bad "git yok"; finish; }

KEY="$TMP/anahtar"
ssh-keygen -q -t ed25519 -N "" -C "test-tek-kullanimlik" -f "$KEY"
V=$(tr -d '[:space:]' < "$ROOT/VERSION")

# Calisma agacinin kopyasi (scripts/ git archive'a girmedigi icin tar ile kopyalanir) + gecici git deposu
fresh() {
  rm -rf "$TMP/r" && mkdir -p "$TMP/r"
  (cd "$ROOT" && tar --exclude=.git --exclude=.venv --exclude=dist -cf - .) | tar -xf - -C "$TMP/r"
  (cd "$TMP/r" && git init -q && git add -A \
    && git -c user.email=t@t -c user.name=t commit -qm base \
    && git -c user.email=t@t -c user.name=t tag -a "v$V" -m "test")
}
rel() { # ortam degiskenleriyle calistir; cikis kodu ve cikti
  (cd "$TMP/r" && LH_SIGNING_KEY="${1:-$KEY}" bash scripts/release.sh 2>&1)
}

echo "-- basarili sunum"
fresh
out=$(rel); rc=$?
expect_eq "release.sh basarili (cikis 0)" "0" "$rc"
expect_contains "  paket olustu" "$out" "linux-hardening-$V.tar.gz"
if [ -f "$TMP/r/dist/linux-hardening-$V.tar.gz" ]; then ok "dist/ paket var"; else bad "dist/ paket yok"; fi
if [ -f "$TMP/r/dist/linux-hardening-$V.tar.gz.sig" ]; then ok "dist/ imza var"; else bad "dist/ imza yok"; fi
expect_contains "  signers satiri yazdirildi" "$out" 'namespaces="sshpocket-component"'

echo "-- bagimsiz dogrulama (script'in kendi dogrulamasindan bagimsiz)"
PUB=$(ssh-keygen -y -f "$KEY" | cut -d' ' -f1,2)
echo "sshpocket-component namespaces=\"sshpocket-component\" $PUB" > "$TMP/signers_ok"
ssh-keygen -Y verify -f "$TMP/signers_ok" -I sshpocket-component -n sshpocket-component \
  -s "$TMP/r/dist/linux-hardening-$V.tar.gz.sig" < "$TMP/r/dist/linux-hardening-$V.tar.gz" >/dev/null 2>&1
expect_eq "dogru principal+ad alani: dogrulanir" "0" "$?"
ssh-keygen -Y verify -f "$TMP/signers_ok" -I baska-principal -n sshpocket-component \
  -s "$TMP/r/dist/linux-hardening-$V.tar.gz.sig" < "$TMP/r/dist/linux-hardening-$V.tar.gz" >/dev/null 2>&1
expect_eq "yanlis principal (-I): DOGRULANMAZ" "255" "$?"
ssh-keygen -Y verify -f "$TMP/signers_ok" -I sshpocket-component -n sshpocket-release \
  -s "$TMP/r/dist/linux-hardening-$V.tar.gz.sig" < "$TMP/r/dist/linux-hardening-$V.tar.gz" >/dev/null 2>&1
expect_eq "yanlis ad alani (-n): DOGRULANMAZ" "255" "$?"
# paket bozulursa imza gecmemeli
cp "$TMP/r/dist/linux-hardening-$V.tar.gz" "$TMP/bozuk.tar.gz"; printf 'x' >> "$TMP/bozuk.tar.gz"
ssh-keygen -Y verify -f "$TMP/signers_ok" -I sshpocket-component -n sshpocket-component \
  -s "$TMP/r/dist/linux-hardening-$V.tar.gz.sig" < "$TMP/bozuk.tar.gz" >/dev/null 2>&1
expect_eq "bozulmus paket: DOGRULANMAZ" "255" "$?"

echo "-- paket icerigi"
list=$(tar -tzf "$TMP/r/dist/linux-hardening-$V.tar.gz")
expect_eq "tek kok dizin" "linux-hardening-$V" "$(printf '%s\n' "$list" | cut -d/ -f1 | sort -u)"
expect_contains "  component.yml var" "$list" "linux-hardening-$V/component.yml"
expect_not_contains "  scripts/ yok" "$list" "linux-hardening-$V/scripts/"
expect_not_contains "  test/ yok" "$list" "linux-hardening-$V/test/"

echo "-- reddedilmesi gerekenler"
expect_fail() { # ad, cikti
  if printf '%s' "$2" | grep -q '^HATA:'; then ok "$1 reddedildi"; else bad "$1 REDDEDILMEDI: $2"; fi
}
fresh; echo "kirli" >> "$TMP/r/README.md"
expect_fail "temiz olmayan calisma agaci" "$(rel)"
fresh; (cd "$TMP/r" && echo x > x.txt && git add -A && git -c user.email=t@t -c user.name=t commit -qm sonra)
expect_fail "etiket HEAD'i gostermiyor" "$(rel)"
fresh; (cd "$TMP/r" && git tag -d "v$V" >/dev/null)
expect_fail "etiket yok" "$(rel)"
fresh
expect_fail "imza anahtari yok" "$(rel "$TMP/yok.key")"
fresh; (cd "$TMP/r" && echo "0.1" > VERSION && git add -A && git -c user.email=t@t -c user.name=t commit -qm v && git tag -d "v$V" >/dev/null)
expect_fail "gecersiz VERSION" "$(rel)"
fresh; (cd "$TMP/r" && sed -i.bak "s/^## \[$V\]/## [9.9.9]/" CHANGELOG.md && rm -f CHANGELOG.md.bak && git add -A \
  && git -c user.email=t@t -c user.name=t commit -qm c && git tag -d "v$V" >/dev/null && git -c user.email=t@t -c user.name=t tag -a "v$V" -m t)
expect_fail "CHANGELOG basligi eksik" "$(rel)"

echo "-- python/PyYAML"
fresh
out=$(cd "$TMP/r" && LH_PYTHON=/bin/false LH_SIGNING_KEY="$KEY" bash scripts/release.sh 2>&1)
expect_fail "PyYAML yok (LH_PYTHON bozuk)" "$out"
expect_contains "  mesaj cozumu soyler" "$out" ".venv/bin/pip install --require-hashes"
expect_contains "  mesaj kullanilan python'u soyler" "$out" "/bin/false"
# .venv/bin/python3 varsa kendiliginden kullanilir (gercek python'a yonlendiren, cagrildigini kaydeden sarmalayici)
fresh
mkdir -p "$TMP/r/.venv/bin"
REALPY="$(command -v python3)"
printf '#!/bin/sh\necho used >> "%s/venv_used"\nexec "%s" "$@"\n' "$TMP" "$REALPY" > "$TMP/r/.venv/bin/python3"
chmod +x "$TMP/r/.venv/bin/python3"
out=$(rel); rc=$?
expect_eq ".venv ile basarili" "0" "$rc"
if [ -s "$TMP/venv_used" ]; then ok ".venv/bin/python3 kendiliginden kullanildi"; else bad ".venv/bin/python3 kullanilmadi"; fi
finish
