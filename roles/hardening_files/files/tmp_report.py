#!/usr/bin/env python3
"""/tmp ve /dev/shm bağlama seçenekleri raporu (CIS 1.1.2: ayrı bağlama, nodev, nosuid, noexec). SALT OKUNUR; hiçbir şeyi değiştirmez, yalnızca karar verir.

Girdi (argv[1], JSON): mounts (her hedef için bir satır: `<sorulan yol>: <bağlama noktası> <dosya sistemi> <seçenekler>`, `findmnt -n -o TARGET,FSTYPE,OPTIONS --target <yol>` çıktısı
önüne yol eklenmiş; findmnt bir şey vermediyse satır `<yol>:` olur), remote_tmp (Ansible'ın uzak geçici dizini, bilinmiyorsa ""). Çıktı (stdout, JSON): status (ok|warn|unknown),
warnings, notes, summary, targets, error.

Uyarı (warn): hedef ayrı bir bağlama değil (seçenek uygulanamaz), ayrı ama `nodev`/`nosuid` yok, ya da Ansible'ın uzak geçici dizini /tmp ya da /dev/shm altında
(noexec açılırsa Ansible modülleri çalışmaz). Not (note): ayrı ama `noexec` yok. Ubuntu'nun varsayılanı budur ve noexec davranışı değiştirdiği için rapor yalnızca bilgi verir.
Python 3.9+ (yalnızca stdlib).
"""
import json
import sys

TARGETS = ("/tmp", "/dev/shm")


def parse(lines):
    out = {}
    for line in lines or []:
        if ":" not in str(line):
            continue
        q, rest = str(line).split(":", 1)
        q = q.strip()
        parts = rest.split()
        if q not in TARGETS:
            continue
        if len(parts) < 3:
            out[q] = {"separate": False, "mount": parts[0] if parts else "", "fstype": "", "options": []}
            continue
        out[q] = {"separate": parts[0] == q, "mount": parts[0], "fstype": parts[1], "options": parts[2].split(",")}
    return out


def decide(cfg):
    res = {"status": "ok", "warnings": [], "notes": [], "summary": "", "targets": {}, "error": ""}
    info = parse(cfg.get("mounts"))
    if not info:
        res.update(status="unknown", error="bağlama bilgisi okunamadı")
        return res
    for t in TARGETS:
        i = info.get(t)
        if i is None:
            continue
        res["targets"][t] = i
        if not i["separate"]:
            res["warnings"].append("%s ayrı bir bağlama değil (%s üzerinde); bağlama seçenekleri (nodev, nosuid, noexec) uygulanamaz, CIS ayrı bağlama ister." % (t, i["mount"] or "kök dosya sistemi"))
            continue
        missing = [o for o in ("nodev", "nosuid") if o not in i["options"]]
        if missing:
            res["warnings"].append("%s bağlamasında %s yok (seçenekler: %s)." % (t, "/".join(missing), ",".join(i["options"])))
        if "noexec" not in i["options"]:
            res["notes"].append("%s bağlamasında noexec yok (CIS ister)." % t)
    rt = str(cfg.get("remote_tmp") or "").strip()
    if rt.startswith(("/tmp", "/dev/shm")):
        res["warnings"].append("Ansible uzak geçici dizini (%s) /tmp ya da /dev/shm altında: noexec açılırsa Ansible modülleri çalışmaz." % rt)
    if res["notes"]:
        res["notes"].append("noexec, bu dizinlerden doğrudan çalıştırmayı kapatır; paket betikleri, derleme araçları ve `remote_tmp` /tmp ise Ansible etkilenebilir. Bu rapor bir şey DEĞİŞTİRMEZ (docs/design/grup3-tmp-su-root.md).")
    if res["warnings"]:
        res["status"] = "warn"
    else:
        res["summary"] = "; ".join("%s: %s %s" % (t, res["targets"][t]["fstype"], ",".join(o for o in ("nodev", "nosuid", "noexec") if o in res["targets"][t]["options"]) or "seçenek yok") for t in res["targets"])
    return res


def main(argv):
    try:
        cfg = json.loads(argv[1])
        if not isinstance(cfg, dict):
            raise ValueError("nesne değil")
    except (IndexError, ValueError) as exc:
        print(json.dumps({"status": "unknown", "warnings": [], "notes": [], "summary": "", "targets": {}, "error": "girdi okunamadı: %s" % exc}))
        return 0
    print(json.dumps(decide(cfg), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
