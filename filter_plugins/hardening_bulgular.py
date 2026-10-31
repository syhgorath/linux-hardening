# lynis-report.dat -> bulgular.tsv (docs/bulgular-sema.md). Bulgular yalnız gösterim içindir; çağıran görev hata olursa dosyayı atlar.
from __future__ import annotations

HEADER = ["kimlik", "risk", "tur", "aciklama", "ayrinti", "oneri", "alan", "deger", "kapanir_varsayilan", "platform"]
RISKS = {"yuksek", "orta", "dusuk", "bilgi", "bilinmiyor"}
KAPANIR = {"evet", "hayir", ""}
PLATFORMS = {"ubuntu", "proxmox", "hepsi"}
TURLER = {"warning[]": "uyari", "suggestion[]": "oneri"}


def _clean(value):
    # Lynis'in "-" yer tutucusu boş sayılır; sekme/satır sonu boşluğa çevrilir (TSV bozulmasın)
    value = " ".join(str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ").split())
    return "" if value == "-" else value


def _mapping(text):
    rows = []
    lines = [ln for ln in str(text or "").splitlines() if ln.strip() and not ln.startswith("#")]
    if not lines:
        return rows
    head = lines[0].split("\t")
    for ln in lines[1:]:
        cols = dict(zip(head, ln.split("\t")))
        kimlik = cols.get("kimlik", "").strip()
        if not kimlik:
            continue
        rows.append({
            "kimlik": kimlik,
            "icerir": cols.get("ayrinti_icerir", "").strip(),
            "risk": cols.get("risk", "").strip(),
            "alan": cols.get("alan", "").strip(),
            "deger": cols.get("deger", "").strip(),
            "kapanir_varsayilan": cols.get("kapanir_varsayilan", "").strip(),
            "platform": cols.get("platform", "").strip(),
        })
    return rows


def hardening_findings_tsv(report, mapping=""):
    if not isinstance(report, str):
        raise TypeError("lynis raporu metin olmalı")
    rows = _mapping(mapping)
    out = ["\t".join(HEADER)]
    genel = 0
    for ln in report.splitlines():
        key, sep, rest = ln.partition("=")
        if not sep or key not in TURLER:
            continue
        parts = rest.split("|")
        kimlik = _clean(parts[0]) if parts else ""
        aciklama = _clean(parts[1]) if len(parts) > 1 else ""
        ayrinti = _clean(parts[2]) if len(parts) > 2 else ""
        oneri = _clean(parts[3]) if len(parts) > 3 else ""
        if not kimlik:
            genel += 1
            kimlik = f"GENEL-{genel}"
        m = next((r for r in rows if r["kimlik"] == kimlik and (not r["icerir"] or r["icerir"] in ayrinti or r["icerir"] in aciklama)), None)
        risk = m["risk"] if m and m["risk"] in RISKS else "bilinmiyor"
        platform = m["platform"] if m and m["platform"] in PLATFORMS else "hepsi"
        kapanir = m["kapanir_varsayilan"] if m and m["kapanir_varsayilan"] in KAPANIR else ""
        alan = m["alan"] if m else ""
        deger = m["deger"] if m else ""
        if not alan:
            kapanir = ""
        out.append("\t".join([kimlik, risk, TURLER[key], aciklama, ayrinti, oneri, alan, deger, kapanir, platform]))
    return "\n".join(out) + "\n"


class FilterModule:
    def filters(self):
        return {"hardening_findings_tsv": hardening_findings_tsv}
