#!/usr/bin/env python3
"""component.yml'den component.json üretir (sshpocket paket standardı §4: makine-okunur bildirim).

Kullanım (repo kökünde, PyYAML'ın kurulu olduğu ortamda):
    python3 -I scripts/make-component-json.py            # component.json'u yazar
    python3 -I scripts/make-component-json.py --check    # yazmaz; dosya güncel değilse çıkış kodu 1

component.json git'e girer ve imzalı pakete o girer (scripts/ pakete girmez). component.yml insan-okunur kaynaktır;
component.json elle düzenlenmez. sshpocket bunu YAML ayrıştırmadan python3 -I + stdlib json ile okur.
"""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def render():
    data = yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def main(argv):
    if argv not in ([], ["--check"]):
        print(__doc__, file=sys.stderr)
        return 2
    want = render()
    target = ROOT / "component.json"
    if argv == ["--check"]:
        if not target.exists() or target.read_text(encoding="utf-8") != want:
            print("component.json güncel değil: python3 -I scripts/make-component-json.py", file=sys.stderr)
            return 1
        print("OK: component.json, component.yml ile aynı")
        return 0
    target.write_text(want, encoding="utf-8")
    print("component.json yazıldı")
    return 0


sys.exit(main(sys.argv[1:]))
