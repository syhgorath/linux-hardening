#!/usr/bin/env bash
# hardening-rollback betiği: sahte ufw/sshd/systemctl ve geçici kök dizinle arm/disarm/restore/status mantığı.
# shellcheck source=test/lib.sh
. "$(dirname "$0")/lib.sh"

# --- betigi sablondan render et ---
cat > "$TMP/render.yml" <<Y
- hosts: localhost
  connection: local
  gather_facts: false
  vars:
    hardening_ssh_service: ssh
  tasks:
    - ansible.builtin.template:
        src: $ROOT/roles/hardening_rollback/templates/hardening-rollback.sh.j2
        dest: $TMP/hardening-rollback
        mode: "0755"
Y
ap -i "$TESTDIR/inventory-local.yml" "$TMP/render.yml" >/dev/null
if [ -x "$TMP/hardening-rollback" ]; then ok "betik render edildi"; else bad "betik render edilemedi"; finish; fi
if command -v shellcheck >/dev/null 2>&1; then
  if shellcheck -s sh "$TMP/hardening-rollback"; then ok "shellcheck (sh) temiz"; else bad "shellcheck bulgu var"; fi
elif [ -n "${CI:-}" ]; then bad "shellcheck CI'da yok"; fi

# --- sahte komutlar ---
BIN="$TMP/bin"; mkdir -p "$BIN"
cat > "$BIN/ufw" <<'F'
#!/bin/sh
echo "ufw $*" >> "$HR_LOG"
if [ "$1" = status ]; then
  if [ -e "$HR_UFW_ACTIVE" ]; then echo "Status: active"; else echo "Status: inactive"; fi
