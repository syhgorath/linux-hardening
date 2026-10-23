#!/usr/bin/env python3
"""SALT OKUNUR sistem raporu (hiçbir şeyi DEĞİŞTİRMEZ, yalnızca karar verir): IPv6 durumu (CIS 3.1.1), dinleyen servisler (2.1.23), kullanıcı nokta dizinleri (7.2.11) ve `nullok` / boş parola (5.3.3.4.1).

Girdi (argv[1], JSON): ipv6 ({disable_all: "0"|"1"|"", global_addrs: int}), listeners (liste: "tcp 0.0.0.0:22" = `ss -H -lntu` netid + yerel adres:port), approved (liste: "22/tcp", "123/udp";
boşsa yalnızca bilgi notu), dotdirs (liste: "750 kullanici /home/kullanici/.ssh" = `stat -c '%a %U %n'`), nullok ({lines: ["/etc/pam.d/common-auth:25:..."], empty_accounts: ["ad"]}).
Çıktı (stdout, JSON): status (ok|warn), warnings, notes. Python 3.9+ (yalnızca stdlib)."""
import json
import re
import sys


def is_loopback(addr):
    return addr in ("127.0.0.1", "::1") or addr.startswith("127.") or addr in ("127.0.0.53%lo", "127.0.0.54")


def split_addr(entry):
    entry = entry.strip()
    if ":" not in entry:
        return entry, ""
    addr, port = entry.rsplit(":", 1)
    return addr.strip("[]"), port


