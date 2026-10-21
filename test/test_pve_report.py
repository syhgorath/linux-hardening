#!/usr/bin/env python3
"""hardening_pve_report: `roles/hardening_pve_report/files/pve_report.py` (Proxmox VE host durumu; SALT OKUNUR, hiçbir şeyi DEĞİŞTİRMEZ).

Ana fixture, iç içe Proxmox VE 9.2.21 VM'inden (2026-10-21) alınan GERÇEK değerlerdir (adresler anonim): firewall `disabled/running`, PermitRootLogin yes, postfix + pve-manager'ın MTA bağımlılığı,
rpcbind/spiceproxy dinleyicileri, 0 VM / 0 CT, abonelik yok."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "roles/hardening_pve_report/files/pve_report.py"
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
    try:
        return r.returncode, json.loads(r.stdout)
    except ValueError:
        return r.returncode, {"_ham": r.stdout, "_err": r.stderr}


REAL = {
    "pveversion": "pve-manager/9.2.21/4f6e0ac86f9e8c7f (running kernel: 7.0.14-25-pve)", "clustered": False, "firewall": "Status: disabled/running",
    "services": {"pve-cluster": "active", "pvedaemon": "active", "pveproxy": "active", "pvestatd": "active", "pve-firewall": "active"},
    "listening": ["127.0.0.1:85", "0.0.0.0:111", "0.0.0.0:22", "127.0.0.1:25", "[::1]:25", "*:8006", "*:3128", "[::]:111", "[::]:22"],
    "sshd": {"permitrootlogin": "yes", "passwordauthentication": "yes"}, "postfix": True, "pve_needs_mta": True, "ufw_installed": False,
    "qemu_count": 0, "lxc_count": 0, "enterprise_repo_enabled": False, "no_subscription_repo": True, "subscription": "notfound",
}


def txt(o, k="warnings"):
    return " ".join(o.get(k, []))


rc, o = run(REAL)
check("1) gercek Proxmox: cikis 0, status warn (firewall kapali, root SSH)", (0, "warn"), (rc, o.get("status")))
check("   surum 9.2.21 ve ozet (tek dugum, firewall devre disi, 0 VM / 0 CT)", ("9.2.21", True), (o.get("version"), "tek düğüm" in o.get("summary", "") and "devre dışı" in o.get("summary", "") and "0 VM / 0 CT" in o.get("summary", "")))
check("   uyari: pve-firewall DEVRE DISI", "DEVRE DIŞI" in txt(o))
check("   uyari: root SSH + parola acik", "PermitRootLogin yes" in txt(o) and "Parola da açık" in txt(o))
check("   not: postfix -> dma degisimi YAPILMAMALI (pve-manager MTA'ya bagimli)", "postfix -> dma" in txt(o, "notes") and "pve-manager ve proxmox-ve" in txt(o, "notes"))
check("   not: rpcbind ve spiceproxy; 22/8006 ve loopback dinleyiciler UYARI/NOT uretmez", "rpcbind" in txt(o, "notes") and "spiceproxy" in txt(o, "notes") and ":22" not in txt(o) + txt(o, "notes") and "8006" not in txt(o, "notes") and "127.0.0.1" not in txt(o, "notes"))
check("   not: ufw kurulu degil, tek dugum, abonelik/no-subscription", "ufw kurulu değil" in txt(o, "notes") and "Tek düğüm" in txt(o, "notes") and "no-subscription" in txt(o, "notes"))
check("   rpcbind notu tekrar etmez (IPv4 + IPv6 satiri tek not)", txt(o, "notes").count("rpcbind") == 1)

rc, o = run({**REAL, "firewall": "Status: enabled/running"})
check("2) firewall etkin: firewall uyarisi YOK; ozet 'etkin'", ("DEVRE DIŞI" not in txt(o), "pve-firewall: etkin" in o.get("summary", "")))
rc, o = run({**REAL, "firewall": "Status: enabled/running", "sshd": {"permitrootlogin": "no", "passwordauthentication": "no"}})
check("   firewall etkin + SSH sikilastirilmis: status ok, uyari yok", ("ok", []), (o.get("status"), o.get("warnings")))
rc, o = run({**REAL, "firewall": "Status: enabled/running", "sshd": {"permitrootlogin": "prohibit-password", "passwordauthentication": "no"}})
check("   root SSH anahtarla (prohibit-password): hala uyari (root girisi acik)", "prohibit-password" in txt(o))
rc, o = run({**REAL, "firewall": "Status: enabled/running", "sshd": {"permitrootlogin": "no", "passwordauthentication": "yes"}})
check("   yalniz parola acik: ayri uyari", "PasswordAuthentication yes" in txt(o) and "PermitRootLogin" not in txt(o))
rc, o = run({**REAL, "firewall": ""})
check("   firewall durumu okunamadi: uyari YOK, ozet 'bilinmiyor'", ("DEVRE DIŞI" not in txt(o), "bilinmiyor" in o.get("summary", "")))

rc, o = run({**REAL, "ufw_installed": True})
check("3) ufw kurulu: UYARI (pve-firewall ile cakisir)", "ufw kurulu: Proxmox'ta güvenlik duvarı pve-firewall" in txt(o))
rc, o = run({**REAL, "postfix": False})
check("   postfix yoksa dma notu YOK", "postfix -> dma" not in txt(o, "notes"))
rc, o = run({**REAL, "clustered": True})
check("   kume: root SSH notu, 'Tek dugum' YOK", "Küme düğümü" in txt(o, "notes") and "Tek düğüm" not in txt(o, "notes") and "küme" in o.get("summary", ""))
rc, o = run({**REAL, "qemu_count": "3", "lxc_count": 2})
check("   VM/CT sayisi (metin ve int): yedekleme notu", "3 VM ve 2 konteyner" in txt(o, "notes") and "3 VM / 2 CT" in o.get("summary", ""))
rc, o = run({**REAL, "listening": REAL["listening"] + ["0.0.0.0:25"]})
check("   MTA 0.0.0.0:25 dinliyor: UYARI", "MTA (port 25)" in txt(o))
rc, o = run({**REAL, "listening": REAL["listening"] + ["0.0.0.0:9999"]})
check("   beklenmeyen dinleyici: not", "Beklenmeyen dinleyici: 0.0.0.0:9999" in txt(o, "notes"))
rc, o = run({**REAL, "services": {**REAL["services"], "pveproxy": "inactive"}})
check("   pveproxy calismiyor: UYARI", "pveproxy" in txt(o) and "inactive" in txt(o))
rc, o = run({**REAL, "services": {k: v for k, v in REAL["services"].items() if k != "pvestatd"}})
check("   servis bilgisi yoksa uyari uretilmez (okunamadi != calismiyor)", "pvestatd" not in txt(o))
rc, o = run({**REAL, "services": {**REAL["services"], "pvedaemon": "unknown"}})
check("   servis durumu 'unknown' (okunamadi): uyari uretilmez", "pvedaemon" not in txt(o))
rc, o = run({**REAL, "enterprise_repo_enabled": True})
check("   pve-enterprise etkin + abonelik yok: 401 uyarisi", "pve-enterprise" in txt(o) and "401" in txt(o))

rc, o = run({**REAL, "pveversion": "Command 'pveversion' not found"})
check("4) Proxmox degil (pveversion yok): unknown + hata, cikis 0", (0, "unknown", True), (rc, o.get("status"), bool(o.get("error"))))
rc, o = run("bu json degil")
check("   girdi okunamazsa unknown + hata, cikis 0", (0, "unknown", True), (rc, o.get("status"), bool(o.get("error"))))
rc, o = run({})
check("   bos girdi: unknown, cokme yok", (0, "unknown"), (rc, o.get("status")))
rc, o = run({**REAL, "qemu_count": "x", "lxc_count": None})
check("   qemu_count/lxc_count sayi degil ya da bos: cokmez, 0 sayilir", (0, "0 VM / 0 CT"), (rc, "0 VM / 0 CT" in o.get("summary", "") and "0 VM / 0 CT" or o.get("summary")))
sys.exit(1 if fails else 0)