fi
F
cat > "$BIN/sshd" <<'F'
#!/bin/sh
echo "sshd $*" >> "$HR_LOG"
[ -e "$HR_SSHD_FAIL" ] && exit 1
exit 0
F
cat > "$BIN/systemctl" <<'F'
#!/bin/sh
echo "systemctl $*" >> "$HR_LOG"
[ "$1" = is-active ] && echo active
exit 0
F
chmod +x "$BIN"/*

setup() {   # temiz kok + varsayilan "once" durumu
  R="$TMP/root"; rm -rf "$R"
  mkdir -p "$R/etc/ssh/sshd_config.d" "$R/etc/ufw" "$R/var/lib"
  printf 'ORIGINAL-UFWCONF\n' > "$R/etc/ufw/ufw.conf"
  printf 'ORIGINAL-RULES4\n' > "$R/etc/ufw/user.rules"
  printf 'ORIGINAL-RULES6\n' > "$R/etc/ufw/user6.rules"
  export HR_ROOT="$R" HR_UFW="$BIN/ufw" HR_SSHD="$BIN/sshd" HR_SYSTEMCTL="$BIN/systemctl"
  export HR_SSH_SERVICE=ssh HR_LOG="$TMP/calls.log" HR_UFW_ACTIVE="$TMP/ufw.active" HR_SSHD_FAIL="$TMP/sshd.fail"
  : > "$HR_LOG"; rm -f "$HR_UFW_ACTIVE" "$HR_SSHD_FAIL"
}
hr() { "$TMP/hardening-rollback" "$@" 2>&1; }
log_has() { grep -qF -- "$1" "$HR_LOG"; }
log_lacks() { ! grep -qF -- "$1" "$HR_LOG"; }
file_eq() { # ad dosya beklenen
  if [ -e "$2" ] && [ "$(cat "$2")" = "$3" ]; then ok "$1"; else bad "$1 (dosya: $(cat "$2" 2>/dev/null || echo YOK))"; fi
}
absent() { if [ ! -e "$2" ]; then ok "$1"; else bad "$1 (dosya var)"; fi; }

echo "-- 1) armed degilken restore: HICBIR sey yapmaz"
setup; printf 'MEVCUT\n' > "$R/etc/ssh/sshd_config.d/00-hardening.conf"
out=$(hr restore); rc=$?
expect_eq "cikis 0" "0" "$rc"; expect_contains "  mesaj" "$out" "armed degil"
file_eq "drop-in dokunulmadi" "$R/etc/ssh/sshd_config.d/00-hardening.conf" "MEVCUT"
if log_lacks "ufw "; then ok "ufw cagrilmadi"; else bad "ufw cagrildi"; fi

echo "-- 2) arm: yedek + armed + timer"
setup; touch "$HR_UFW_ACTIVE"; printf 'ORIGINAL-DROPIN\n' > "$R/etc/ssh/sshd_config.d/00-hardening.conf"
out=$(hr arm); rc=$?
expect_eq "cikis 0" "0" "$rc"
if [ -e "$R/var/lib/hardening-rollback/armed" ]; then ok "armed var"; else bad "armed yok"; fi
file_eq "drop-in yedeklendi" "$R/var/lib/hardening-rollback/00-hardening.conf" "ORIGINAL-DROPIN"
file_eq "ufw.conf yedeklendi" "$R/var/lib/hardening-rollback/ufw/ufw.conf" "ORIGINAL-UFWCONF"
file_eq "user.rules yedeklendi" "$R/var/lib/hardening-rollback/ufw/user.rules" "ORIGINAL-RULES4"
file_eq "ufw-active=yes" "$R/var/lib/hardening-rollback/ufw-active" "yes"
if log_has "systemctl enable hardening-rollback.timer" && log_has "systemctl restart hardening-rollback.timer"; then ok "timer enable+restart"; else bad "timer cagrilari eksik"; fi
perm=$(stat -c '%a' "$R/var/lib/hardening-rollback" 2>/dev/null || stat -f '%Lp' "$R/var/lib/hardening-rollback")
expect_eq "state dizini 0700" "700" "$perm"

echo "-- 3) degisiklik sonrasi restore: ONCEKI icerik geri yuklenir (silmez)"
printf 'DEGISTI-DROPIN\n' > "$R/etc/ssh/sshd_config.d/00-hardening.conf"
printf 'DEGISTI-RULES4\n' > "$R/etc/ufw/user.rules"
printf 'DEGISTI-UFWCONF\n' > "$R/etc/ufw/ufw.conf"
: > "$HR_LOG"
out=$(hr restore); rc=$?
expect_eq "cikis 0" "0" "$rc"
file_eq "drop-in onceki icerige dondu" "$R/etc/ssh/sshd_config.d/00-hardening.conf" "ORIGINAL-DROPIN"
file_eq "user.rules geri yuklendi" "$R/etc/ufw/user.rules" "ORIGINAL-RULES4"
file_eq "ufw.conf geri yuklendi" "$R/etc/ufw/ufw.conf" "ORIGINAL-UFWCONF"
if log_has "ufw --force enable"; then ok "ufw eskiden aktifti: enable"; else bad "ufw enable cagrilmadi"; fi
if log_has "systemctl reload ssh"; then ok "sshd reload"; else bad "sshd reload yok"; fi
if log_has "systemctl disable --now hardening-rollback.timer"; then ok "timer durduruldu"; else bad "timer durdurulmadi"; fi
absent "armed silindi" "$R/var/lib/hardening-rollback/armed"
echo "-- 3b) restore idempotent"
: > "$HR_LOG"; out=$(hr restore)
expect_contains "  ikinci restore no-op" "$out" "armed degil"
if log_lacks "ufw "; then ok "ikinci restore ufw cagirmadi"; else bad "ikinci restore ufw cagirdi"; fi

echo "-- 4) drop-in YOKTU, ufw PASIFTI: restore siler/kapatir"
setup   # ufw aktif degil, drop-in yok
hr arm >/dev/null
printf 'YENI\n' > "$R/etc/ssh/sshd_config.d/00-hardening.conf"
: > "$HR_LOG"; hr restore >/dev/null
absent "drop-in silindi (onceden yoktu)" "$R/etc/ssh/sshd_config.d/00-hardening.conf"
if log_has "ufw --force disable"; then ok "ufw pasifti: disable"; else bad "ufw disable cagrilmadi"; fi
if log_lacks "ufw --force enable"; then ok "ufw enable CAGRILMADI"; else bad "ufw enable cagrildi"; fi

echo "-- 5) iki kez arm: ILK yedek korunur"
setup; touch "$HR_UFW_ACTIVE"; printf 'BIRINCI\n' > "$R/etc/ssh/sshd_config.d/00-hardening.conf"
hr arm >/dev/null
printf 'IKINCI\n' > "$R/etc/ssh/sshd_config.d/00-hardening.conf"
out=$(hr arm); expect_contains "  ikinci arm mesaji" "$out" "ilk yedek korunuyor"
hr restore >/dev/null
file_eq "ilk yedege donuldu" "$R/etc/ssh/sshd_config.d/00-hardening.conf" "BIRINCI"

echo "-- 6) disarm: armed+yedek silinir, sonra restore no-op"
setup; printf 'ORIGINAL-DROPIN\n' > "$R/etc/ssh/sshd_config.d/00-hardening.conf"
hr arm >/dev/null; printf 'ONAYLI-DEGISIKLIK\n' > "$R/etc/ssh/sshd_config.d/00-hardening.conf"
hr disarm >/dev/null
absent "armed silindi" "$R/var/lib/hardening-rollback/armed"
absent "yedek silindi" "$R/var/lib/hardening-rollback/00-hardening.conf"
absent "bos ufw yedek klasoru de silindi (artik birakilmaz)" "$R/var/lib/hardening-rollback/ufw"
out=$(hr restore); expect_contains "  restore no-op" "$out" "armed degil"
file_eq "onayli degisiklik KORUNDU" "$R/etc/ssh/sshd_config.d/00-hardening.conf" "ONAYLI-DEGISIKLIK"

echo "-- 7) sshd -t basarisiz: reload edilmez ama dosyalar geri yuklenir"
setup; touch "$HR_UFW_ACTIVE"; printf 'ORIGINAL-DROPIN\n' > "$R/etc/ssh/sshd_config.d/00-hardening.conf"
hr arm >/dev/null; printf 'BOZUK\n' > "$R/etc/ssh/sshd_config.d/00-hardening.conf"
touch "$HR_SSHD_FAIL"; : > "$HR_LOG"
out=$(hr restore); expect_contains "  uyari" "$out" "sshd -t basarisiz"
if log_lacks "systemctl reload"; then ok "sshd reload edilmedi"; else bad "sshd reload edildi"; fi
file_eq "dosya yine de geri yazildi" "$R/etc/ssh/sshd_config.d/00-hardening.conf" "ORIGINAL-DROPIN"

echo "-- 7b) journald: systemd altinda (INVOCATION_ID) logger cagrilmaz (cift kayit yok)"
cat > "$BIN/logger" <<'F'
#!/bin/sh
echo "logger $*" >> "$HR_LOG"
F
chmod +x "$BIN/logger"
setup; printf 'X\n' > "$R/etc/ssh/sshd_config.d/00-hardening.conf"
PATH="$BIN:$PATH" INVOCATION_ID=abc123 hr arm >/dev/null
if log_lacks "logger "; then ok "INVOCATION_ID dolu: logger cagrilmadi"; else bad "INVOCATION_ID dolu iken logger cagrildi"; fi
: > "$HR_LOG"; setup; printf 'X\n' > "$R/etc/ssh/sshd_config.d/00-hardening.conf"
# CI runner'i (systemd altinda) ortamda zaten INVOCATION_ID tasir: acikca BOSALT
PATH="$BIN:$PATH" INVOCATION_ID="" hr arm >/dev/null
if log_has "logger -t hardening-rollback"; then ok "INVOCATION_ID bos: logger cagrildi (elle/Ansible)"; else bad "logger cagrilmadi"; fi

echo "-- 8) status ve kullanim"
setup; out=$(hr status); expect_contains "  armed=no" "$out" "armed=no"
hr arm >/dev/null; out=$(hr status); expect_contains "  armed=yes" "$out" "armed=yes"
out=$(hr foo); rc=$?; expect_eq "gecersiz komut cikis 2" "2" "$rc"; expect_contains "  kullanim" "$out" "kullanim:"
finish
