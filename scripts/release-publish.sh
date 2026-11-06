#!/usr/bin/env bash
# release-publish.sh - release.sh'in ÖNCESİNİ ve SONRASINI yapar (bakımcı aracı, yerelde çalışır): kontroller, etiket, paket+imza (release.sh), GitHub Release, yüklenen
# dosyaların özet doğrulaması ve components.lock'a yazılacak bilgilerin yazdırılması.
#
#   LH_SIGNING_KEY=~/.ssh/<anahtar> scripts/release-publish.sh --dry-run     # ne yapacağını gösterir, HİÇBİR ŞEY yapmaz
#   LH_SIGNING_KEY=~/.ssh/<anahtar> scripts/release-publish.sh                # onay ister, sonra etiketler, imzalar, Release açar
#   --yes (onay sorma), --no-ci-check (main CI kontrolünü atla: önerilmez), --no-index (paket indeksi adımını atla)
#
# Son adım (6) imzalı paket indeksidir (syhgorath/sshpocket-index): Release + özet doğrulaması geçtikten sonra `index-publish.sh` çağrılır
# (konum: $SSHPOCKET_INDEX_DIR, varsayılan ~/Developer/sshpocket-index). Baştaki y/N yayın onayı olduğundan indeks betiğine `--yes` geçirilir (ikinci onay etkileşimsiz pencerede düşerdi). İndeks hatası yayımlanmış Release'i geçersiz kılmaz; `index-publish.sh` tek başına yeniden çalıştırılabilir.
# İndeks imza anahtarı: INDEX_SIGNING_KEY, yoksa PAKET_SIGNING_KEY, yoksa LH_SIGNING_KEY (yalnızca yol aktarılır, anahtar okunmaz).
#
# Özel imza anahtarı ASLA repoya, CI'a veya sohbete konmaz; yalnızca release.sh'e LH_SIGNING_KEY ile aktarılır. components.lock sshpocket reposundadır: bu betik ona DOKUNMAZ,
# yalnızca yazılacak SHA-256 ve imzalayıcı satırını yazdırır. Ayrıntı: docs/RELEASING.md
set -euo pipefail
cd "$(dirname "$0")/.."

die() { echo "HATA: $*" >&2; exit 1; }
DRY=0; YES=0; NOCI=0; NOINDEX=0
for a in "$@"; do
    case "$a" in
        --dry-run) DRY=1 ;;
        --yes) YES=1 ;;
        --no-ci-check) NOCI=1 ;;
        --no-index) NOINDEX=1 ;;
        -h|--help) sed -n 2,10p "$0"; exit 0 ;;
        *) die "bilinmeyen bağımsız değişken: $a (kullanım: --dry-run, --yes, --no-ci-check, --no-index)" ;;
    esac
done
command -v git >/dev/null || die "git yok"
command -v gh >/dev/null || die "gh (GitHub CLI) yok"

VERSION=$(tr -d '[:space:]' < VERSION)
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "VERSION geçersiz: '$VERSION'"
TAG="v$VERSION"
ARCHIVE="dist/linux-hardening-$VERSION.tar.gz"
PKG_ID="linux-hardening"
INDEX_PUBLISH="${SSHPOCKET_INDEX_DIR:-$HOME/Developer/sshpocket-index}/scripts/index-publish.sh"
SUMOF() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || die "main dalında değilsiniz"
[ -z "$(git status --porcelain)" ] || die "çalışma alanı temiz değil (commit edilmemiş değişiklik var)"
git fetch -q origin main --tags || die "git fetch başarısız"
HEAD_SHA=$(git rev-parse HEAD)
[ "$HEAD_SHA" = "$(git rev-parse origin/main)" ] || die "HEAD origin/main ile aynı değil (önce: git pull)"
grep -q "^## \[$VERSION\]" CHANGELOG.md || die "CHANGELOG.md içinde [$VERSION] başlığı yok"

