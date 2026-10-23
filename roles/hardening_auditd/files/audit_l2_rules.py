#!/usr/bin/env python3
"""CIS Level 2 auditd kural seti (6.2.3.x) üretici: YALNIZCA metin üretir, hiçbir şeyi yazmaz.

Girdi (argv[1], JSON): arch ("x86_64", "aarch64", ...), paths (liste: VAR olan izlenecek yollar; kural yalnızca bunlar için yazılır, var olmayan yola kural eklemek yüklemeyi bozar),
priv (liste: setuid/setgid dosyaları), sudo_logfile (str), has_b32 (bool: 32 bit sistem çağrısı arayüzü, x86_64'te true; aarch64'te çoğu çekirdekte yok).
Çıktı (stdout, JSON): rules (kural metni), count (kural satırı sayısı).

Zaten 60-hardening.rules'ta olan kurallar (passwd/group/shadow, sudoers, time-change b64, /etc/localtime, lastlog, modules b64) TEKRAR YAZILMAZ: aynı kural iki kez yüklenince
auditctl "Rule exists" der. `-e 2` (değiştirilemez yapılandırma, 6.2.3) bilerek YOKTUR: kurallar yeniden başlatmadan güncellenemez, rolün kendi yeniden yüklemesi de çalışmaz.
Python 3.9+ (yalnızca stdlib)."""
import json
import re
import sys

AUID = "-F auid>=1000 -F auid!=unset"
SAFE = re.compile(r"^/[A-Za-z0-9_@%+=:,./-]+$")


def archs(has_b32):
    return ["b64", "b32"] if has_b32 else ["b64"]


def decide(cfg):
    paths = {p for p in cfg.get("paths") or [] if SAFE.match(str(p))}
    has_b32 = bool(cfg.get("has_b32"))
    out = []

    def watch(path, key, perm="wa"):
        if path in paths:
            out.append("-w %s -p %s -k %s" % (path, perm, key))

    def sc(syscalls, key, extra="", arch_list=None):
        for a in arch_list or archs(has_b32):
            out.append(("-a always,exit -F arch=%s -S %s %s -k %s" % (a, syscalls, extra, key)).replace("  ", " "))

    out.append("# CIS Level 2 (6.2.3.x), Ansible tarafından yönetilir (hardening_auditd_cis_l2)")
    out.append("-c")   # 6.2.3: bir kural hatalı olsa da yüklemeye devam et
    # 6.2.3 sudo günlüğü
    sudo_log = str(cfg.get("sudo_logfile") or "")
    if sudo_log and sudo_log in paths:
        out.append("-w %s -p wa -k sudo_log_file" % sudo_log)
    # 6.2.3 başka kullanıcı olarak yapılan işlemler
    sc("execve", "user_emulation", "-C euid!=uid -F auid!=unset")
    # 6.2.3 saat (b64 zaten 60-hardening.rules'ta; yalnızca 32 bit arayüzü)
    if has_b32:
        sc("adjtimex,settimeofday,clock_settime", "time-change", "", ["b32"])
    # 6.2.3 sethostname/setdomainname ve 6.2.3/.8 ağ ortamı dosyaları
    sc("sethostname,setdomainname", "system-locale")
    for p in ("/etc/issue", "/etc/issue.net", "/etc/hosts", "/etc/networks", "/etc/network/", "/etc/netplan/"):
        watch(p, "system-locale")
    # 6.2.3 ayrıcalıklı komutlar
    for f in sorted({str(p) for p in cfg.get("priv") or [] if SAFE.match(str(p))}):
        out.append("-a always,exit -F path=%s -F perm=x %s -k privileged" % (f, AUID))
    # 6.2.3 başarısız dosya erişimleri
    calls = "creat,open,openat,openat2,truncate,ftruncate"
    for err in ("EACCES", "EPERM"):
        sc(calls, "access", "-F exit=-%s %s" % (err, AUID))
    # 6.2.3-.17 kimlik/PAM dosyaları
    for p in ("/etc/security/opasswd", "/etc/nsswitch.conf", "/etc/pam.conf", "/etc/pam.d/"):
        watch(p, "identity" if p.endswith("opasswd") else "pam")
    # 6.2.3-.20 DAC değişiklikleri
    sc("chmod,fchmod,fchmodat,fchmodat2", "perm_mod", AUID)
    sc("chown,fchown,lchown,fchownat", "perm_mod", AUID)
    sc("setxattr,lsetxattr,fsetxattr,removexattr,lremovexattr,fremovexattr", "perm_mod", AUID)
    # 6.2.3 bağlamalar
    sc("mount", "mounts", AUID)
    # 6.2.3-.23 oturum / giriş
    for p in ("/var/run/utmp", "/var/log/wtmp", "/var/log/btmp"):
        watch(p, "session")
    for p in ("/var/log/faillog", "/var/log/tallylog"):
        watch(p, "logins")
    # 6.2.3-.25 silme / yeniden adlandırma
    sc("unlink,unlinkat,rename,renameat,renameat2", "delete", AUID)
    # 6.2.3 MAC
    for p in ("/etc/apparmor/", "/etc/apparmor.d/"):
        watch(p, "MAC-policy")
    # 6.2.3-.30 komut kullanımları
    for tool, key in (("/usr/bin/chcon", "perm_chng"), ("/usr/bin/setfacl", "perm_chng"), ("/usr/bin/chacl", "perm_chng"), ("/usr/sbin/usermod", "usermod")):
        if tool in paths:
            out.append("-a always,exit -F path=%s -F perm=x %s -k %s" % (tool, AUID, key))
    # 6.2.3-.33 çekirdek modülleri (b64 zaten 60-hardening.rules'ta)
    if has_b32:
        sc("init_module,finit_module,delete_module", "modules", "", ["b32"])
    watch("/usr/bin/kmod", "kernel_modules", "x")
    return {"rules": "\n".join(out) + "\n", "count": len([l for l in out if l and not l.startswith("#")])}


def main(argv):
    try:
        cfg = json.loads(argv[1])
        if not isinstance(cfg, dict):
            raise ValueError("nesne değil")
    except (IndexError, ValueError) as exc:
        print(json.dumps({"rules": "", "count": 0, "error": "girdi okunamadı: %s" % exc}))
        return 0
    print(json.dumps(decide(cfg), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
