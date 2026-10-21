#!/usr/bin/env python3
"""Takip edilen dosyalarda yalnızca belgelenmiş/örnek IP adreslerine izin verir (gerçek IP sızıntısı yakalanır).

İzinli: 127.0.0.0/8, 0.0.0.0, 10.0.0.0/8 aralık notasyonu (belgelenmiş yönetim ağı),
        192.168.1.x ve 192.0.2.x (örnek), testlerin sahte adresleri (10.1.2.x, 10.9.9.9, fd00::, 1.1.1.1 vb.).
Regex `\\b` yerine açık sınır (lookaround) kullanır; platforma (macOS/GNU) bağlı grep davranışından etkilenmez.
"""
import ipaddress
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IP = re.compile(r"(?<![0-9A-Za-z.])((?:\d{1,3}\.){3}\d{1,3})(?:/(\d{1,2}))?(?![0-9A-Za-z.])")
# cis-esleme.md, cis-esleme-debian.md, grup3-tmp-su-root.md: CIS madde numaraları (3.3.1.4 gibi) dört sayılı noktalı yazım olduğu için IP gibi görünür; belgede adres yok.
SKIP_FILES = {"requirements.txt", "requirements-dev.txt", "CHANGELOG.md", "cis-esleme.md", "cis-esleme-debian.md", "grup3-tmp-su-root.md"}
SKIP_PREFIX = ("test/",)  # testlerin sahte adresleri; ayrıca asagida sinanir

def allowed(ip_s, mask):
    try:
        ip = ipaddress.ip_address(ip_s)
    except ValueError:
        return True  # surum numarasi vb. (ör. 3.1.6.2 gecerli IP degil)
    if ip.is_loopback or str(ip) == "0.0.0.0":
        return True
    if ip_s.startswith("10.") and mask == "8" and ip_s == "10.0.0.0":
        return True
    if ip_s.startswith("192.168.1.") or ip_s.startswith("192.0.2."):
        return True
    if ip_s in {"1.1.1.1", "2.2.2.2", "3.3.3.3"}:   # grup deseni testinin adresleri (yalniz test/ icinde olmali)
        return False
    return False

files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n")
bad = []
checked = 0
for rel in filter(None, files):
    if Path(rel).name in SKIP_FILES or rel.startswith(SKIP_PREFIX):
        continue
    p = ROOT / rel
    try:
        text = p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        continue
    checked += 1
    for n, line in enumerate(text.splitlines(), 1):
        for m in IP.finditer(line):
            if not allowed(m.group(1), m.group(2)):
                bad.append(f"{rel}:{n}: {m.group(0)}")
if checked == 0:
    print("  FAIL hic dosya taranmadi (test bozuk)")
    sys.exit(1)
if bad:
    print("Beklenmeyen IP adresleri:")
    for b in bad:
        print("  -", b)
    sys.exit(1)
print(f"  ok   {checked} dosya tarandi, beklenmeyen IP yok")
print("TAMAM")