if gh release view "$TAG" >/dev/null 2>&1; then die "GitHub Release $TAG zaten var"; fi
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    [ "$(git rev-list -n1 "$TAG")" = "$HEAD_SHA" ] || die "yerel $TAG etiketi şu anki commit'i göstermiyor"
fi
if git ls-remote --exit-code --tags origin "refs/tags/$TAG" >/dev/null 2>&1; then
    [ "$(git ls-remote origin "refs/tags/$TAG^{}" | cut -f1)" = "$HEAD_SHA" ] || die "uzaktaki $TAG etiketi şu anki commit'i göstermiyor"
fi

# İndeks betiği yoksa Release'ten SONRA öğrenmek yerine etiketten ÖNCE dur (indekssiz yayın için --no-index)
if [ "$NOINDEX" = 0 ] && [ ! -x "$INDEX_PUBLISH" ]; then
    die "index-publish.sh bulunamadı ($INDEX_PUBLISH): SSHPOCKET_INDEX_DIR ayarlayın ya da indekssiz yayın için --no-index kullanın (hiçbir şey yapılmadı)"
fi

# release.sh'in tutarlılık denetimini ETİKET ATILMADAN ÖNCE de yap: etiket itildikten sonra release.sh başarısız olursa etiket Release'siz kalırdı
if [ -n "${LH_PYTHON:-}" ]; then PY="$LH_PYTHON"; elif [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
"$PY" -I scripts/check-consistency.py >/dev/null 2>&1 || die "scripts/check-consistency.py başarısız (PyYAML'lı bir Python gerekir: LH_PYTHON ya da .venv); bulguyu görmek için: $PY -I scripts/check-consistency.py"
"$PY" -I scripts/make-component-json.py --check >/dev/null 2>&1 || die "component.json güncel değil: $PY -I scripts/make-component-json.py ile üretip commit edin"

if [ "$NOCI" = 0 ]; then
    CI=$(gh run list --branch main --limit 1 --json status,conclusion,headSha --jq '.[0] | "\(.status) \(.conclusion) \(.headSha)"') || die "gh run list başarısız"
    [ "$CI" = "completed success $HEAD_SHA" ] || die "main CI yeşil değil ya da şu anki commit'e ait değil: '$CI' (beklenen: completed success $HEAD_SHA)"
fi

# Sürüm notları: CHANGELOG.md'deki [VERSION] bölümü
NOTES=$(mktemp)
trap 'rm -f "$NOTES"' EXIT
awk -v v="$VERSION" '$0 ~ "^## \\[" v "\\]" {f=1; next} /^## \[/ {f=0} f' CHANGELOG.md | sed '/./,$!d' > "$NOTES"
[ -s "$NOTES" ] || die "CHANGELOG.md [$VERSION] bölümü boş"

echo "Sürüm: $TAG (commit ${HEAD_SHA:0:7})"
echo "Yapılacaklar:"
echo "  1) git tag -a $TAG -m \"linux-hardening $VERSION\" && git push origin $TAG"
echo "  2) scripts/release.sh  (paket + imza + kendi doğrulaması)"
echo "  3) gh release create $TAG $ARCHIVE $ARCHIVE.sig --title $TAG --notes-file <CHANGELOG [$VERSION] bölümü, $(wc -l < "$NOTES" | tr -d ' ') satır>"
echo "  4) yüklenen dosyaların SHA-256 özetini yerel dosyalarla karşılaştır"
echo "  5) components.lock için SHA-256 ve imzalayıcı satırını yazdır (bilgi; normal sürümde GEREKMEZ, indeks halleder; sshpocket reposuna DOKUNULMAZ)"
if [ "$NOINDEX" = 0 ]; then
    echo "  6) indeks: $INDEX_PUBLISH $PKG_ID $VERSION <sahip/depo> --archive $ARCHIVE --sig $ARCHIVE.sig --yes  (yerel commit, push sizde)"
else
    echo "  6) indeks: ATLANACAK (--no-index)"
fi
if [ "$DRY" = 1 ]; then
    if [ "$NOINDEX" = 0 ]; then
        # İndeks betiğinin kendi --dry-run'ı: yazmaz. Paket henüz üretilmediği için arşiv/imza verilmez. Hata deneme çalıştırmasını bozmaz.
        echo "  -- indeks betiği --dry-run:"
        "$INDEX_PUBLISH" --dry-run "$PKG_ID" "$VERSION" "$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || echo '<sahip/depo>')" 2>&1 | sed 's/^/     /' || true
    fi
    echo "[dry-run] hiçbir şey yapılmadı."; exit 0
fi
if [ "$YES" = 0 ]; then
    read -r -p "Devam edilsin mi? (etiket itilir, Release yayımlanır) [y/N] " ans </dev/tty || ans=""
    [ "$ans" = "y" ] || [ "$ans" = "Y" ] || die "iptal edildi"
fi

if ! git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    git tag -a "$TAG" -m "linux-hardening $VERSION"
fi
git push origin "$TAG"

OUT=$(mktemp)
trap 'rm -f "$NOTES" "$OUT"' EXIT
scripts/release.sh | tee "$OUT"
[ -f "$ARCHIVE" ] || die "release.sh paket üretmedi"
[ -f "$ARCHIVE.sig" ] || die "release.sh imza üretmedi"

gh release create "$TAG" "$ARCHIVE" "$ARCHIVE.sig" --title "$TAG" --notes-file "$NOTES" --verify-tag

# Yüklenenlerin özeti yerelle AYNI olmalı
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
REMOTE=$(gh api "repos/$REPO/releases/tags/$TAG" --jq '.assets[] | "\(.name) \(.digest)"') || die "Release varlıkları okunamadı"
for f in "$ARCHIVE" "$ARCHIVE.sig"; do
    want="sha256:$(SUMOF "$f")"
    got=$(printf '%s\n' "$REMOTE" | awk -v n="$(basename "$f")" '$1 == n {print $2}')
    [ -n "$got" ] || die "Release'te $(basename "$f") yok"
    [ "$got" = "$want" ] || die "$(basename "$f") özeti uyuşmuyor: Release=$got yerel=$want"
done

# 6) indeks: Release yayımlandı ve özetler doğrulandı. İndeks hatası Release'i geçersiz kılmaz.
INDEX_RC=0
if [ "$NOINDEX" = 0 ]; then
    echo ""
    echo "-- 6) indeks"
    INDEX_SIGNING_KEY="${INDEX_SIGNING_KEY:-${PAKET_SIGNING_KEY:-${LH_SIGNING_KEY:-}}}"
    if [ -n "$INDEX_SIGNING_KEY" ]; then export INDEX_SIGNING_KEY; else unset INDEX_SIGNING_KEY; fi
    "$INDEX_PUBLISH" "$PKG_ID" "$VERSION" "$REPO" --archive "$ARCHIVE" --sig "$ARCHIVE.sig" --yes || INDEX_RC=$?
fi
echo ""
echo "✅ $TAG yayımlandı ve yüklenen dosyaların özeti yerelle aynı."
echo "components.lock (bilgi; normal sürümde GEREKMEZ, indeks halleder): sürüm $VERSION, SHA-256 $(SUMOF "$ARCHIVE")"
grep -E '^  .* namespaces=' "$OUT" || true
if [ "$NOINDEX" = 1 ]; then
    echo "UYARI: indeks adımı atlandı (--no-index). İndeksi sonra güncellemek için: $INDEX_PUBLISH $PKG_ID $VERSION $REPO"
elif [ "$INDEX_RC" != 0 ]; then
    echo "HATA: indeks adımı başarısız (çıkış $INDEX_RC). Release YAYIMLANDI ve geçerli; geri alınmadı." >&2
    echo "Tek başına yeniden çalıştırın (idempotent): $INDEX_PUBLISH $PKG_ID $VERSION $REPO --archive $ARCHIVE --sig $ARCHIVE.sig --yes" >&2
    exit 1
else
    echo "İndeks güncellendi (yerel commit): push SİZDE, indeks deposundaki komutu çalıştırın."
fi
