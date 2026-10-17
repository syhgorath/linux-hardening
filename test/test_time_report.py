#!/usr/bin/env python3
"""hardening_time: `roles/hardening_time/files/time_report.py` (salt okunur zaman raporu; davranışı DEĞİŞTİRMEZ).

Karar mantığı tek betikte olduğu için gerçek bir sunucu gerekmeden denenir. Fixture'lar test VM'inde `chronyc -c sources` ile alınan GERÇEK çıktı biçimindedir
(mod,durum,ad,katman,poll,reach,lastrx,ayarlı_ofset,ölçülen_ofset,hata). Asıl hedef, snapshot dönüşünde yaşanan durumu yakalamak:
`timedatectl` "synchronized: yes" derken saatin günlerce kayık olması (kaynaklar `?`, ofset ~ -714420 sn).
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "roles/hardening_time/files/time_report.py"
fails = 0


def check(name, want, got):
    global fails
    if want == got:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}: beklenen={want!r} gercek={got!r}")


def run(cfg):
    arg = cfg if isinstance(cfg, str) else json.dumps(cfg)
    r = subprocess.run([sys.executable, str(SCRIPT), arg], capture_output=True, text=True)
    try:
        return r.returncode, json.loads(r.stdout)
    except ValueError:
        return r.returncode, {"_ham": r.stdout, "_err": r.stderr}


HEALTHY = [
    "^,*,185.125.190.122,2,9,377,29,0.000666793,0.001044883,0.037564151",
    "^,+,185.125.190.123,2,7,377,32,0.000416195,0.000794150,0.038205650",
    "^,+,91.189.91.112,2,9,377,36,0.001633003,0.002010757,0.087522641",
    "^,-,185.125.190.121,2,9,377,483,-0.002289361,-0.001933929,0.040119708",
]
STALE = [  # snapshot dönüşü: tüm kaynaklar '?' ve ofset ~ -8,27 gün
    "^,?,185.125.190.122,2,6,377,20,-714420.5,-714420.5,0.038",
    "^,?,185.125.190.123,2,6,377,21,-714420.4,-714420.4,0.037",
    "^,?,91.189.91.112,0,6,0,0,0.0,0.0,0.0",
]
base = {"service": "active", "sources": HEALTHY, "ntp_synchronized": "yes", "max_offset": 5}

rc, o = run(base)
check("1) sağlıklı: status ok", "ok", o.get("status"))
check("   çıkış 0", 0, rc)
check("   seçili kaynak var, 4 kaynak / 4 ulaşılabilir", (True, 4, 4), (o.get("selected"), o.get("sources"), o.get("reachable")))
check("   en büyük ofset ~2.3 ms", True, abs((o.get("max_offset") or 0) - 0.002289361) < 1e-9)
check("   uyarı mesajı yok", [], o.get("messages"))

rc, o = run({**base, "sources": STALE})
check("2) BAYAT durum (kaynaklar ?, ~8 gün ofset): status warn", "warn", o.get("status"))
msgs = " ".join(o.get("messages", []))
check("   mesaj: günlerle ifade edilen kayma", True, "gün" in msgs)
check("   mesaj: 'synchronized: yes' yanıltıcı uyarısı", True, "yanıltıcı" in msgs)
check("   mesaj: seçili kaynak yok", True, "seçil" in msgs)
check("   mesaj: çözüm önerisi (restart chrony)", True, "restart chrony" in msgs)
check("   en büyük ofset ~714420 sn", True, abs((o.get("max_offset") or 0) - 714420.5) < 1e-6)

rc, o = run({**base, "sources": STALE, "ntp_synchronized": "no"})
check("3) senkron 'no' iken 'yanıltıcı' uyarısı eklenmez", False, "yanıltıcı" in " ".join(o.get("messages", [])))

rc, o = run({**base, "service": "inactive"})
check("4) zaman servisi çalışmıyor: warn", ("warn", True), (o.get("status"), "çalışm" in " ".join(o.get("messages", []))))
rc, o = run({**base, "service": "failed"})
check("   failed da warn", "warn", o.get("status"))

rc, o = run({**base, "sources": []})
check("5) kaynak yok: warn", "warn", o.get("status"))

rc, o = run({**base, "sources": ["^,?,a.example,2,6,0,0,0.0,0.0,0.0", "^,?,b.example,2,6,0,0,0.0,0.0,0.0"]})
check("6) hiçbir kaynağa ulaşılamıyor (reach 0): warn", ("warn", 0), (o.get("status"), o.get("reachable")))

src3 = ["^,*,a.example,2,6,377,5,3.0,3.0,0.01"]
rc, o = run({**base, "sources": src3, "max_offset": 5})
check("7) ofset 3 sn, eşik 5: ok", "ok", o.get("status"))
rc, o = run({**base, "sources": ["^,*,a.example,2,6,377,5,8.0,8.0,0.01"], "max_offset": 5})
check("   ofset 8 sn, eşik 5: warn", "warn", o.get("status"))
rc, o = run({**base, "sources": src3, "max_offset": 1})
check("   ofset 3 sn, eşik 1: warn", "warn", o.get("status"))
rc, o = run({**base, "sources": ["^,*,a.example,2,6,377,5,-8.0,-8.0,0.01"], "max_offset": 5})
check("   negatif ofset (-8 sn) da mutlak değerle: warn", "warn", o.get("status"))

rc, o = run({**base, "sources": ["^,*,a.example,2,6,377,5,0.001,0.001,0.01", "bozuk satir", "", "^,+,b"]})
check("8) bozuk satırlar atlanır, geçerli kaynak değerlendirilir", ("ok", 1), (o.get("status"), o.get("sources")))
rc, o = run({**base, "sources": ["bozuk", "x,y"]})
check("   hepsi bozuksa kaynak yok sayılır: warn", "warn", o.get("status"))

rc, o = run({**base, "sources": ["^,+,a.example,2,6,377,5,0.001,0.001,0.01"]})
check("9) hiç '*' (seçili) kaynak yok, ofset küçük: warn (senkron değil)", ("warn", False), (o.get("status"), o.get("selected")))

rc, o = run("bu json degil")
check("10) girdi okunamazsa unknown + hata, çıkış 0", (0, "unknown", True), (rc, o.get("status"), bool(o.get("error"))))
rc, o = run({**base, "max_offset": "abc"})
check("    eşik sayı değilse unknown + hata", ("unknown", True), (o.get("status"), bool(o.get("error"))))

sys.exit(1 if fails else 0)
