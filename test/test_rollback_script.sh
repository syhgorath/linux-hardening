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
    hardening_rollback_timeout: 300
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
[ "$1" = is-active ] && echo "${HR_TIMER_OUT-active}"
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
out=$(hr disarm); expect_contains "  armed iken disarm 'disarmed' der (Ansible changed)" "$out" "disarmed"
out=$(hr disarm); expect_contains "  armed degilken disarm degisiklik yok der" "$out" "armed degil: yapilacak bir sey yok"
if printf '%s' "$out" | grep -q "disarmed"; then bad "armed degilken 'disarmed' yazdi (Ansible changed=1 olurdu)"; else ok "armed degilken 'disarmed' YOK"; fi
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

echo "-- 8) status: TEK satir, kararli anahtarlar (armed degil / armed / eski surum / timer bos)"
PFX="SSHPOCKET_RESULT linux-hardening.rollback_status installed=yes"
setup; out=$(HR_NOW=1000 hr status)
expect_eq "  armed=no" "$PFX armed=no timer=active remaining_seconds=unknown timeout_seconds=300" "$out"
HR_NOW=1000 hr arm >/dev/null
out=$(HR_NOW=1088 hr status)
expect_eq "  armed=yes, kalan 212" "$PFX armed=yes timer=active remaining_seconds=212 timeout_seconds=300" "$out"
out=$(HR_NOW=9999 hr status)
expect_eq "  sure dolduysa kalan 0 (negatif degil)" "$PFX armed=yes timer=active remaining_seconds=0 timeout_seconds=300" "$out"
: > "$R/var/lib/hardening-rollback/armed"
out=$(HR_NOW=1088 hr status)
expect_eq "  eski surum (bos armed): kalan unknown" "$PFX armed=yes timer=active remaining_seconds=unknown timeout_seconds=300" "$out"
out=$(HR_TIMER_OUT="" HR_NOW=1088 hr status)
expect_eq "  timer bos cikti: unknown" "$PFX armed=yes timer=unknown remaining_seconds=unknown timeout_seconds=300" "$out"
n=$(printf '%s\n' "$out" | wc -l | tr -d ' ')
expect_eq "  status tek satir" "1" "$n"
echo "-- 9) PAM: arm yedekler, restore ONCEKI haline dondurur (bozuk yigin dahil), sayaclar silinir"
pam_setup() {
  setup
  mkdir -p "$R/etc/pam.d" "$R/var/lib/pam" "$R/usr/share/pam-configs" "$R/etc/security" "$R/run/faillock"
  for f in common-auth common-account common-password common-session common-session-noninteractive; do printf 'ORIJINAL-%s\n' "$f" > "$R/etc/pam.d/$f"; done
  for f in account auth password session session-noninteractive seen; do printf 'DURUM-%s\n' "$f" > "$R/var/lib/pam/$f"; done
  printf 'ORIJINAL-FAILLOCK-CONF\n' > "$R/etc/security/faillock.conf"
  printf 'kilit\n' > "$R/run/faillock/lhtest"
}
pam_setup; hr arm >/dev/null
file_eq "common-auth yedeklendi" "$R/var/lib/hardening-rollback/pam/common-auth" "ORIJINAL-common-auth"
file_eq "common-password yedeklendi" "$R/var/lib/hardening-rollback/pam/common-password" "ORIJINAL-common-password"
file_eq "/var/lib/pam/auth yedeklendi" "$R/var/lib/hardening-rollback/pam-state/auth" "DURUM-auth"
file_eq "faillock.conf yedeklendi" "$R/var/lib/hardening-rollback/faillock.conf" "ORIJINAL-FAILLOCK-CONF"
absent "faillock profili ONCEDEN yoktu: yedek dizininde profil yok" "$R/var/lib/hardening-rollback/faillock-profiles/hardening-faillock-preauth"
# degisiklik: bozuk yigin + yeni profiller (IKI tane) + degismis conf + yeni durum
printf 'auth required pam_deny.so\n' > "$R/etc/pam.d/common-auth"
printf 'BOZUK\n' > "$R/etc/pam.d/common-account"
printf 'Name: faillock preauth\n' > "$R/usr/share/pam-configs/hardening-faillock-preauth"
printf 'Name: faillock authfail\n' > "$R/usr/share/pam-configs/hardening-faillock-authfail"
printf 'Name: baska paket profili\n' > "$R/usr/share/pam-configs/pwquality"
printf 'DEGISTI\n' > "$R/etc/security/faillock.conf"
printf 'YENI-DURUM\n' > "$R/var/lib/pam/auth"
: > "$HR_LOG"; out=$(hr restore); rc=$?
expect_eq "restore cikis 0" "0" "$rc"
file_eq "bozuk common-auth ORIJINALE dondu" "$R/etc/pam.d/common-auth" "ORIJINAL-common-auth"
file_eq "common-account geri yuklendi" "$R/etc/pam.d/common-account" "ORIJINAL-common-account"
file_eq "/var/lib/pam/auth geri yuklendi" "$R/var/lib/pam/auth" "DURUM-auth"
absent "sonradan eklenen faillock preauth profili SILINDI" "$R/usr/share/pam-configs/hardening-faillock-preauth"
absent "sonradan eklenen faillock authfail profili SILINDI" "$R/usr/share/pam-configs/hardening-faillock-authfail"
file_eq "faillock OLMAYAN baska profile DOKUNULMADI" "$R/usr/share/pam-configs/pwquality" "Name: baska paket profili"
file_eq "faillock.conf geri yuklendi" "$R/etc/security/faillock.conf" "ORIJINAL-FAILLOCK-CONF"
absent "kilit sayaclari silindi (kimse kilitli kalmaz)" "$R/run/faillock/lhtest"
expect_contains "  PAM mesaji" "$out" "PAM dosyalari onceki icerige donduruldu"
if log_lacks "pam-auth-update"; then ok "pam-auth-update CAGRILMADI (dosyalar oldugu gibi geri yazilir)"; else bad "pam-auth-update cagrildi"; fi
absent "PAM yedegi temizlendi" "$R/var/lib/hardening-rollback/pam"
echo "-- 9b) faillock profili ONCEDEN vardi: restore ESKI icerigi yazar (silmez)"
pam_setup; printf 'ESKI-PROFIL\n' > "$R/usr/share/pam-configs/hardening-faillock-preauth"; hr arm >/dev/null
printf 'YENI-PROFIL\n' > "$R/usr/share/pam-configs/hardening-faillock-preauth"
printf 'EKLENEN\n' > "$R/usr/share/pam-configs/hardening-faillock-authfail"; hr restore >/dev/null
file_eq "eski profil geri yazildi" "$R/usr/share/pam-configs/hardening-faillock-preauth" "ESKI-PROFIL"
absent "arm'da olmayan ikinci profil silindi" "$R/usr/share/pam-configs/hardening-faillock-authfail"
echo "-- 9c) disarm: PAM yedegi de silinir, onayli degisiklik KORUNUR"
pam_setup; hr arm >/dev/null; printf 'ONAYLI\n' > "$R/etc/pam.d/common-auth"; hr disarm >/dev/null
absent "pam yedek klasoru silindi" "$R/var/lib/hardening-rollback/pam"
absent "pam-state yedegi silindi" "$R/var/lib/hardening-rollback/pam-state"
file_eq "onayli common-auth KORUNDU" "$R/etc/pam.d/common-auth" "ONAYLI"
echo "-- 9d) PAM dosyalari hic yokken (eski/baska sistem): arm ve restore hata vermez"
setup; hr arm >/dev/null; out=$(hr restore); rc=$?; expect_eq "cikis 0" "0" "$rc"
echo "-- 9e) restore sirasi: PAM, ssh/ufw adimlarindan ONCE (ssh/ufw takilsa bile PAM donmus olur)"
pam_setup; touch "$HR_UFW_ACTIVE"; hr arm >/dev/null; printf 'BOZUK\n' > "$R/etc/pam.d/common-auth"
cat > "$BIN/ufw" <<'F'
#!/bin/sh
echo "ufw $*" >> "$HR_LOG"
[ "$1" = status ] && { [ -e "$HR_UFW_ACTIVE" ] && echo "Status: active" || echo "Status: inactive"; }
[ "$1" = "--force" ] && exit 1
exit 0
F
chmod +x "$BIN/ufw"; hr restore >/dev/null 2>&1
file_eq "ufw basarisiz olsa da PAM donmustu" "$R/etc/pam.d/common-auth" "ORIJINAL-common-auth"
echo "-- 10) Proxmox pve-firewall (cluster.fw): arm yedekler, restore geri yazar/siler, restart; olmazsa stop"
cat > "$BIN/pve-firewall" <<'F'
#!/bin/sh
echo "pve-firewall $*" >> "$HR_LOG"
[ "$1" = restart ] && [ -e "$HR_PVEFW_FAIL" ] && exit 1
exit 0
F
chmod +x "$BIN/pve-firewall"
export HR_PVEFW="$BIN/pve-firewall" HR_PVEFW_FAIL="$TMP/pvefw.fail"
pve_setup() { setup; rm -f "$HR_PVEFW_FAIL"; mkdir -p "$R/etc/pve/firewall"; }
echo "-- 10a) cluster.fw ONCEDEN vardi: restore eski icerigi yazar ve pve-firewall restart eder"
pve_setup; printf 'ESKI-CLUSTER\n' > "$R/etc/pve/firewall/cluster.fw"; hr arm >/dev/null
printf 'YENI-CLUSTER\n' > "$R/etc/pve/firewall/cluster.fw"; out=$(hr restore)
file_eq "eski cluster.fw geri yazildi" "$R/etc/pve/firewall/cluster.fw" "ESKI-CLUSTER"
expect_contains "  mesaj" "$out" "pve-firewall cluster.fw onceki icerige donduruldu"
if log_has "pve-firewall restart"; then ok "pve-firewall restart cagrildi"; else bad "restart cagrilmadi"; fi
if log_lacks "pve-firewall stop"; then ok "restart basariliyken stop CAGRILMADI"; else bad "gereksiz stop"; fi
absent "pve yedegi temizlendi" "$R/var/lib/hardening-rollback/pve-firewall"
echo "-- 10b) cluster.fw ONCEDEN yoktu: restore olusturulan dosyayi SILER"
pve_setup; hr arm >/dev/null; printf 'ROL-YAZDI\n' > "$R/etc/pve/firewall/cluster.fw"; out=$(hr restore)
absent "arm'da olmayan cluster.fw silindi" "$R/etc/pve/firewall/cluster.fw"
expect_contains "  mesaj" "$out" "cluster.fw onceden yoktu: silindi"
if log_has "pve-firewall restart"; then ok "silindikten sonra restart"; else bad "restart yok"; fi
echo "-- 10c) restart basarisiz: son care pve-firewall stop"
pve_setup; hr arm >/dev/null; printf 'ROL-YAZDI\n' > "$R/etc/pve/firewall/cluster.fw"; : > "$HR_PVEFW_FAIL"; out=$(hr restore)
if log_has "pve-firewall stop"; then ok "stop cagrildi"; else bad "stop cagrilmadi"; fi
expect_contains "  uyari" "$out" "pve-firewall restart basarisiz"
absent "yine de cluster.fw silindi" "$R/etc/pve/firewall/cluster.fw"
echo "-- 10d) Proxmox DEGIL (/etc/pve/firewall yok): pve-firewall HIC cagrilmaz"
setup; hr arm >/dev/null; hr restore >/dev/null
if log_lacks "pve-firewall"; then ok "pve-firewall cagrilmadi"; else bad "Proxmox olmayan hostta pve-firewall cagrildi"; fi
absent "yedek klasoru olusmadi" "$R/var/lib/hardening-rollback/pve-firewall"
echo "-- 10e) disarm: onayli cluster.fw KORUNUR, yedek silinir, pve-firewall cagrilmaz"
pve_setup; hr arm >/dev/null; printf 'ONAYLI\n' > "$R/etc/pve/firewall/cluster.fw"; hr disarm >/dev/null
file_eq "onayli cluster.fw KORUNDU" "$R/etc/pve/firewall/cluster.fw" "ONAYLI"
absent "pve yedegi silindi" "$R/var/lib/hardening-rollback/pve-firewall"
if log_lacks "pve-firewall"; then ok "disarm pve-firewall'a dokunmadi"; else bad "disarm pve-firewall cagirdi"; fi
echo "-- 10f) armed degilken restore hicbir sey yapmaz"
pve_setup; printf 'DOKUNMA\n' > "$R/etc/pve/firewall/cluster.fw"; hr restore >/dev/null
file_eq "cluster.fw degismedi" "$R/etc/pve/firewall/cluster.fw" "DOKUNMA"
if log_lacks "pve-firewall"; then ok "pve-firewall cagrilmadi"; else bad "armed degilken pve-firewall cagrildi"; fi
echo "-- 10g) ufw KURULU DEGIL (Proxmox): restore ufw uyarisi uretmez, yine de bitirir"
pve_setup; HR_UFW="$TMP/yok-ufw" hr arm >/dev/null; out=$(HR_UFW="$TMP/yok-ufw" hr restore)
expect_not_contains "  ufw uyarisi yok" "$out" "ufw"
expect_contains "  tamamlandi" "$out" "geri alma tamamlandi"
out=$(hr foo); rc=$?; expect_eq "gecersiz komut cikis 2" "2" "$rc"; expect_contains "  kullanim" "$out" "kullanim:"
finish
