#!/usr/bin/env bash
# scripts/release-publish.sh: kontroller, etiket+push (yerel bare origin), release.sh (gerçek imza, tek kullanımlık anahtar), sahte `gh` ile Release ve özet doğrulaması.
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"
command -v ssh-keygen >/dev/null || { bad "ssh-keygen yok"; finish; }
command -v git >/dev/null || { bad "git yok"; finish; }

KEY="$TMP/anahtar"
ssh-keygen -q -t ed25519 -N "" -C "test-tek-kullanimlik" -f "$KEY"
V=$(tr -d '[:space:]' < "$ROOT/VERSION")
BIN="$TMP/bin"; mkdir -p "$BIN"
# Sahte gh: cagrilari gh.log'a yazar; davranisi FAKE_* ortam degiskenleri belirler
cat > "$BIN/gh" <<'GH'
#!/usr/bin/env bash
echo "gh $*" >> "$FAKE_GH_LOG"
case "$1 $2" in
  "repo view") echo "sahip/depo" ;;
  "release view") [ "${FAKE_RELEASE_EXISTS:-0}" = 1 ] && exit 0 || exit 1 ;;
  "run list") echo "${FAKE_CI:-completed success $(git rev-parse HEAD)}" ;;
  "release create") shift 2; echo "$@" > "$FAKE_GH_CREATE"
     while [ $# -gt 0 ]; do [ "$1" = "--notes-file" ] && cp "$2" "$FAKE_GH_NOTES"; shift; done ;;
  "api repos/sahip/depo/releases/tags/"*)
     for f in $(cat "$FAKE_GH_CREATE"); do
       case "$f" in dist/*) n=$(basename "$f"); if command -v sha256sum >/dev/null 2>&1; then s=$(sha256sum "$f" | cut -d' ' -f1); else s=$(shasum -a 256 "$f" | cut -d' ' -f1); fi
         [ "${FAKE_DIGEST:-iyi}" = "kotu" ] && s="0000000000000000000000000000000000000000000000000000000000000000"
         echo "$n sha256:$s" ;; esac
     done ;;
  *) echo "bilinmeyen gh cagrisi: $*" >&2; exit 9 ;;
esac
GH
chmod +x "$BIN/gh"
# CI ortaminda global git kimligi yoktur: etiket (annotated) ve commit icin test kimligi
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export FAKE_GH_LOG="$TMP/gh.log" FAKE_GH_CREATE="$TMP/gh.create" FAKE_GH_NOTES="$TMP/gh.notes"

fresh() { # temiz depo + yerel bare origin (main, takip ediyor)
  rm -rf "$TMP/r" "$TMP/o.git" "$TMP/gh.log" "$TMP/gh.create" "$TMP/gh.notes" && mkdir -p "$TMP/r"
  git init -q --bare "$TMP/o.git"
  (cd "$ROOT" && tar --exclude=.git --exclude=.venv --exclude=dist -cf - .) | tar -xf - -C "$TMP/r"
  (cd "$TMP/r" && git init -q -b main && git add -A \
    && git -c user.email=t@t -c user.name=t commit -qm base \
    && git remote add origin "$TMP/o.git" && git push -q -u origin main)
}
pub() { (cd "$TMP/r" && PATH="$BIN:$PATH" LH_SIGNING_KEY="$KEY" bash scripts/release-publish.sh "$@" 2>&1); }
expect_fail() { if printf '%s' "$2" | grep -q '^HATA:'; then ok "$1 reddedildi"; else bad "$1 REDDEDILMEDI: $2"; fi; }

echo "-- dry-run: ne yapacagini gosterir, HICBIR SEY yapmaz"
fresh; out=$(pub --dry-run); rc=$?
expect_eq "dry-run cikis 0" "0" "$rc"
expect_contains "  plan: etiket" "$out" "git tag -a v$V"
expect_contains "  plan: gh release create" "$out" "gh release create v$V"
expect_contains "  [dry-run] hicbir sey yapilmadi" "$out" "[dry-run] hiçbir şey yapılmadı"
if (cd "$TMP/r" && git rev-parse -q --verify "refs/tags/v$V" >/dev/null); then bad "dry-run etiket OLUSTURDU"; else ok "dry-run etiket olusturmadi"; fi
if git --git-dir="$TMP/o.git" rev-parse -q --verify "refs/tags/v$V" >/dev/null; then bad "dry-run etiketi ITTI"; else ok "dry-run etiketi itmedi"; fi
if [ -f "$TMP/gh.create" ]; then bad "dry-run Release ACTI"; else ok "dry-run Release acmadi"; fi
if [ -d "$TMP/r/dist" ]; then bad "dry-run paket URETTI"; else ok "dry-run paket uretmedi"; fi

echo "-- reddedilmesi gerekenler"
fresh; echo "kirli" >> "$TMP/r/README.md"; expect_fail "temiz olmayan calisma agaci" "$(pub --dry-run)"
fresh; (cd "$TMP/r" && git checkout -q -b baska); expect_fail "main disinda bir dal" "$(pub --dry-run)"
fresh; (cd "$TMP/r" && echo x > x.txt && git add -A && git -c user.email=t@t -c user.name=t commit -qm yerel); expect_fail "HEAD origin/main ile ayni degil" "$(pub --dry-run)"
fresh; sed -i.bak "s/^## \[$V\]/## [0.0.0]/" "$TMP/r/CHANGELOG.md" && rm -f "$TMP/r/CHANGELOG.md.bak"; (cd "$TMP/r" && git -c user.email=t@t -c user.name=t commit -qam x && git push -q origin main); expect_fail "CHANGELOG basligi yok" "$(pub --dry-run)"
fresh; export FAKE_RELEASE_EXISTS=1; expect_fail "Release zaten var" "$(pub --dry-run)"; unset FAKE_RELEASE_EXISTS
fresh; export FAKE_CI="completed failure abc"; expect_fail "main CI yesil degil" "$(pub --dry-run)"; unset FAKE_CI
fresh; export FAKE_CI="in_progress  abc"; expect_fail "main CI bitmemis" "$(pub --dry-run)"; unset FAKE_CI
fresh; out=$(FAKE_CI="completed failure abc" pub --dry-run --no-ci-check); expect_contains "--no-ci-check CI kontrolunu atlar" "$out" "[dry-run]"
fresh; expect_fail "bilinmeyen bagimsiz degisken" "$(pub --bilinmeyen)"
fresh; (cd "$TMP/r" && git tag -a "v$V" -m x && git -c user.email=t@t -c user.name=t commit -q --allow-empty -m yeni && git push -q origin main); expect_fail "yerel etiket baska commit'i gosteriyor" "$(pub --dry-run)"

fresh; out=$(cd "$TMP/r" && PATH="$BIN:$PATH" LH_PYTHON=/bin/false LH_SIGNING_KEY="$KEY" bash scripts/release-publish.sh --yes 2>&1); rc=$?
if [ "$rc" != "0" ] && printf '%s' "$out" | grep -q "check-consistency"; then ok "tutarlilik denetimi ETIKETTEN ONCE (Python/PyYAML yoksa durur)"; else bad "tutarlilik denetimi atlandi (rc=$rc): $out"; fi
if git --git-dir="$TMP/o.git" rev-parse -q --verify "refs/tags/v$V" >/dev/null; then bad "tutarlilik basarisizken etiket itildi"; else ok "tutarlilik basarisizken etiket itilmedi"; fi

echo "-- tam kosu (--yes): etiket+push, gercek imza, Release, ozet dogrulama"
fresh; out=$(pub --yes); rc=$?
expect_eq "tam kosu cikis 0" "0" "$rc"
if git --git-dir="$TMP/o.git" rev-parse -q --verify "refs/tags/v$V" >/dev/null; then ok "etiket origin'e itildi"; else bad "etiket itilmedi: $out"; fi
if [ -f "$TMP/r/dist/linux-hardening-$V.tar.gz.sig" ]; then ok "paket ve imza uretildi (gercek release.sh)"; else bad "imza yok: $out"; fi
create=$(cat "$TMP/gh.create" 2>/dev/null)
expect_contains "  Release: paket yuklendi" "$create" "dist/linux-hardening-$V.tar.gz"
expect_contains "  Release: imza yuklendi" "$create" "dist/linux-hardening-$V.tar.gz.sig"
expect_contains "  Release: --verify-tag" "$create" "--verify-tag"
notes=$(cat "$TMP/gh.notes" 2>/dev/null)
expect_contains "  Release notlari CHANGELOG'daki surum bolumunden" "$notes" "$(awk -v v="$V" '$0 ~ "^## \\[" v "\\]" {f=1; next} f && NF {print; exit}' "$ROOT/CHANGELOG.md" | cut -c1-40)"
expect_not_contains "  Release notlari bir sonraki surum basligini icermez" "$notes" "## ["
expect_contains "  ozet dogrulandi mesaji" "$out" "yüklenen dosyaların özeti yerelle aynı"
expect_contains "  components.lock bilgisi: SHA-256" "$out" "SHA-256"
expect_contains "  components.lock bilgisi: imzalayici satiri" "$out" 'namespaces="sshpocket-component"'
expect_not_contains "  sshpocket reposuna dokunmaz (components.lock yazilmaz)" "$out" "components.lock'a yazıldı"
echo "-- ozet UYUSMAZSA durur"
fresh; export FAKE_DIGEST=kotu; out=$(pub --yes); rc=$?; unset FAKE_DIGEST
if [ "$rc" != "0" ] && printf '%s' "$out" | grep -q "özeti uyuşmuyor"; then ok "uyusmayan ozet reddedildi"; else bad "uyusmayan ozet KABUL EDILDI (rc=$rc): $out"; fi
echo "-- onay sorulmadan (--yes olmadan, stdin yok) iptal"
fresh; out=$(pub </dev/null); rc=$?
if [ "$rc" != "0" ]; then ok "onay yok -> iptal"; else bad "onaysiz devam etti"; fi
if git --git-dir="$TMP/o.git" rev-parse -q --verify "refs/tags/v$V" >/dev/null; then bad "onaysiz etiket itildi"; else ok "onaysiz etiket itilmedi"; fi
finish
