#!/usr/bin/env python3
"""GRUB parolası doğrulaması (SALT OKUNUR): `update-grub` sonrası üretilen grub.cfg'de parola ayarının ve açılış girdilerinin beklenen biçimde olduğunu denetler.

Girdi (argv[1], JSON): cfg (grub.cfg yolu), user (süper kullanıcı), hash (grub.pbkdf2.sha512... özeti), unrestricted (bool: normal açılış parolasız kalmalı).
Çıktı (stdout, JSON): ok (bool), errors (liste), entries (üst düzey Linux girdisi sayısı). Python 3.9+ (yalnızca stdlib).

Neden: gerçek `grub-mkconfig` (GRUB 2.14, Ubuntu 26.04) ile görüldü: (1) `superusers` ayarlanınca `--unrestricted` olmayan her girdi parola ister, yani normal açılış da bloklanır;
(2) `CLASS` satırına `--unrestricted` eklemek recovery girdilerini de kilitsiz yapar (parolasız kök kabuğu), bu yüzden recovery kapatılır; (3) /etc/grub.d içinde kalan bir yedek dosya
çalıştırılır ve menüyü ÇİFT üretir (ikinci kopya yamasız)."""
import json
import re
import subprocess
import sys
from shutil import which


def check(cfg_text, user, pw_hash, unrestricted):
    errors = []
    lines = cfg_text.split("\n")
    su = [ln for ln in lines if re.match(r'^\s*set\s+superusers="', ln)]
    if len(su) != 1 or su[0].strip() != 'set superusers="%s"' % user:
        errors.append('grub.cfg içinde tam olarak bir `set superusers="%s"` satırı olmalı (bulunan: %d).' % (user, len(su)))
    pw = [ln for ln in lines if re.match(r"^\s*password_pbkdf2\s", ln)]
    if len(pw) != 1 or pw[0].split() != ["password_pbkdf2", user, pw_hash]:
        errors.append("grub.cfg içinde tam olarak bir `password_pbkdf2 %s <özet>` satırı olmalı (bulunan: %d)." % (user, len(pw)))
    entries = [ln for ln in lines if ln.lstrip().startswith("menuentry ")]
    # Ana açılış girdisi: 10_linux'un üst düzey `gnulinux-simple-` girdisi. os-prober'ın bulduğu başka işletim sistemleri (`osprober-`), UEFI ayarları ve
    # `Advanced options` alt menüsü bilerek KİLİTLİ kalır (gerçek LAB koşusunda os-prober başka bir diski bulup girdi ekledi).
    linux = [ln for ln in lines if ln.startswith("menuentry ") and "'gnulinux-simple-" in ln]
    if unrestricted:
        if not linux:
            errors.append("Parolasız açılış istendi ama ana Linux açılış girdisi (gnulinux-simple-) bulunamadı.")
        for ln in linux:
            if "--unrestricted" not in ln:
                errors.append("Ana Linux girdisi `--unrestricted` değil: açılış konsolda parola bekler. Girdi: %s" % ln[:80])
        for ln in entries:
            if "recovery" in ln.lower() and "--unrestricted" in ln:
                errors.append("Kilitsiz (--unrestricted) recovery girdisi var: parolasız kök kabuğu açar; GRUB_DISABLE_RECOVERY=true olmalı. Girdi: %s" % ln.strip()[:80])
    # Yinelenme yalnızca ANA girdide aranır (os-prober başka disklerde aynı kimliği üretebilir); /etc/grub.d içinde kalan yedek dosya ana girdiyi çiftler.
    ids = [m.group(1) for ln in entries for m in [re.search(r"'(gnulinux-simple-[^']+)'", ln)] if m]
    if len(ids) != len(set(ids)):
        errors.append("Ana açılış girdisi yinelenmiş: /etc/grub.d içinde yedek/ikinci betik kalmış olabilir (dizindeki her çalıştırılabilir dosya çalışır).")
    return errors, len(linux)


def main(argv):
    try:
        cfg = json.loads(argv[1])
        text = open(cfg["cfg"], encoding="utf-8", errors="replace").read()
        errors, n = check(text, str(cfg["user"]), str(cfg["hash"]), bool(cfg.get("unrestricted", True)))
    except (IndexError, ValueError, KeyError, OSError) as exc:
        print(json.dumps({"ok": False, "errors": ["denetim girdisi okunamadı: %s" % exc], "entries": 0}, ensure_ascii=False))
        return 0
    if which("grub-script-check"):
        r = subprocess.run(["grub-script-check", cfg["cfg"]], capture_output=True, text=True)
        if r.returncode != 0:
            errors.append("grub-script-check başarısız: %s" % (r.stdout + r.stderr).strip()[:200])
    print(json.dumps({"ok": not errors, "errors": errors, "entries": n}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
