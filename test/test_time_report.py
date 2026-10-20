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

# 11) GERÇEK vaka (test VM'i, snapshot dönüşü): saat ~8 gün geride, ama kaynaklar '~' (çok değişken) ve ofset yalnızca -9,2 sn gösterdi, '*' yok.
TILDE = [
    "^,~,185.125.190.122,2,6,377,44,-9.224942207,-9.224942207,0.036573015",
    "^,~,185.125.190.123,2,6,377,46,-9.226245880,-9.226245880,0.037203822",
    "^,~,91.189.91.112,2,6,377,49,-9.225152969,-9.225152969,0.089674123",
]
rc, o = run({**base, "sources": TILDE})
m = " ".join(o.get("messages", []))
check("11) '~' kaynaklar, seçili yok: warn", "warn", o.get("status"))
check("    ofset 'kesin kayma' diye YAZILMAZ (güvenilmez denir)", (True, False), ("GÜVENİLMEZ" in m, "Saat kaynaklara göre" in m))
check("    'hiçbir kaynak seçilmedi' ve düzeltme önerisi", (True, True), ("seçilmedi" in m, "restart chrony" in m))
NOW = 1792000000
rc, o = run({**base, "sources": TILDE, "controller_epoch": NOW, "target_epoch": NOW - 8 * 86400 - 3600})
m = " ".join(o.get("messages", []))
check("    kontrol makinesi çapraz kontrolü gerçek kaymayı yakalar (~8 gün geride)", (True, True, True), ("8 gün" in m, "geride" in m, "kontrol makinesi" in m))
check("    ...ve kontrol makinesinin de yanlış olabileceğini söyler", True, "yanlış olabilir" in m)

rc, o = run({**base, "controller_epoch": NOW, "target_epoch": NOW - 8 * 86400})
check("12) kaynaklar sağlıklı ama sunucu saati 8 gün geride: yine warn", ("warn", True), (o.get("status"), "8 gün" in " ".join(o.get("messages", []))))
m = " ".join(o.get("messages", []))
check("    düzeltme önerisi ve 'synchronized: yes yanıltıcı' notu da gelir", (True, True), ("restart chrony" in m, "yanıltıcı" in m))
rc, o = run({**base, "controller_epoch": NOW, "target_epoch": NOW + 2 * 3600})
check("    ileride ise 'ileride' yazar", True, "ileride" in " ".join(o.get("messages", [])))
rc, o = run({**base, "controller_epoch": NOW, "target_epoch": NOW - 2})
check("13) 2 sn fark (komut/ağ gecikmesi): uyarı YOK", "ok", o.get("status"))
rc, o = run({**base, "controller_epoch": NOW, "target_epoch": NOW - 29})
check("    29 sn fark (30 sn alt sınırının altında): uyarı YOK", "ok", o.get("status"))
rc, o = run({**base, "controller_epoch": NOW, "target_epoch": NOW - 31})
check("    31 sn fark: uyarı", "warn", o.get("status"))
rc, o = run({**base, "max_offset": 120, "controller_epoch": NOW, "target_epoch": NOW - 100})
check("    eşik 120 sn iken 100 sn fark: uyarı YOK (eşik 30'dan büyükse eşik kullanılır)", "ok", o.get("status"))
for label, extra in (("epoch yok", {}), ("boş metin", {"controller_epoch": "", "target_epoch": ""}), ("sayı değil", {"controller_epoch": "x", "target_epoch": "y"}),
                     ("yalnız biri", {"controller_epoch": NOW})):
    rc, o = run({**base, **extra})
    check(f"14) çapraz kontrol atlanır ({label}): ok ve çökme yok", (0, "ok"), (rc, o.get("status")))
rc, o = run({**base, "service": "inactive", "controller_epoch": NOW, "target_epoch": NOW - 86400})
check("15) servis kapalıyken de saat farkı raporlanır", True, "gün" in " ".join(o.get("messages", [])))
rc, o = run({**base, "sources": [], "controller_epoch": NOW, "target_epoch": NOW - 86400})
check("    kaynak yokken de", True, "gün" in " ".join(o.get("messages", [])))

rc, o = run("bu json degil")
check("10) girdi okunamazsa unknown + hata, çıkış 0", (0, "unknown", True), (rc, o.get("status"), bool(o.get("error"))))
rc, o = run({**base, "max_offset": "abc"})
check("    eşik sayı değilse unknown + hata", ("unknown", True), (o.get("status"), bool(o.get("error"))))

# 16) `fix` alanı: raporun önerdiği düzeltme (betik hiçbir şey çalıştırmaz)
rc, o = run(base)
check("16) sağlıklı: fix boş", "", o.get("fix"))
rc, o = run({**base, "sources": ["^,*,a.example,2,6,377,5,-8.0,-8.0,0.01"], "max_offset": 5})
check("    kaynak SEÇİLİ ve ofset büyük: fix=makestep", "makestep", o.get("fix"))
rc, o = run({**base, "sources": STALE})
check("    kaynaklar '?' (seçili yok), ofset büyük: fix=restart (makestep etkisiz kalırdı)", "restart", o.get("fix"))
rc, o = run({**base, "sources": TILDE, "controller_epoch": NOW, "target_epoch": NOW - 8 * 86400})
check("    '~' kaynaklar + sunucu saati 8 gün geride: fix=restart", "restart", o.get("fix"))
rc, o = run({**base, "controller_epoch": NOW, "target_epoch": NOW - 8 * 86400})
check("    kaynaklar sağlıklı ama sunucu saati geride: fix=makestep", "makestep", o.get("fix"))
rc, o = run({**base, "service": "inactive"})
check("    servis çalışmıyor: fix BOŞ (saat düzeltilemez)", "", o.get("fix"))
rc, o = run({**base, "sources": []})
check("    kaynak yok: fix boş", "", o.get("fix"))
rc, o = run({**base, "sources": ["^,?,a.example,2,6,0,0,0.0,0.0,0.0"]})
check("    hiçbir kaynağa ulaşılamıyor: fix boş", "", o.get("fix"))
rc, o = run({**base, "sources": ["^,+,a.example,2,6,377,5,0.001,0.001,0.01"]})
check("    yalnız 'seçili kaynak yok' ama ofset küçük: fix boş (sıçratmaya gerek yok)", "", o.get("fix"))
rc, o = run("bu json degil")
check("    girdi okunamazsa fix boş", "", o.get("fix"))

sys.exit(1 if fails else 0)
