#!/usr/bin/env python3
"""root ortamı raporu: CIS 5.4.2.5 (root PATH bütünlüğü) ve 5.4.2.6 (root umask). SALT OKUNUR; hiçbir şeyi değiştirmez, yalnızca karar verir.

Girdi (argv[1], JSON): path (root giriş kabuğunun PATH değeri), dirs (PATH girdileri için satırlar: `<mod> <sahip> <yol>` ya da `MISSING - <yol>`; `stat -L` ile alınır),
login_defs_umask (/etc/login.defs UMASK değeri ya da ""), pam_umask (common-session'da etkin pam_umask.so satırı var mı), file_umasks (`<dosya>:<umask komutu satırı>` listesi:
/root/.bashrc, /root/.profile, /etc/profile, /etc/bash.bashrc, /etc/profile.d/*.sh). Çıktı (stdout, JSON): status (ok|warn|unknown), messages, summary,
path_issues, umask_issues, error.

CIS ölçütü: PATH'te boş girdi (`::`, baştaki/sondaki `:`), `.`, olmayan dizin, root'a ait olmayan ya da grup/diğer YAZILABİLİR dizin olmamalı; root umask'ı 027 ya da daha kısıtlayıcı olmalı
((umask & 027) == 027). Sembolik umask (`u=rwx,g=rx,o=`) ayrıştırılmaz: "elle bakın" denir. Python 3.9+ (yalnızca stdlib).
"""
import json
import re
import sys


def parse_umask(text):
    """'0027' / '027' / '27' -> int; ayrıştırılamazsa None."""
    t = str(text).strip()
    if re.fullmatch(r"[0-7]{1,4}", t):
        return int(t, 8)
    return None


def too_open(value):
    return (value & 0o027) != 0o027


def check_path(path, dirs):
    issues = []
    entries = str(path).split(":")
    if str(path).strip() == "":
        return ["PATH boş."]
    for i, e in enumerate(entries):
        if e == "":
            issues.append("PATH'te boş girdi var (`::` ya da baştaki/sondaki `:`; geçerli dizin anlamına gelir).")
            break
    if any(e == "." for e in entries):
        issues.append("PATH'te `.` (geçerli dizin) var.")
    seen = set()
    for row in dirs or []:
        parts = str(row).split(" ", 2)
        if len(parts) != 3:
            continue
        mode, owner, p = parts
        if p in seen:
            continue
        seen.add(p)
        if mode == "MISSING":
            issues.append("PATH'teki dizin yok: `%s`." % p)
            continue
        if owner != "root":
            issues.append("PATH'teki dizin root'a ait değil (%s): `%s`." % (owner, p))
        try:
            m = int(mode, 8)
        except ValueError:
            continue
        if m & 0o022:
            issues.append("PATH'teki dizin grup/diğer tarafından YAZILABİLİR (%s): `%s`." % (mode, p))
    return issues


def check_umask(login_defs, pam_umask, file_umasks):
    issues = []
    manual = []
    values = []
    ld = str(login_defs or "").strip()
    if ld:
        v = parse_umask(ld)
        if v is None:
            manual.append("/etc/login.defs UMASK ayrıştırılamadı (%s)" % ld)
        else:
            values.append(("/etc/login.defs", v))
    for line in file_umasks or []:
        if ":" not in str(line):
            continue
        fname, cmd = str(line).split(":", 1)
        m = re.match(r"^\s*umask\s+(\S+)", cmd)
        if not m:
            continue
        v = parse_umask(m.group(1))
        if v is None:
            manual.append("%s: `%s` (sembolik ya da ayrıştırılamayan umask; elle bakın)" % (fname, cmd.strip()))
        else:
            values.append((fname, v))
    for fname, v in values:
        if too_open(v):
            issues.append("%s içinde umask %04o, 027'den gevşek." % (fname, v))
    if not ld and not any(f != "/etc/login.defs" for f, _ in values):
        issues.append("Hiçbir yerde umask ayarı bulunamadı; kabuğun varsayılanı (022) geçerli olabilir.")
    elif ld and not pam_umask and not any(f != "/etc/login.defs" for f, _ in values):
        issues.append("/etc/login.defs UMASK var ama common-session'da `pam_umask.so` etkin değil; bu değer giriş oturumlarına uygulanmayabilir.")
    return issues, manual


def decide(cfg):
    res = {"status": "ok", "messages": [], "summary": "", "path_issues": [], "umask_issues": [], "error": ""}
    if not isinstance(cfg.get("path", None), str):
        res.update(status="unknown", error="path metin olmalı")
        return res
    res["path_issues"] = check_path(cfg["path"], cfg.get("dirs"))
    ui, manual = check_umask(cfg.get("login_defs_umask"), bool(cfg.get("pam_umask")), cfg.get("file_umasks"))
    res["umask_issues"] = ui
    res["messages"] = list(res["path_issues"]) + list(ui) + ["Elle bakın: " + m for m in manual]
    if res["path_issues"] or ui or manual:
        res["status"] = "warn"
    else:
        n = len([e for e in cfg["path"].split(":") if e])
        res["summary"] = "root PATH temiz (%d dizin) ve umask 027 ya da daha kısıtlayıcı." % n
    return res


def main(argv):
    try:
        cfg = json.loads(argv[1])
        if not isinstance(cfg, dict):
            raise ValueError("nesne değil")
    except (IndexError, ValueError) as exc:
        print(json.dumps({"status": "unknown", "messages": [], "summary": "", "path_issues": [], "umask_issues": [], "error": "girdi okunamadı: %s" % exc}))
        return 0
    print(json.dumps(decide(cfg), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