def decide(cfg):
    warn, note = [], []

    ipv6 = cfg.get("ipv6") or {}
    if ipv6:
        da, n = str(ipv6.get("disable_all", "")).strip(), int(ipv6.get("global_addrs") or 0)
        if da == "1":
            note.append("IPv6 çekirdekte devre dışı (disable_ipv6=1).")
        elif da == "0":
            note.append("IPv6 etkin%s. Kullanmıyorsanız kapatmak sizin kararınızdır (CIS 3.1.1 yalnızca durumun belirlenmesini ister); bu paket IPv6'yı kapatmaz." % (" ve genel (global) adres atanmış" if n else ", genel adres yok"))
        else:
            note.append("IPv6 durumu okunamadı.")

    approved = {str(a).strip() for a in cfg.get("approved") or [] if str(a).strip()}
    seen = []
    for entry in cfg.get("listeners") or []:
        parts = str(entry).split()
        if len(parts) != 2:
            continue
        proto, local = parts
        addr, port = split_addr(local)
        if not port or is_loopback(addr):
            continue
        key = "%s/%s" % (port, proto)
        if key not in seen:
            seen.append(key)
    if approved:
        extra = [k for k in seen if k not in approved]
        if extra:
            warn.append("Onaylı listede OLMAYAN, yerel olmayan adreste dinleyen servis(ler) (CIS 2.1.23): %s." % ", ".join(extra))
    elif seen:
        note.append("Yerel olmayan adreste dinleyen portlar: %s. Beklenenleri hardening_approved_listeners'a yazarsanız listede olmayanlar uyarı olur (CIS 2.1.23)." % ", ".join(seen))

    bad = []
    for line in cfg.get("dotdirs") or []:
        m = re.match(r"^([0-7]{3,4}) (\S+) (.+)$", str(line).strip())
        if not m:
            continue
        mode, owner, path = int(m.group(1), 8), m.group(2), m.group(3)
        limit = 0o077 if path.rstrip("/").endswith("/.ssh") else 0o027
        if mode & limit:
            bad.append("%s (%s, %s)" % (path, oct(mode)[2:], owner))
    if bad:
        warn.append("Kullanıcı nokta dizinleri gereğinden açık (CIS 7.2.11: 0750 ya da daha kısıtlı, .ssh 0700): %s. Değiştirilmedi." % "; ".join(bad[:10]) + (" ..." if len(bad) > 10 else ""))

    nk = cfg.get("nullok") or {}
    empty = [str(a) for a in nk.get("empty_accounts") or []]
    lines = nk.get("lines") or []
    if empty:
        warn.append("BOŞ PAROLALI hesap(lar): %s. (CIS 5.3.3.4.1: boş parola ile giriş kapatılmalı.)" % ", ".join(empty))
    if lines:
        note.append("pam_unix'te `nullok` var (boş parolayla girişe izin verir): %s. Bu paket değiştirmez; boş parolalı hesap yoksa pam-auth-update ile kaldırabilirsiniz." % "; ".join(str(x)[:100] for x in lines[:3]))
    elif nk:
        note.append("pam_unix'te `nullok` yok.")

    # 1.6.4: pam_motd'nin gösterdiği dosyalarda işletim sistemi bilgisi (\\m \\r \\s \\v ya da dağıtım adı) olmamalı; DEĞİŞTİRİLMEZ, nasıl kapatılacağı söylenir
    motd = cfg.get("motd") or {}
    hits = [str(h) for h in motd.get("hits") or []]
    if hits:
        warn.append("MOTD dosyalarında işletim sistemi bilgisi var (CIS 1.6.4): %s. Değiştirilmedi. /etc/update-motd.d betikleri üretiyorsa hardening_motd_disable_scripts (örn. [\"00-header\", \"10-help-text\"]) ile kapatılır; düz dosyaysa (örn. Debian'ın /etc/motd'u) içeriğini elle düzenleyin, rol dokunmaz." % ", ".join(hits[:5]))
    # 5.3.3.4.2 / 5.3.3.4.4: pam_unix'te `remember=` olmamalı (geçmiş için pam_pwhistory), parola yığınında `use_authtok` olmalı
    pu = cfg.get("pamunix") or {}
    if pu.get("remember"):
        warn.append("pam_unix'te `remember=` var (CIS 5.3.3.4.2: parola geçmişi için pam_pwhistory kullanılmalı): %s." % "; ".join(str(x)[:100] for x in pu["remember"][:3]))
    if pu.get("no_authtok"):
        warn.append("pam_unix parola satırında `use_authtok` yok (CIS 5.3.3.4.4): %s." % "; ".join(str(x)[:100] for x in pu["no_authtok"][:3]))

    # 5.2.4 (Level 2): sudoers'ta NOPASSWD olmamalı; DEĞİŞTİRİLMEZ (otomasyon hesabı için bilinçli olabilir)
    nopw = [str(x) for x in cfg.get("nopasswd") or []]
    if nopw:
        warn.append("sudoers'ta NOPASSWD var, yani bazı kullanıcılar parola sormadan sudo kullanıyor (CIS 5.2.4, Level 2): %s. Değiştirilmedi; otomasyon hesabı için bilinçli olabilir." % "; ".join(x[:100] for x in nopw[:5]))
    # 5.4.3 (Level 2): /etc/shells içinde nologin listelenmemeli (nologin kabuğu 'geçerli kabuk' sayılır); DEĞİŞTİRİLMEZ
    if cfg.get("shells_nologin"):
        note.append("/etc/shells içinde nologin listeleniyor (CIS 5.4.3, Level 2): hesaplar nologin kabuğuyla 'geçerli kabuk' sayılır. Değiştirilmedi.")
    # 1.1.2.3.1, 1.1.2.4.1, 1.1.2.5.1, 1.1.2.6.1, 1.1.2.7.1 (Level 2): ayrı bölümler kurulumda yapılır; yalnızca durum bildirilir
    mounts = cfg.get("mounts") or {}
    missing = [m for m, sep in mounts.items() if str(sep).lower() not in ("yes", "true", "1")]
    if mounts and missing:
        note.append("Ayrı bölüm (mount noktası) yok: %s (CIS 1.1.2.x.1, Level 2). Bölümler kurulumda belirlenir; çalışan sunucuda sonradan eklenmez, bu paket de dokunmaz." % ", ".join(missing))

    return {"status": "warn" if warn else "ok", "warnings": warn, "notes": note}


def main(argv):
    try:
        cfg = json.loads(argv[1])
        if not isinstance(cfg, dict):
            raise ValueError("nesne değil")
    except (IndexError, ValueError) as exc:
        print(json.dumps({"status": "ok", "warnings": [], "notes": ["rapor girdisi okunamadı: %s" % exc]}, ensure_ascii=False))
        return 0
    print(json.dumps(decide(cfg), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
