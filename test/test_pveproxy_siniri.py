#!/usr/bin/env python3
"""hardening_pve_pveproxy: Proxmox web arayüzü (pveproxy) erişim sınırı. Karar betiği pveproxy_plan.py (hiçbir şey yazmaz) ve rolün yazma/yedek/doğrulama/geri yükleme akışı
gerçek Ansible ile geçici dosyalar üzerinde denenir (pveproxy yeniden başlatma ve 8006 doğrulaması testte kapatılır / sahtelenir)."""
import grp
import json
import os
import pwd
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "roles/hardening_pve_pveproxy/files/pveproxy_plan.py"
fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail}")


def load(p):
    return yaml.safe_load((ROOT / p).read_text(encoding="utf-8"))


def plan(cfg):
    r = subprocess.run([sys.executable, str(SCRIPT), cfg if isinstance(cfg, str) else json.dumps(cfg)], capture_output=True, text=True)
    return json.loads(r.stdout)


BEGIN, END = "# BEGIN linux-hardening pveproxy (elle degistirmeyin)", "# END linux-hardening pveproxy"
base = {"allow_from": ["192.0.2.0/24"], "client_ip": "192.0.2.10", "existing": None}
o = plan(base)
check("gecerli girdi: apply, ALLOW_FROM liste + yerel dongu, DENY_FROM all, POLICY allow", o["status"] == "apply" and o["allow_value"] == "192.0.2.0/24,127.0.0.0/8,::1/128" and 'DENY_FROM="all"' in o["content"] and 'ALLOW_FROM="192.0.2.0/24,127.0.0.0/8,::1/128"' in o["content"] and 'POLICY="allow"' in o["content"] and o["content"].startswith(BEGIN) and o["content"].endswith(END + "\n"), str(o))
check("yerel dongu zaten listedeyse tekrarlanmaz", plan({**base, "allow_from": ["192.0.2.0/24", "127.0.0.0/8"]})["allow_value"] == "192.0.2.0/24,127.0.0.0/8,::1/128")
check("IPv6 ag + istemci kabul", plan({"allow_from": ["2001:db8::/32"], "client_ip": "2001:db8::5", "existing": None})["status"] == "apply")
for name, cfg in (("bos liste", {**base, "allow_from": []}), ("liste degil", {**base, "allow_from": "192.0.2.0/24"}), ("'all'", {**base, "allow_from": ["all"]}), ("virgullu girdi", {**base, "allow_from": ["192.0.2.0/24,10.0.0.0/8"]}),
                  ("bosluklu girdi", {**base, "allow_from": ["192.0.2.0/24 10.0.0.0/8"]}), ("gecersiz ag", {**base, "allow_from": ["abc"]}), ("istemci kapsanmiyor", {**base, "client_ip": "203.0.113.9"}),
                  ("istemci okunamadi", {**base, "client_ip": ""}), ("istemci IPv6, liste IPv4", {**base, "client_ip": "2001:db8::5"})):
    o = plan(cfg)
    check(f"RED ve hicbir sey yazilmaz: {name}", o["status"] == "refuse" and o["content"] == "" and o["reasons"], str(o))
mine = plan(base)["content"]
o = plan({**base, "existing": 'ALLOW_FROM="10.0.0.0/8"\n'})
check("kullanicinin kendi ALLOW_FROM satiri varsa DOKUNULMAZ (RED)", o["status"] == "refuse" and "ALLOW_FROM" in " ".join(o["reasons"]), str(o))
check("kullanicinin POLICY satiri de RED", plan({**base, "existing": 'POLICY="deny"\n'})["status"] == "refuse")
o = plan({**base, "existing": "# yorum\nLISTEN_IP=\"192.0.2.5\"\n"})
check("baska anahtarlar (LISTEN_IP) korunur, blok sonuna eklenir", o["status"] == "apply" and o["content"].startswith('# yorum\nLISTEN_IP="192.0.2.5"\n' + BEGIN), str(o))
o = plan({**base, "existing": mine})
check("zaten istenen icerik -> noop", o["status"] == "noop", str(o))
o = plan({**base, "allow_from": ["198.51.100.0/24", "192.0.2.0/24"], "existing": mine})
check("liste degisince eski blok DEGISTIRILIR (cogaltilmaz)", o["status"] == "apply" and o["content"].count(BEGIN) == 1 and "198.51.100.0/24" in o["content"], str(o))
# kaldirma
o = plan({"remove": True, "existing": "# a\n" + mine + "LISTEN_IP=\"x\"\n"})
check("remove: yalniz bu rolun blogu kalkar, kullanicinin satirlari korunur", o["status"] == "apply" and BEGIN not in o["content"] and o["content"] == "# a\nLISTEN_IP=\"x\"\n", str(o))
o = plan({"remove": True, "existing": mine})
check("remove: blok tek basinaysa dosya SILINMELI (delete true)", o["status"] == "apply" and o["delete"] is True and o["content"].strip() == "", str(o))
check("remove: kullanicinin satiri varsa dosya SILINMEZ (delete false)", plan({"remove": True, "existing": "# a\n" + mine})["delete"] is False and plan({"remove": True, "existing": mine + 'LISTEN_IP="x"\n'})["delete"] is False)
check("remove: blok yoksa noop", plan({"remove": True, "existing": "# a\n"})["status"] == "noop" and plan({"remove": True, "existing": None})["status"] == "noop")
check("bozuk girdi: RED", plan("{")["status"] == "refuse")

