#!/bin/sh
# Ansible tarafından yönetilir (hardening_rollback). Elle düzenlemeyin.
#
#   hardening-rollback arm      önceki durumu yedekler (zaten armed ise yedeği korur), zamanlayıcıyı başlatır
#   hardening-rollback disarm   değişiklik onaylandı: armed'ı ve yedeği siler, zamanlayıcıyı durdurur
#   hardening-rollback restore  önceki duruma döner (zamanlayıcı bunu çağırır); armed değilse hiçbir şey yapmaz
#   hardening-rollback status   durumu TEK satir olarak yazar (kararli anahtarlar; docs/design/rollback-timer.md 4.4)
#
# Test için ortam değişkenleri: HR_ROOT (yol öneki), HR_UFW, HR_SSHD, HR_SYSTEMCTL, HR_SSH_SERVICE, HR_NOW (epoch saniye).
set -eu

ROOT="${HR_ROOT:-}"
STATE="$ROOT/var/lib/hardening-rollback"
ARMED="$STATE/armed"
DROPIN="$ROOT/etc/ssh/sshd_config.d/00-hardening.conf"
UFWDIR="$ROOT/etc/ufw"
UFW="${HR_UFW:-ufw}"
SSHD="${HR_SSHD:-/usr/sbin/sshd}"
SYSTEMCTL="${HR_SYSTEMCTL:-systemctl}"
DEFAULT_SSH_SERVICE='ssh'
SSH_SERVICE="${HR_SSH_SERVICE:-$DEFAULT_SSH_SERVICE}"
TIMER="hardening-rollback.timer"
TIMEOUT_SECONDS=300
UFW_FILES="ufw.conf user.rules user6.rules"

# systemd altinda (INVOCATION_ID dolu) stdout zaten journal'a (hardening-rollback etiketiyle) gider; logger'i da
# cagirmak her satiri iki kez kaydederdi. Elle/Ansible calistirmada stdout journal'a gitmez: logger ile yazilir.
log() {
  if [ -z "${INVOCATION_ID:-}" ]; then
    logger -t hardening-rollback -- "$*" 2>/dev/null || true
  fi
  echo "$*"
}

do_backup() {
  mkdir -p "$STATE/ufw"
  chmod 0700 "$STATE"
  rm -f "$STATE/had-dropin" "$STATE/00-hardening.conf" "$STATE/ufw-active"
  for f in $UFW_FILES; do rm -f "$STATE/ufw/$f"; done
  if [ -e "$DROPIN" ]; then
    cp -p "$DROPIN" "$STATE/00-hardening.conf"
    : > "$STATE/had-dropin"
  fi
  for f in $UFW_FILES; do
    if [ -e "$UFWDIR/$f" ]; then cp -p "$UFWDIR/$f" "$STATE/ufw/$f"; fi
  done
  if "$UFW" status 2>/dev/null | grep -q '^Status: active'; then
    echo yes > "$STATE/ufw-active"
  else
    echo no > "$STATE/ufw-active"
  fi
}

do_arm() {
  mkdir -p "$STATE"
  chmod 0700 "$STATE"
  if [ -e "$ARMED" ]; then
    log "zaten armed: ilk yedek korunuyor, geri sayim yenileniyor"
  else
    do_backup
    : > "$ARMED"
  fi
  "$SYSTEMCTL" enable "$TIMER" >/dev/null 2>&1 || true
  "$SYSTEMCTL" restart "$TIMER"
  # armed dosyasina bitis zamani (epoch) yazilir: status kalan sureyi buradan hesaplar (dosyanin varligi hala armed demektir)
  echo $(( ${HR_NOW:-$(date +%s)} + TIMEOUT_SECONDS )) > "$ARMED"
  log "armed"
}

do_disarm() {
  rm -f "$ARMED" "$STATE/had-dropin" "$STATE/00-hardening.conf" "$STATE/ufw-active"
  for f in $UFW_FILES; do rm -f "$STATE/ufw/$f"; done
  rmdir "$STATE/ufw" 2>/dev/null || true
  "$SYSTEMCTL" disable --now "$TIMER" >/dev/null 2>&1 || true
  log "disarmed"
}

do_restore() {
  if [ ! -e "$ARMED" ]; then
    log "armed degil: yapilacak bir sey yok"
    exit 0
  fi
  # ssh: onceki drop-in icerigini geri yaz; yoksa sil
  if [ -e "$STATE/had-dropin" ]; then
    cp -p "$STATE/00-hardening.conf" "$DROPIN"
    log "sshd drop-in onceki icerige donduruldu"
  else
    rm -f "$DROPIN"
    log "sshd drop-in onceden yoktu: silindi"
  fi
  if "$SSHD" -t >/dev/null 2>&1; then
    "$SYSTEMCTL" reload "$SSH_SERVICE" || log "UYARI: sshd reload basarisiz"
  else
    log "UYARI: sshd -t basarisiz; sshd reload edilmedi"
  fi
  # ufw: yedekteki dosyalari geri yaz, aktif/pasif durumunu eski haline getir
  if [ -e "$STATE/ufw-active" ]; then
    for f in $UFW_FILES; do
      if [ -e "$STATE/ufw/$f" ]; then cp -p "$STATE/ufw/$f" "$UFWDIR/$f"; fi
    done
    if [ "$(cat "$STATE/ufw-active")" = "yes" ]; then
      "$UFW" --force enable >/dev/null 2>&1 || log "UYARI: ufw enable basarisiz"
      log "ufw onceki kurallarla aktif birakildi"
    else
      "$UFW" --force disable >/dev/null 2>&1 || log "UYARI: ufw disable basarisiz"
      log "ufw onceden pasifti: pasif birakildi"
    fi
  fi
  rm -f "$ARMED"
  "$SYSTEMCTL" disable --now "$TIMER" >/dev/null 2>&1 || true
  log "geri alma tamamlandi"
}

do_status() {
  armed=no remaining=unknown
  if [ -e "$ARMED" ]; then
    armed=yes
    deadline=$(cat "$ARMED" 2>/dev/null || true)
    case "$deadline" in
      ''|*[!0-9]*) ;;   # bos ya da sayi degil (eski surum): bilinmiyor
      *)
        remaining=$(( deadline - ${HR_NOW:-$(date +%s)} ))
        if [ "$remaining" -lt 0 ]; then remaining=0; fi
        ;;
    esac
  fi
  timer=$("$SYSTEMCTL" is-active "$TIMER" 2>/dev/null || true)
  if [ -z "$timer" ]; then timer=unknown; fi
  echo "SSHPOCKET_RESULT linux-hardening.rollback_status installed=yes armed=$armed timer=$timer remaining_seconds=$remaining timeout_seconds=$TIMEOUT_SECONDS"
}

case "${1:-}" in
  arm) do_arm ;;
  disarm) do_disarm ;;
  restore) do_restore ;;
  status) do_status ;;
  *) echo "kullanim: hardening-rollback arm|disarm|restore|status" >&2; exit 2 ;;
esac
