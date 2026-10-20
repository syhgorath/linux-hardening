#!/usr/bin/env python3
"""/tmp ve /dev/shm için `nodev,nosuid,noexec` UYGULAMA PLANI (bu betik hiçbir şeyi değiştirmez, yalnızca ne yapılacağına karar verir).

Girdi (argv[1], JSON): mounts (`<yol>: <bağlama noktası> <dosya sistemi> <seçenekler>` satırları, `findmnt -n -o TARGET,FSTYPE,OPTIONS --target <yol>` çıktısı), tmp_mount_active
(`systemctl show tmp.mount -p ActiveState --value` çıktısı), shm_fstab (/etc/fstab'daki `/dev/shm` satırı ya da ""), want_tmp, want_shm (bool).
Çıktı (stdout, JSON): tmp ve shm için {manage, persist, remount, reason}, warnings, error.

Kural (yanlış bağlamaya dokunmak sunucuyu bozar): yalnızca AYRI bir bağlama olan ve `tmpfs` olan dizin yönetilir. `/tmp` için ayrıca `tmp.mount` etkin olmalı (kalıcılık drop-in ile sağlanır);
`/dev/shm` için kalıcılık /etc/fstab satırıdır ve satır zaten varsa ÜSTÜNE YAZILMAZ (kullanıcının size= vb. seçenekleri kaybolmasın). Python 3.9+ (yalnızca stdlib).
"""
import json
import re
import sys

NEED = ("noexec", "nosuid", "nodev")


def parse(lines):
    out = {}
    for line in lines or []:
        if ":" not in str(line):
            continue
        q, rest = str(line).split(":", 1)
        parts = rest.split()
        q = q.strip()
        if q in ("/tmp", "/dev/shm") and len(parts) >= 3:
            out[q] = {"separate": parts[0] == q, "fstype": parts[1], "options": parts[2].split(",")}
    return out


def plan_for(path, want, info, extra_reason="", persist=True):
    res = {"manage": False, "persist": False, "remount": False, "reason": ""}
    if not want:
        return res
    if info is None:
        res["reason"] = "%s için bağlama bilgisi okunamadı" % path
    elif not info["separate"]:
        res["reason"] = "%s ayrı bir bağlama değil (seçenek uygulanamaz)" % path
    elif info["fstype"] != "tmpfs":
        res["reason"] = "%s dosya sistemi tmpfs değil (%s); elle yapılandırın" % (path, info["fstype"])
    elif extra_reason:
        res["reason"] = extra_reason
    else:
        res["manage"] = True
        res["persist"] = persist
        res["remount"] = any(o not in info["options"] for o in NEED)
    return res


def decide(cfg):
    out = {"tmp": {}, "shm": {}, "warnings": [], "error": ""}
    info = parse(cfg.get("mounts"))
    tmp_extra = "" if str(cfg.get("tmp_mount_active", "")).strip() == "active" else "/tmp tmp.mount ile yönetilmiyor (fstab ya da başka bir yöntem); elle yapılandırın"
    out["tmp"] = plan_for("/tmp", bool(cfg.get("want_tmp")), info.get("/tmp"), tmp_extra)
    line = str(cfg.get("shm_fstab") or "").strip()
    shm_persist = True
    shm_info = info.get("/dev/shm")
    if line and all(o in re.split(r"[,\s]+", line) for o in NEED):
        shm_persist = False  # satır zaten üç seçeneği içeriyor
    elif line:
        out["shm"] = plan_for("/dev/shm", bool(cfg.get("want_shm")), shm_info, "/etc/fstab'da /dev/shm satırı zaten var ve noexec/nosuid/nodev içermiyor; üstüne yazılmadı, elle düzenleyin")
        shm_persist = None
    if shm_persist is not None:
        out["shm"] = plan_for("/dev/shm", bool(cfg.get("want_shm")), shm_info, "", shm_persist)
    for k in ("tmp", "shm"):
        if out[k].get("reason"):
            out["warnings"].append(out[k]["reason"] + ".")
    return out


def main(argv):
    try:
        cfg = json.loads(argv[1])
        if not isinstance(cfg, dict):
            raise ValueError("nesne değil")
    except (IndexError, ValueError) as exc:
        z = {"manage": False, "persist": False, "remount": False, "reason": ""}
        print(json.dumps({"tmp": z, "shm": z, "warnings": [], "error": "girdi okunamadı: %s" % exc}))
        return 0
    print(json.dumps(decide(cfg), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