# ---- rol ----
d = load("roles/hardening_pve_pveproxy/defaults/main.yml")
check("varsayilan: liste BOS (hicbir sey yazmaz), yeniden baslatma ve dogrulama acik", d["hardening_pve_pveproxy_allow_from"] == [] and d["hardening_pve_pveproxy_restart"] is True and d["hardening_pve_pveproxy_verify"] is True)
tasks = load("roles/hardening_pve_pveproxy/tasks/main.yml")
outer = next(t for t in tasks if t.get("name") == "Limit the pveproxy web access")
check("rol yalniz hardening_platform=proxmox-host iken calisir; baska platformda NOT", "== 'proxmox-host'" in str(outer["when"]) and any(t.get("name", "").startswith("Say that the pveproxy") for t in tasks))
inner = {t["name"]: t for t in outer["block"]}
check("karar betigi SALT OKUNUR (check_mode false), --check'te yalniz onizleme", inner["Decide what to write (read-only)"].get("check_mode") is False and "ansible_check_mode" in str(inner["Show what would be written (--check)"]["when"]))
apply_blk = inner["Apply the pveproxy access limit and verify the web UI"]
ib = {t["name"]: t for t in apply_blk["block"]}
check("yazma yalniz plan apply iken ve --check degilken", "== 'apply'" in apply_blk["when"] and "not ansible_check_mode" in apply_blk["when"])
check("sira: (blok tek basinaysa sil) -> yaz -> yeniden baslat -> kontrol makinesinden 8006 dogrula", list(ib) == ["Remove the pveproxy defaults file (only this role's block was in it)", "Write the pveproxy defaults file", "Restart pveproxy", "Verify the web UI from the controller (a NEW connection to the web port)"])
check("silme ve yazma birbirini DISLAR (delete bayragi)", "plan.delete | bool" in str(ib["Remove the pveproxy defaults file (only this role's block was in it)"]["when"]) and "not (hardening_pve_pveproxy_plan.delete" in str(ib["Write the pveproxy defaults file"]["when"]))
vf = ib["Verify the web UI from the controller (a NEW connection to the web port)"]
check("dogrulama kontrol makinesinden (delegate_to localhost), 8006, HTTP 200", vf["delegate_to"] == "localhost" and ":8006/" in vf["ansible.builtin.uri"]["url"] and vf["ansible.builtin.uri"]["status_code"] == 200)
rs = {t["name"]: t for t in apply_blk["rescue"]}
check("basarisizsa ESKI icerik geri yazilir (yoksa dosya silinir), pveproxy yeniden baslar, rol DURUR", "Restore the previous pveproxy defaults file" in rs and "Remove the pveproxy defaults file (it did not exist before)" in rs and rs["Restart pveproxy with the previous settings"].get("failed_when") is False and "ansible.builtin.fail" in rs["Stop after the failed web UI verification"])


def run_role(extra, existing, extra_vars_hosts=None):
    """Rolu gercek Ansible ile calistirir (Proxmox benzeri: platform=proxmox-host); dosya gecici, yeniden baslatma/dogrulama kapali."""
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "pveproxy"
        if existing is not None:
            f.write_text(existing, encoding="utf-8")
        pb = Path(td) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "roles": ["hardening_pve_pveproxy"]}]), encoding="utf-8")
        ev = {"hardening_platform": "proxmox-host", "hardening_pve_pveproxy_file": str(f), "hardening_pve_pveproxy_restart": False, "hardening_pve_pveproxy_verify": False,
              "hardening_pve_pveproxy_owner": pwd.getpwuid(os.getuid()).pw_name, "hardening_pve_pveproxy_group": grp.getgrgid(os.getgid()).gr_name, **extra}
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb), "-e", json.dumps(ev)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg"), "ANSIBLE_ROLES_PATH": str(ROOT / "roles"), "SSH_CONNECTION": "192.0.2.10 50000 198.51.100.1 22"})
        return r.returncode, r.stdout + r.stderr, (f.read_text(encoding="utf-8") if f.exists() else None)


