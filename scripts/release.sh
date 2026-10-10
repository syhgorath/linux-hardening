#!/usr/bin/env bash
# release.sh - Etiketli sürümden imzalı sürüm paketi üretir (bakımcı aracı, yerelde çalışır).
#
#   1) VERSION, component.yml ve CHANGELOG.md'yi güncelleyin; commit + etiket: git tag -a vX.Y.Z -m "..."
#   2) LH_SIGNING_KEY=~/.ssh/<ozel_anahtar> scripts/release.sh
#   3) dist/ içindeki .tar.gz ve .tar.gz.sig dosyalarını GitHub Release'e yükleyin.
#
# Özel imza anahtarı ASLA repoya, CI'a veya sohbete konmaz. Ayrıntı: docs/RELEASING.md
set -euo pipefail
cd "$(dirname "$0")/.."

NS="sshpocket-component"                       # imza ad alanı (çekirdeğin sshpocket-release'inden ayrı)
ID="${LH_SIGNER_ID:-sshpocket-component}"      # allowed_signers satırındaki principal; doğrulayıcının -I değeriyle AYNI olmalı
KEY="${LH_SIGNING_KEY:-$HOME/.ssh/sshpocket_release}"

die() { echo "HATA: $*" >&2; exit 1; }

VERSION=$(tr -d '[:space:]' < VERSION)
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "VERSION geçersiz: '$VERSION'"
TAG="v$VERSION"

[ -z "$(git status --porcelain)" ] || die "çalışma alanı temiz değil (commit edilmemiş değişiklik var)"
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null || die "etiket yok: $TAG (önce: git tag -a $TAG -m ...)"
[ "$(git rev-list -n1 "$TAG")" = "$(git rev-parse HEAD)" ] || die "$TAG şu anki commit'i göstermiyor"
grep -q "^## \[$VERSION\]" CHANGELOG.md || die "CHANGELOG.md içinde [$VERSION] başlığı yok"
[ -f "$KEY" ] || die "imza anahtarı bulunamadı: $KEY (LH_SIGNING_KEY ile belirtin)"
command -v ssh-keygen >/dev/null || die "ssh-keygen yok"

# Tutarlılık (VERSION, component.yml, profiller, destek matrisi, vars)
python3 -I scripts/check-consistency.py >/dev/null \
    || die "scripts/check-consistency.py başarısız (PyYAML kurulu mu? bulgu için komutu doğrudan çalıştırın)"

mkdir -p dist
ARCHIVE="dist/linux-hardening-$VERSION.tar.gz"
rm -f "$ARCHIVE" "$ARCHIVE.sig"
git archive --format=tar.gz --prefix="linux-hardening-$VERSION/" -o "$ARCHIVE" "$TAG"

# Paket içeriği: tek kök dizin, VERSION doğru, geliştirme dosyaları yok
roots=$(tar -tzf "$ARCHIVE" | cut -d/ -f1 | sort -u)
[ "$roots" = "linux-hardening-$VERSION" ] || die "pakette beklenmeyen kök dizin(ler): $roots"
inner=$(tar -xzOf "$ARCHIVE" "linux-hardening-$VERSION/VERSION" | tr -d '[:space:]')
[ "$inner" = "$VERSION" ] || die "paket içindeki VERSION ($inner) etiketle ($VERSION) aynı değil"
if tar -tzf "$ARCHIVE" | grep -qE "^linux-hardening-$VERSION/(\.github/|test/|scripts/|scans/|\.gitattributes)"; then
    die "pakette geliştirme dosyaları var (.gitattributes export-ignore kontrol edin)"
fi

ssh-keygen -Y sign -f "$KEY" -n "$NS" "$ARCHIVE"

# Yayından önce kendi doğrulamamız: özel anahtardan türetilen public key ile, aynı principal/ad alanıyla
PUB=$(ssh-keygen -y -f "$KEY" | cut -d' ' -f1,2)
SIGNERS=$(mktemp)
trap 'rm -f "$SIGNERS"' EXIT
printf '%s namespaces="%s" %s\n' "$ID" "$NS" "$PUB" > "$SIGNERS"
ssh-keygen -Y verify -f "$SIGNERS" -I "$ID" -n "$NS" -s "$ARCHIVE.sig" < "$ARCHIVE" >/dev/null \
    || die "üretilen imza DOĞRULANAMADI (yanlış anahtar/principal/ad alanı?)"

if command -v sha256sum >/dev/null 2>&1; then SUM=$(sha256sum "$ARCHIVE" | cut -d' ' -f1); else SUM=$(shasum -a 256 "$ARCHIVE" | cut -d' ' -f1); fi

echo ""
echo "✅ İmzalı paket hazır ve doğrulandı:"
ls -l "$ARCHIVE" "$ARCHIVE.sig"
echo "SHA-256: $SUM"
echo ""
echo "Doğrulayıcının (sshpocket components.lock) kullanacağı satır (principal=$ID, ad alanı=$NS):"
echo "  $ID namespaces=\"$NS\" $PUB"
echo ""
echo "Sıradaki: GitHub'da $TAG release'ini açın ve şu iki dosyayı 'Assets'e yükleyin:"
echo "  $ARCHIVE"
echo "  $ARCHIVE.sig"
