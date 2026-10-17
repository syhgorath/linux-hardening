#!/usr/bin/env python3
"""hardening_ufw: `roles/hardening_ufw/files/stale_ssh_rules.py` (allow_from'da OLMAYAN, bizim biçimimizdeki SSH kurallarını bulur).

Karar mantığı tek bir betikte olduğu için sahte ufw gerekmeden denenir. Asıl risk, geçerli bir kuralı yanlışlıkla "eski" sayıp silmek
(erişim kaybı); bu yüzden normalleştirme (10.0.0.1 == 10.0.0.1/32), güvenlik ağları ve uç durumlar tek tek sınanır.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "roles/hardening_ufw/files/stale_ssh_rules.py"
fails = 0


def check(name, want, got):
    global fails
    if want == got:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}: beklenen={want!r} gercek={got!r}")


def run(cfg):
    r = subprocess.run([sys.executable, str(SCRIPT), json.dumps(cfg)], capture_output=True, text=True)
    try:
        return r.returncode, json.loads(r.stdout)
    except ValueError:
        return r.returncode, {"_ham": r.stdout, "_err": r.stderr}


def rule(src, port=22, tail=""):
    return f"ufw allow from {src} to any port {port} proto tcp{tail}"


base = {"allow_from": ["10.1.10.0/24"], "ssh_ports": [22], "extra_allow": [], "controller": "10.1.10.190", "added": []}

if not SCRIPT.exists():
    check("betik var (roles/hardening_ufw/files/stale_ssh_rules.py)", True, False)
    sys.exit(1)

rc, o = run({**base, "added": [rule("10.1.10.0/24"), rule("10.99.0.0/24")]})
check("1) allow_from'da olmayan ağ eski sayılır", [{"src": "10.99.0.0/24", "port": "22"}], o.get("stale"))
check("   çıkış 0", 0, rc)

# Kontrol makinesi BAŞKA ağda (10.1.10.190): normalleştirme hatası kontrol makinesi korumasıyla örtülmesin; ne stale ne blocked olmalı.
rc, o = run({**base, "allow_from": ["10.0.0.1/32", "10.1.10.0/24"], "added": [rule("10.0.0.1"), rule("10.1.10.0/24")]})
check("2) normalleştirme: 10.0.0.1/32 ile 10.0.0.1 aynı (ne silinir ne engellenir)", ([], []), (o.get("stale"), o.get("blocked")))
rc, o = run({**base, "allow_from": ["10.0.0.5", "10.1.10.0/24"], "added": [rule("10.0.0.5/32"), rule("10.1.10.0/24")]})
check("   ters yön: allow_from '10.0.0.5', ufw '10.0.0.5/32'", ([], []), (o.get("stale"), o.get("blocked")))

rc, o = run({**base, "allow_from": ["fd00::/8", "10.1.10.0/24"], "added": [rule("fd00:0::/8"), rule("fe80::/10")]})
check("3) IPv6 normalleştirme (fd00:0::/8 == fd00::/8); fe80::/10 eski", ([{"src": "fe80::/10", "port": "22"}], []), (o.get("stale"), o.get("blocked")))

rc, o = run({**base, "added": [rule("10.99.0.0/24", 8080)]})
check("4) SSH portu olmayan (8080) kurala dokunulmaz", [], o.get("stale"))

rc, o = run({**base, "added": ["ufw allow 443/tcp", rule("10.99.0.0/24").replace("proto tcp", "proto udp"), "ufw deny from 10.99.0.0/24 to any port 22 proto tcp",
                                 "ufw allow from 10.99.0.0/24", "ufw allow from 10.99.0.0/24 to any port 22 proto tcp comment 'x' extra"]})
check("5) biçime uymayan kurallar (443, udp, deny, portsuz) yok sayılır", [], o.get("stale"))

rc, o = run({**base, "added": [rule("10.99.0.0/24", 22, " comment 'hardening-ssh'")]})
check("6) comment ekli kural da ayrıştırılır", [{"src": "10.99.0.0/24", "port": "22"}], o.get("stale"))

rc, o = run({**base, "extra_allow": ["from 10.99.0.0/24 to any port 22 proto tcp"], "added": [rule("10.99.0.0/24")]})
check("7) extra_allow ile aynı kural silinmez", [], o.get("stale"))

rc, o = run({**base, "controller": "10.99.0.7", "added": [rule("10.1.10.0/24"), rule("10.99.0.0/24")]})
check("8) kontrol makinesinin adresini kapsayan kural SİLİNMEZ (engellenir)", [], o.get("stale"))
check("   ... ve 'blocked' içinde raporlanır", [{"src": "10.99.0.0/24", "port": "22"}], [{"src": b["src"], "port": b["port"]} for b in o.get("blocked", [])])

rc, o = run({**base, "allow_from": ["abc"], "added": [rule("10.99.0.0/24")]})
check("9) allow_from çözülemezse silme yok, hata", ([], True), (o.get("stale"), bool(o.get("error"))))
rc, o = run({**base, "allow_from": [], "added": [rule("10.99.0.0/24")]})
check("10) allow_from BOŞSA silme yok (her şey 'eski' olurdu), hata", ([], True), (o.get("stale"), bool(o.get("error"))))

rc, o = run({**base, "ssh_ports": [22, 2222], "added": [rule("10.99.0.0/24", 2222), rule("10.98.0.0/24", 22), rule("10.1.10.0/24", 2222)]})
check("11) birden çok SSH portu: eski olanlar sıralı, geçerli olan kalır", [{"src": "10.98.0.0/24", "port": "22"}, {"src": "10.99.0.0/24", "port": "2222"}], o.get("stale"))

rc, o = run({**base, "added": [rule("not-an-ip")]})
check("12) çözülemeyen kaynak silinmez, 'skipped' raporlanır", ([], 1), (o.get("stale"), len(o.get("skipped", []))))

rc, o = run({**base, "controller": "", "added": [rule("10.99.0.0/24")]})
check("13) kontrol makinesi adresi bilinmiyorsa silme yok (güvenli taraf), hata", ([], True), (o.get("stale"), bool(o.get("error"))))


# --- missing: allow_from'daki her ağ x SSH portu için kural olmalı (silmeden SONRA doğrulama; yoksa ufw enable'dan önce durulur)
rc, o = run({**base, "added": [rule("10.1.10.0/24")]})
check("14) missing: tüm allow_from kuralları var -> boş", [], o.get("missing"))
rc, o = run({**base, "allow_from": ["10.1.10.0/24", "10.2.0.0/16"], "added": [rule("10.1.10.0/24")]})
check("15) missing: 10.2.0.0/16 kuralı yok -> raporlanır", [{"src": "10.2.0.0/16", "port": "22"}], o.get("missing"))
rc, o = run({**base, "allow_from": ["10.0.0.9/32"], "controller": "10.0.0.9", "added": [rule("10.0.0.9")]})
check("16) missing normalleştirme: 10.0.0.9/32 ile ufw'deki 10.0.0.9 aynı -> boş", [], o.get("missing"))
rc, o = run({**base, "ssh_ports": [22, 2222], "added": [rule("10.1.10.0/24", 22)]})
check("17) missing: 2222 portu için kural yok -> raporlanır", [{"src": "10.1.10.0/24", "port": "2222"}], o.get("missing"))
rc, o = run({**base, "allow_from": [], "added": []})
check("18) hata durumunda missing de boş döner (karar verilmez)", ([], True), (o.get("missing"), bool(o.get("error"))))

sys.exit(1 if fails else 0)