rc, out, txt = run_role({"hardening_pve_pveproxy_allow_from": ["192.0.2.0/24"]}, None)
check("gercek kosu: dosya yoksa olusur, blok dogru", rc == 0 and txt is not None and 'ALLOW_FROM="192.0.2.0/24,127.0.0.0/8,::1/128"' in txt, out[-300:])
rc, out, txt2 = run_role({"hardening_pve_pveproxy_allow_from": ["192.0.2.0/24"]}, txt)
check("ikinci kosu changed=0 (noop)", rc == 0 and "changed=0" in out and txt2 == txt, out[-200:])
rc, out, txt3 = run_role({"hardening_pve_pveproxy_allow_from": ["203.0.113.0/24"]}, "# a\n")
check("istemci listede degil -> rol DURUR, dosya DEGISMEZ", rc != 0 and txt3 == "# a\n" and "kapanırdı" in out, out[-300:])
rc, out, txt4 = run_role({"hardening_pve_pveproxy_allow_from": ["192.0.2.0/24"]}, 'ALLOW_FROM="10.0.0.0/8"\n')
check("kullanicinin ALLOW_FROM'u -> rol DURUR, dosya DEGISMEZ", rc != 0 and txt4 == 'ALLOW_FROM="10.0.0.0/8"\n', out[-300:])
rc, out, txt5 = run_role({"hardening_pve_pveproxy_allow_from": []}, "# a\n" + mine + "LISTEN_IP=\"x\"\n")
check("liste bosalinca blok kaldirilir, kullanicinin satirlari korunur", rc == 0 and BEGIN not in txt5 and 'LISTEN_IP="x"' in txt5, out[-300:])
rc, out, txt5b = run_role({"hardening_pve_pveproxy_allow_from": []}, mine)
check("liste bosalinca blok TEK BASINAYSA dosya SILINIR (bos dosya birakilmaz; sshpocket 0.8.2 notu)", rc == 0 and txt5b is None, out[-300:])
rc, out, txt6 = run_role({"hardening_pve_pveproxy_allow_from": []}, "# a\n")
check("liste bos ve blok yok: hicbir sey degismez (changed=0)", rc == 0 and "changed=0" in out and txt6 == "# a\n", out[-200:])
rc, out, txt7 = run_role({"hardening_platform": "generic", "hardening_pve_pveproxy_allow_from": ["192.0.2.0/24"]}, None)
check("Proxmox olmayan platformda NOT verir, dosya olusmaz", rc == 0 and txt7 is None and "Proxmox VE hostu değil" in out, out[-200:])
# dogrulama basarisiz -> eski icerik geri yuklenir (gercek uri: kapali portta basarisiz olur)
rc, out, txt8 = run_role({"hardening_pve_pveproxy_allow_from": ["192.0.2.0/24"], "hardening_pve_pveproxy_verify": True, "ansible_host": "127.0.0.1"}, "# once\n")
check("web arayuzu dogrulanamazsa ESKI icerik geri yazilir ve rol durur", rc != 0 and txt8 == "# once\n" and "ESKİ HALİNE" in out, out[-400:])
rc, out, txt9 = run_role({"hardening_pve_pveproxy_allow_from": ["192.0.2.0/24"], "hardening_pve_pveproxy_verify": True, "ansible_host": "127.0.0.1"}, None)
check("dosya onceden yoksa dogrulama basarisizliginda dosya SILINIR", rc != 0 and txt9 is None, out[-300:])

cv = {v["name"]: v for v in load("component.yml")["vars"] if isinstance(v, dict)}
v = cv.get("hardening_pve_pveproxy_allow_from")
check("component.yml: liste, varsayilan []", v is not None and v["type"] == "list[cidr]" and v["default"] == [], str(v))
check("docs/component-vars.md icerir", "`hardening_pve_pveproxy_allow_from`" in (ROOT / "docs/component-vars.md").read_text(encoding="utf-8"))
hy = load("playbooks/harden.yml")[0]["roles"]
ent = next((r for r in hy if isinstance(r, dict) and r["role"] == "hardening_pve_pveproxy"), None)
roles = [r["role"] for r in hy if isinstance(r, dict)]
check("harden.yml: `pveproxy` etiketiyle, geri alma agindan ONCE", ent is not None and ent["tags"] == ["pveproxy"] and roles.index("hardening_pve_pveproxy") < roles.index("hardening_rollback"))
print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
