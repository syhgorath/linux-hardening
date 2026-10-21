#!/usr/bin/env python3
"""Proxmox VE host durumu raporu (SALT OKUNUR; hiçbir şeyi değiştirmez, yalnızca karar verir).

Girdi (argv[1], JSON): pveversion (`pveversion` ilk satırı), clustered (bool), firewall (`pve-firewall status` ilk satırı), services ({birim: durum}), listening (`ss -H -ltn` yerel adresleri,
`adres:port`), sshd ({permitrootlogin, passwordauthentication}), postfix (bool: kurulu mu), pve_needs_mta (bool: pve-manager bir MTA'ya bağımlı mı), ufw_installed (bool),
qemu_count, lxc_count (int), enterprise_repo_enabled, no_subscription_repo (bool), subscription (`pvesubscription get` durum alanı).
Çıktı (stdout, JSON): status (ok|warn|unknown), summary, warnings, notes, version, error.

Amaç: bu paket Proxmox VE hostunu henüz SERTLEŞTİRMEZ (hardening_preflight reddeder); bu rapor, ileride sertleştirme yazılırken Ubuntu kurallarının nerede ÇAKIŞACAĞINI ve host'un
bugünkü açık yönlerini gösterir. Uyarı (warn): bugün gerçek bir açık ya da bozuk durum. Not (note): sertleştirme tasarımı için bilgi. Python 3.9+ (yalnızca stdlib).
"""
import json
import re
import sys

REQUIRED_SERVICES = ("pve-cluster", "pvedaemon", "pveproxy", "pvestatd")
# Beklenen, herkese açık dinleyiciler: SSH ve web arayüzü. Diğerleri not/uyarı üretir.
EXPECTED_PUBLIC = {"22", "8006"}


def split_addr(entry):
    """'0.0.0.0:111' / '[::]:22' / '*:8006' / '127.0.0.1:25' -> (adres, port)"""
    entry = str(entry).strip()
    if ":" not in entry:
        return entry, ""
    addr, port = entry.rsplit(":", 1)
    return addr.strip("[]"), port


def is_loopback(addr):
    return addr in ("127.0.0.1", "::1") or addr.startswith("127.")


def to_int(value):
    try:
        return int(str(value).strip() or 0)
    except ValueError:
        return 0


def decide(cfg):
    res = {"status": "ok", "summary": "", "warnings": [], "notes": [], "version": "", "error": ""}
    m = re.search(r"pve-manager/([0-9][0-9.]*)", str(cfg.get("pveversion", "")))
    if not m:
        res.update(status="unknown", error="pveversion çıktısı tanınmadı (Proxmox VE değil mi?): %r" % (str(cfg.get("pveversion", ""))[:80],))
        return res
    res["version"] = m.group(1)
    warn, note = res["warnings"], res["notes"]

    fw = str(cfg.get("firewall", "")).strip()
    fw_state = "bilinmiyor"
    if fw:
        low = fw.lower()
        if "disabled" in low:
            fw_state = "devre dışı"
            warn.append("pve-firewall DEVRE DIŞI (%s): yönetim arayüzü (8006) ve SSH güvenlik duvarı olmadan erişilebilir." % fw)
        elif "enabled" in low:
            fw_state = "etkin"
        else:
            note.append("pve-firewall durumu okunamadı: %s" % fw)

    sshd = cfg.get("sshd") or {}
    if str(sshd.get("permitrootlogin", "")).lower() in ("yes", "without-password", "prohibit-password"):
        warn.append("SSH ile root girişi açık (PermitRootLogin %s)." % sshd.get("permitrootlogin") + (" Parola da açık." if str(sshd.get("passwordauthentication", "")).lower() == "yes" else ""))
    elif str(sshd.get("passwordauthentication", "")).lower() == "yes":
        warn.append("SSH parola girişi açık (PasswordAuthentication yes).")

    svc = cfg.get("services") or {}
    for name in REQUIRED_SERVICES:
        if svc.get(name) not in (None, "active", "unknown"):  # okunamayan durum "calismiyor" sayilmaz
            warn.append("Proxmox servisi çalışmıyor: %s (%s)." % (name, svc.get(name)))

    for entry in cfg.get("listening") or []:
        addr, port = split_addr(entry)
        if is_loopback(addr) or port in EXPECTED_PUBLIC or not port:
            continue
        if port == "25":
            warn.append("MTA (port 25) yerel olmayan adreste dinliyor: %s." % entry)
        elif port == "111":
            note.append("rpcbind (port 111) tüm arayüzlerde dinliyor; NFS kullanmıyorsanız gereksizdir.")
        elif port == "3128":
            note.append("spiceproxy (port 3128) tüm arayüzlerde dinliyor (SPICE konsolu).")
        else:
            note.append("Beklenmeyen dinleyici: %s." % entry)
    note[:] = list(dict.fromkeys(note))

    if cfg.get("postfix") and cfg.get("pve_needs_mta"):
        note.append("pve-manager bir MTA'ya bağımlı ve postfix kurulu: `hardening_base`'in postfix -> dma değişimi Proxmox'ta YAPILMAMALI (postfix'i tek başına kaldırmak pve-manager ve proxmox-ve'yi de kaldırır).")
    if cfg.get("ufw_installed"):
        warn.append("ufw kurulu: Proxmox'ta güvenlik duvarı pve-firewall'dur, ufw ile çakışır.")
    else:
        note.append("ufw kurulu değil: Proxmox'ta `hardening_ufw` çalıştırılmamalı, bunun yerine pve-firewall yönetilecek.")
    if cfg.get("clustered"):
        note.append("Küme düğümü: düğümler arası root SSH gerekebilir; `PermitRootLogin no` kümeyi bozabilir.")
    else:
        note.append("Tek düğüm (küme yok).")

    q, c = to_int(cfg.get("qemu_count")), to_int(cfg.get("lxc_count"))
    if q or c:
        note.append("%d VM ve %d konteyner kayıtlı: sertleştirme VM ağını etkileyebilir, önce yedekleyin." % (q, c))
    if cfg.get("subscription") == "notfound" and cfg.get("no_subscription_repo") and not cfg.get("enterprise_repo_enabled"):
        note.append("Abonelik yok ve pve-no-subscription deposu etkin (Proxmox bunu test/ev kullanımı için önerir).")
    elif cfg.get("enterprise_repo_enabled") and cfg.get("subscription") == "notfound":
        warn.append("pve-enterprise deposu etkin ama abonelik yok: `apt update` 401 hatası verir.")

    res["summary"] = "Proxmox VE %s (%s), pve-firewall: %s, %d VM / %d CT." % (res["version"], "küme" if cfg.get("clustered") else "tek düğüm", fw_state, q, c)
    if warn:
        res["status"] = "warn"
    return res


def main(argv):
    try:
        cfg = json.loads(argv[1])
        if not isinstance(cfg, dict):
            raise ValueError("nesne değil")
    except (IndexError, ValueError) as exc:
        print(json.dumps({"status": "unknown", "summary": "", "warnings": [], "notes": [], "version": "", "error": "girdi okunamadı: %s" % exc}))
        return 0
    print(json.dumps(decide(cfg), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
