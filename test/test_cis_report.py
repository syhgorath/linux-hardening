#!/usr/bin/env python3
"""hardening_report: `cis_report.py` karar mantığı (SALT OKUNUR; IPv6 durumu 3.1.1, dinleyiciler 2.1.23, nokta dizinleri 7.2.11, nullok/boş parola 5.3.3.4.1)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "roles/hardening_report/files/cis_report.py"
fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail}")


def run(cfg):
    r = subprocess.run([sys.executable, str(SCRIPT), cfg if isinstance(cfg, str) else json.dumps(cfg)], capture_output=True, text=True)
    return json.loads(r.stdout)


w = lambda o: " ".join(o["warnings"])
n = lambda o: " ".join(o["notes"])

# IPv6
check("ipv6 etkin + global adres -> not (uyari degil), kapatmaz", "etkin" in n(run({"ipv6": {"disable_all": "0", "global_addrs": 2}})) and "global" in n(run({"ipv6": {"disable_all": "0", "global_addrs": 2}})) and not run({"ipv6": {"disable_all": "0", "global_addrs": 2}})["warnings"])
check("ipv6 kapali -> not", "devre dışı" in n(run({"ipv6": {"disable_all": "1"}})))
check("ipv6 okunamadi -> not", "okunamadı" in n(run({"ipv6": {"disable_all": ""}})))

# dinleyiciler
L = ["tcp 0.0.0.0:22", "tcp [::]:22", "tcp 127.0.0.1:25", "tcp [::1]:631", "udp 127.0.0.53%lo:53", "tcp *:8006", "udp 0.0.0.0:68", "tcp 10.0.0.5:3306"]
o = run({"listeners": L, "approved": []})
check("onaysiz liste bos -> yalniz NOT: yerel olmayan portlar listelenir, uyari yok", not o["warnings"] and all(k in n(o) for k in ("22/tcp", "8006/tcp", "68/udp", "3306/tcp")) and "25/tcp" not in n(o) and "53/udp" not in n(o), str(o))
o = run({"listeners": L, "approved": ["22/tcp", "68/udp"]})
check("onayli liste dolu -> listede olmayan yerel-olmayan portlar UYARI", "8006/tcp" in w(o) and "3306/tcp" in w(o) and "22/tcp" not in w(o) and "68/udp" not in w(o), str(o))
check("tum yerel-olmayan portlar onayli -> uyari yok", not run({"listeners": L, "approved": ["22/tcp", "8006/tcp", "68/udp", "3306/tcp"]})["warnings"])
check("loopback dinleyiciler hic raporlanmaz", "127.0.0.1" not in w(o) and "631" not in w(o) + n(o))
check("bozuk dinleyici satiri atlanir, cokmez", run({"listeners": ["x", "", "tcp"], "approved": ["1/tcp"]})["warnings"] == [])

# nokta dizinleri
D = ["750 ali /home/ali/.config", "755 ali /home/ali/.cache", "700 ali /home/ali/.ssh", "750 veli /home/veli/.ssh", "777 veli /home/veli/.gnupg", "640 veli /home/veli/.x"]
o = run({"dotdirs": D})
check("nokta dizini 755 (diger okuma/calistirma) -> uyari; 750 ve 700 temiz", "/home/ali/.cache" in w(o) and "/home/ali/.config" not in w(o) and "/home/ali/.ssh" not in w(o), str(o))
check(".ssh 750 (grup erisimi) -> uyari (0700 beklenir)", "/home/veli/.ssh" in w(o))
check("777 -> uyari", "/home/veli/.gnupg" in w(o))
check("hicbir sey degistirilmedi diye belirtir", "Değiştirilmedi" in w(o))
check("temiz dizinler -> uyari yok", not run({"dotdirs": ["750 ali /home/ali/.config", "700 ali /home/ali/.ssh", "700 ali /home/ali/.gnupg"]})["warnings"])
check("10'dan fazla -> kisaltilir", w(run({"dotdirs": ["777 a /home/a/.d%d" % i for i in range(15)]})).count("/home/a/.d") == 10 and "..." in w(run({"dotdirs": ["777 a /home/a/.d%d" % i for i in range(15)]})))

# nullok / bos parola
o = run({"nullok": {"lines": ["/etc/pam.d/common-auth:25:auth [success=1 default=ignore] pam_unix.so nullok"], "empty_accounts": []}})
check("nullok var, bos parola yok -> NOT, uyari degil", "nullok" in n(o) and not o["warnings"], str(o))
o = run({"nullok": {"lines": [], "empty_accounts": ["test"]}})
check("bos parolali hesap -> UYARI", "BOŞ PAROLALI" in w(o) and "test" in w(o), str(o))
check("nullok yok, bos parola yok -> 'nullok yok' notu", "`nullok` yok" in n(run({"nullok": {"lines": [], "empty_accounts": []}})))
o = run({"nullok": {"lines": ["x"], "empty_accounts": ["a", "b"]}})
check("hem nullok hem bos parola", "a, b" in w(o) and "nullok" in n(o))

# MOTD (1.6.4) ve pam_unix (5.3.3.4.2, 5.3.3.4.4)
o = run({"motd": {"hits": ["/run/motd.dynamic", "/etc/motd"]}})
check("MOTD'da isletim sistemi bilgisi -> UYARI, dosyalar ve hardening_motd_disable_scripts yonlendirmesi", "1.6.4" in w(o) and "/run/motd.dynamic" in w(o) and "hardening_motd_disable_scripts" in w(o) and o["status"] == "warn", str(o))
check("MOTD temiz -> uyari yok", not run({"motd": {"hits": []}})["warnings"])
o = run({"pamunix": {"remember": ["/etc/pam.d/common-password:26:password pam_unix.so remember=5"], "no_authtok": []}})
check("pam_unix remember= -> UYARI (5.3.3.4.2)", "5.3.3.4.2" in w(o) and "remember=" in w(o), str(o))
o = run({"pamunix": {"remember": [], "no_authtok": ["/etc/pam.d/common-password:26"]}})
check("pam_unix use_authtok yok -> UYARI (5.3.3.4.4)", "5.3.3.4.4" in w(o) and "use_authtok" in w(o), str(o))
check("pam_unix temiz -> uyari yok", not run({"pamunix": {"remember": [], "no_authtok": []}})["warnings"])

# genel
check("bos girdi -> ok, bos", run({}) == {"status": "ok", "warnings": [], "notes": []})
check("status warn <=> uyari var", run({"nullok": {"empty_accounts": ["x"]}})["status"] == "warn" and run({"ipv6": {"disable_all": "1"}})["status"] == "ok")
check("bozuk JSON cokmez", run("{bozuk")["status"] == "ok" and run("[1]")["status"] == "ok")

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
