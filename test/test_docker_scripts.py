#!/usr/bin/env python3
"""hardening_docker: karar betikleri (docker_report.py, docker_daemon_merge.py). Gerçek Docker gerekmez; girdiler `docker ps --format` ve daemon.json biçimindedir.

Asıl hedefler: (1) yayınlanan portların izinli listeyle doğru karşılaştırılması (127.0.0.1 ve yayınlanmamış portlar uyarı DEĞİL; IPv4+IPv6 çifti tek kez), (2) docker grubu / TCP API / tehlikeli
daemon.json ayarlarının uyarıya dönüşmesi, (3) birleştirmenin kullanıcının ayarlarını ASLA silmemesi, geçersiz JSON'a dokunmaması ve idempotent olması.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "roles/hardening_docker/files/docker_report.py"
MERGE = ROOT / "roles/hardening_docker/files/docker_daemon_merge.py"
fails = 0


def check(name, want, got):
    global fails
    if want == got:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}: beklenen={want!r} gercek={got!r}")


def run(script, cfg):
    arg = cfg if isinstance(cfg, str) else json.dumps(cfg)
    r = subprocess.run([sys.executable, str(script), arg], capture_output=True, text=True)
    try:
        return r.returncode, json.loads(r.stdout)
    except ValueError:
        return r.returncode, {"_ham": r.stdout, "_err": r.stderr}


base = {"group_members": [], "ports": [], "listening": [], "daemon": None, "daemon_error": "", "allowed_published": [80, 443]}
PROXY = "proxy|0.0.0.0:80->80/tcp, :::80->80/tcp, 0.0.0.0:443->443/tcp, :::443->443/tcp"

# ---------- docker_report.py ----------
rc, o = run(REPORT, base)
check("1) bos girdi: ok, cikis 0, uyari yok", (0, "ok", []), (rc, o.get("status"), o.get("warnings")))
rc, o = run(REPORT, {**base, "ports": [PROXY, "db|3306/tcp", "app|127.0.0.1:8080->80/tcp"]})
check("2) yalniz izinli 80/443 herkese yayinli, db yayinlanmamis, app loopback: uyari YOK", ("ok", []), (o.get("status"), o.get("published")))
rc, o = run(REPORT, {**base, "ports": [PROXY, "redis|0.0.0.0:6379->6379/tcp, :::6379->6379/tcp"]})
check("3) izinli listede olmayan 6379 herkese yayinli: warn, tek kez (IPv4+IPv6 cifti)", ("warn", ["redis:6379/tcp"]), (o.get("status"), o.get("published")))
check("   mesaj ufw'yi atlama bilgisini icerir", True, "ufw" in " ".join(o.get("warnings", [])))
rc, o = run(REPORT, {**base, "ports": ["x|0.0.0.0:8000-8002->8000-8002/tcp"]})
check("4) port araligi acilir (8000-8002 -> 3 port)", ["x:8000/tcp", "x:8001/tcp", "x:8002/tcp"], sorted(o.get("published")))
rc, o = run(REPORT, {**base, "ports": ["a|[::1]:9000->9000/tcp", "b|[::]:9001->9001/tcp"]})
check("5) IPv6 loopback ([::1]) uyari degil, [::] (herkes) uyari", ["b:9001/tcp"], o.get("published"))
rc, o = run(REPORT, {**base, "allowed_published": [], "ports": [PROXY]})
check("6) izinli liste bos iken 80/443 de uyari", 2, len(set(p.split(":")[1].split("/")[0] for p in o.get("published"))))
rc, o = run(REPORT, {**base, "ports": ["u|0.0.0.0:53->53/udp"]})
check("7) udp portu da yakalanir", ["u:53/udp"], o.get("published"))

rc, o = run(REPORT, {**base, "group_members": ["alice", "bob"]})
check("8) docker grubu uyesi: warn ve adlar", ("warn", True), (o.get("status"), "alice, bob" in " ".join(o.get("warnings", []))))
rc, o = run(REPORT, {**base, "listening": ["0.0.0.0:2375"]})
check("9) TLS'siz TCP API 2375 dis arayuzde: warn", "warn", o.get("status"))
rc, o = run(REPORT, {**base, "listening": ["127.0.0.1:2375"]})
check("   2375 yalniz loopback'te: uyari degil", "ok", o.get("status"))
rc, o = run(REPORT, {**base, "listening": ["0.0.0.0:2376"]})
check("   2376 (TLS) not, uyari degil", ("ok", True), (o.get("status"), bool(o.get("notes"))))
for label, daemon, frag in (("iptables:false", {"iptables": False}, "iptables"), ("experimental:true", {"experimental": True}, "experimental"),
                            ("insecure-registries", {"insecure-registries": ["10.0.0.5:5000"]}, "insecure"), ("hosts tcp://", {"hosts": ["tcp://0.0.0.0:2375"]}, "tcp://")):
    rc, o = run(REPORT, {**base, "daemon": daemon})
    check(f"10) daemon.json {label}: warn", (True, "warn"), (frag in " ".join(o.get("warnings", [])), o.get("status")))
rc, o = run(REPORT, {**base, "daemon": {"live-restore": True, "log-opts": {"max-size": "10m"}}})
check("11) saglikli daemon.json: ok ve not yok", ("ok", []), (o.get("status"), o.get("notes")))
rc, o = run(REPORT, {**base, "daemon": {}})
check("    live-restore ve log boyutu yoksa yalniz NOT (uyari degil)", ("ok", 2), (o.get("status"), len(o.get("notes"))))
rc, o = run(REPORT, {**base, "daemon_text": '{"iptables": false, "live-restore": true, "log-opts": {"max-size": "5m"}}'})
check("11b) daemon_text (ham metin) cozulur ve ayni kurallar uygulanir", ("warn", True), (o.get("status"), "iptables" in " ".join(o.get("warnings", []))))
rc, o = run(REPORT, {**base, "daemon_text": "{ bozuk"})
check("11c) daemon_text gecersiz JSON: warn (Docker bu dosyayla baslamaz)", ("warn", True), (o.get("status"), "BAŞLAMAZ" in " ".join(o.get("warnings", []))))
rc, o = run(REPORT, {**base, "daemon_text": "[1]"})
check("11d) daemon_text nesne degil: warn", "warn", o.get("status"))
rc, o = run(REPORT, {**base, "daemon_text": ""})
check("11e) daemon_text bos: not (varsayilanlar), uyari degil", ("ok", True), (o.get("status"), bool(o.get("notes"))))
rc, o = run(REPORT, {**base, "daemon_error": "izin yok"})
check("12) daemon.json okunamazsa not, calismaya devam", ("ok", True), (o.get("status"), "okunamad" in " ".join(o.get("notes", []))))
rc, o = run(REPORT, "bu json degil")
check("13) bozuk girdi: unknown + hata, cikis 0", (0, "unknown", True), (rc, o.get("status"), bool(o.get("error"))))
rc, o = run(REPORT, {**base, "allowed_published": ["abc"]})
check("    izinli liste sayi degilse unknown", "unknown", o.get("status"))

# ---------- docker_daemon_merge.py ----------
S = {"live-restore": True, "log-driver": "json-file", "log-opts": {"max-size": "10m", "max-file": "3"}}
rc, o = run(MERGE, {"existing": "", "settings": S})
new = json.loads(o["text"])
check("14) dosya yok/bos: ayarlar yazilir", (True, S), (o["changed"], new))
rc, o = run(MERGE, {"existing": '{"data-root": "/srv/docker", "registry-mirrors": ["https://m.example"]}', "settings": S})
new = json.loads(o["text"])
check("15) mevcut ayarlar KORUNUR (data-root, registry-mirrors)", ("/srv/docker", ["https://m.example"], True), (new["data-root"], new["registry-mirrors"], new["live-restore"]))
rc, o = run(MERGE, {"existing": '{"log-opts": {"labels": "env", "max-size": "1g"}}', "settings": S})
text1 = o["text"]
new = json.loads(text1)
check("16) sozluk degerleri birlesir: mevcut alt anahtar (labels) korunur, istenen (max-size) uzerine yazilir", {"labels": "env", "max-size": "10m", "max-file": "3"}, new["log-opts"])
rc, o = run(MERGE, {"existing": text1, "settings": S})
check("17) ikinci kosu: changed=false ve metin ayni (idempotent)", (False, text1), (o["changed"], o["text"]))
rc, o = run(MERGE, {"existing": '{"live-restore": true, "log-driver": "json-file", "log-opts": {"max-size": "10m", "max-file": "3"}}', "settings": S})
check("    zaten uygun dosya: changed=false", False, o["changed"])
rc, o = run(MERGE, {"existing": '{"live-restore": false}', "settings": {"live-restore": True}})
check("18) mevcut deger degisir (live-restore false -> true)", (True, True), (o["changed"], json.loads(o["text"])["live-restore"]))
orig = "{ bozuk json"
rc, o = run(MERGE, {"existing": orig, "settings": S})
check("19) gecersiz JSON: error, changed=false, metin DEGISMEZ", (False, True, orig), (o["changed"], bool(o["error"]), o["text"]))
rc, o = run(MERGE, {"existing": '["liste"]', "settings": S})
check("20) JSON nesne degilse (liste): error ve dokunulmaz", (False, True), (o["changed"], bool(o["error"])))
rc, o = run(MERGE, {"existing": "{}", "settings": "nesne degil"})
check("21) settings nesne degilse error", True, bool(o["error"]))
rc, o = run(MERGE, "bu json degil")
check("22) bozuk girdi: error, cikis 0", (0, True), (rc, bool(o.get("error"))))
rc, o = run(MERGE, {"existing": '{"a": 1}', "settings": {}})
check("23) bos settings: degisiklik yok", False, o["changed"])
rc, o = run(MERGE, {"existing": "  \n", "settings": {"experimental": False}})
check("24) yalniz bosluk: bos sayilir", (True, {"experimental": False}), (o["changed"], json.loads(o["text"])))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
