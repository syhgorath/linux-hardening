#!/usr/bin/env python3
"""hardening_pve_firewall: `pve_firewall_plan.py` karar mantığı. Hiçbir şey yazılmaz; reddedilen her durumda içerik BOŞ döner (hiçbir şey yazılamaz)."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "roles/hardening_pve_firewall/files/pve_firewall_plan.py"
fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail}")


def run(cfg):
    arg = cfg if isinstance(cfg, str) else json.dumps(cfg)
    r = subprocess.run([sys.executable, str(SCRIPT), arg], capture_output=True, text=True)
    return json.loads(r.stdout)


OK = {"clustered": False, "allow_from": ["192.0.2.0/24", "198.51.100.7"], "client_ip": "192.0.2.10", "existing": None, "extra_ports": [], "ssh_port": 22, "web_port": 8006}


def with_(**kw):
    d = dict(OK)
    d.update(kw)
    return d


r = run(OK)
check("tek dugum + gecerli allow_from + kontrol makinesi kapsanir -> apply", r["status"] == "apply" and not r["reasons"], str(r))
c, d = r["content"], r["content_disabled"]
check("icerik: enable 1, policy_in DROP, policy_out ACCEPT", "enable: 1\n" in c and "policy_in: DROP" in c and "policy_out: ACCEPT" in c)
check("on dogrulama icerigi enable: 0 ve aksi halde AYNI", "enable: 0\n" in d and d.replace("enable: 0", "enable: 1") == c)
check("management IP kumesi allow_from'dan (tekil adres /32)", "[IPSET management]\n192.0.2.0/24\n198.51.100.7/32\n" in c, c)
check("local_network alias YONETIM agi (Proxmox yoksa yerel agi management kumesine kendisi ekler); IPv4 one alinir", "[ALIASES]\nlocal_network 192.0.2.0/24\n" in c and "[ALIASES]\nlocal_network 192.0.2.0/24\n" in run(with_(allow_from=["2001:db8::/64", "192.0.2.0/24"], client_ip="192.0.2.10"))["content"] and "local_network 2001:db8::/64" in run(with_(allow_from=["2001:db8::/64"], client_ip="2001:db8::5"))["content"])
check("SSH, 8006 ve icmp yalniz +management kaynagindan", all(x in c for x in ("IN ACCEPT -p tcp -dport 22 -source +management", "IN ACCEPT -p tcp -dport 8006 -source +management", "IN ACCEPT -p icmp -source +management")))
check("kaynaksiz (herkese acik) ACCEPT kurali YOK", all("-source +management" in l for l in c.splitlines() if l.startswith("IN ")))
check("isaret satiri var", c.startswith("# hardening-managed:"))
check("ek portlar kurala eklenir (aralik ve udp)", "-p tcp -dport 3128 -source +management" in run(with_(extra_ports=["3128/tcp"]))["content"] and "-p udp -dport 8000:8010 -source +management" in run(with_(extra_ports=["8000:8010/udp"]))["content"])
check("ipv6 ag ve ipv6 istemci", run(with_(allow_from=["2001:db8::/64"], client_ip="2001:db8::5"))["status"] == "apply")

refuse = lambda cfg: run(cfg)
for name, cfg in {
    "kume": with_(clustered=True),
    "allow_from bos": with_(allow_from=[]),
    "allow_from liste degil": with_(allow_from="192.0.2.0/24"),
    "allow_from tanimsiz": {k: v for k, v in OK.items() if k != "allow_from"},
    "gecersiz ag": with_(allow_from=["not-a-net"]),
    "kontrol makinesi kapsanmiyor": with_(client_ip="203.0.113.9"),
    "istemci adresi okunamadi": with_(client_ip=""),
    "ipv6 istemci, yalniz ipv4 ag": with_(client_ip="2001:db8::5"),
    "gecersiz ek port": with_(extra_ports=["abc"]),
    "ek port 70000": with_(extra_ports=["70000/tcp"]),
    "ek port ters aralik": with_(extra_ports=["9000:8000/tcp"]),
    "ek port protokolsuz": with_(extra_ports=["443"]),
    "ssh_port 0": with_(ssh_port=0),
    "kullanici kurali": with_(existing="[OPTIONS]\nenable: 1\n\n[RULES]\nIN ACCEPT -p tcp -dport 80\n"),
    "kullanici dosyasi (yalniz OPTIONS)": with_(existing="[OPTIONS]\nlog_ratelimit: enable=1\n"),
}.items():
    x = refuse(cfg)
    check(f"{name} -> refuse, icerik BOS (hicbir sey yazilamaz)", x["status"] == "refuse" and x["content"] == "" and x["content_disabled"] == "" and x["reasons"], str(x))

check("bos/yorum-only mevcut dosya kullanicinin sayilmaz -> apply", run(with_(existing="# bos\n\n"))["status"] == "apply")
check("bos string mevcut dosya -> apply", run(with_(existing=""))["status"] == "apply")
managed = run(OK)["content"]
check("kendi isaretimiz olan dosya guncellenebilir (farkli icerik -> apply)", run(with_(existing=managed.replace("enable: 1", "enable: 0")))["status"] == "apply")
check("ayni icerik -> noop (ikinci kosu changed=0)", run(with_(existing=managed))["status"] == "noop")
check("isaretli dosyaya kullanici kurali eklenmis olsa da isaret varsa guncellenir (isaret = bu rolun)", run(with_(existing=managed + "IN ACCEPT -p tcp -dport 80\n"))["status"] == "apply")
check("sondaki ek bos satir farki noop sayilir (pmxcfs/tee yeni satir ekleyebilir)", run(with_(existing=managed + "\n"))["status"] == "noop")
check("bozuk girdi -> refuse, cokmez", run("{bozuk")["status"] == "refuse" and run("[1]")["status"] == "refuse")
check("birden cok neden birikir", len(run(with_(clustered=True, allow_from=[]))["reasons"]) >= 2)

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
