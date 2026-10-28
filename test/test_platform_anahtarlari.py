#!/usr/bin/env python3
"""sshpocket menu suzmesi (platform_var, platforms, group) ve kosulsuz gorevlerin sunucu basina anahtarlari.
Anahtarlar: varsayilan true = davranis degismez; false gorevi atlar. Gorevler gercek Ansible ile, hedef yollari gecici dizine cevrilerek calistirilir."""
import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {str(detail)[-500:]}")


comp = yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))
vars_ = {v["name"]: v for v in comp["vars"]}

# ---- manifest ----
check("platform_var = hardening_platform ve tanimli", comp.get("platform_var") == "hardening_platform" and "hardening_platform" in vars_)
check("pve_firewall_preview/apply platforms=[proxmox-host]", all(comp["actions"][a].get("platforms") == ["proxmox-host"] for a in ("pve_firewall_preview", "pve_firewall_apply")))
check("diger eylemlerde platforms YOK (her platformda gorunur)", all("platforms" not in a for n, a in comp["actions"].items() if not n.startswith("pve_firewall")))
pve = [n for n, v in vars_.items() if v.get("platforms") == ["proxmox-host"]]
check("Proxmox degiskenleri platforms+group=Proxmox tasir", len(pve) == 10 and all(vars_[n].get("group") == "Proxmox" for n in pve), pve)
check("hardening_pve_* degiskenlerinin hepsi platformlu", all(vars_[n].get("platforms") for n in vars_ if n.startswith("hardening_pve_")), [n for n in vars_ if n.startswith("hardening_pve_") and not vars_[n].get("platforms")])
check("platformlu hicbir degisken required degil", not any(v.get("required") for v in vars_.values() if v.get("platforms")))
check("ortak degiskenlere platforms eklenmemis (hardening_ssh_allow_from, hardening_platform)", "platforms" not in vars_["hardening_ssh_allow_from"] and "platforms" not in vars_["hardening_platform"])
tog = ["hardening_sysctl_hardening", "hardening_disable_network_protocols", "hardening_disable_filesystem_modules", "hardening_unattended_upgrades", "hardening_legal_banner", "hardening_journald_persistent"]
check("6 anahtar: bool, varsayilan true (davranis degismez), rol varsayilaniyla ayni", all(vars_[n]["type"] == "bool" and vars_[n]["default"] is True and not vars_[n].get("warn_if") for n in tog))

# tutarlilik denetimi gecersiz platform bilgisini yakalar
def consistency(mutate):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        for e in ROOT.iterdir():
            if e.name not in (".git", ".venv", "component.yml", "component.json", "scripts"):
                os.symlink(e, d / e.name)
        (d / "component.json").write_bytes((ROOT / "component.json").read_bytes())
        (d / "scripts").mkdir()
        (d / "scripts/check-consistency.py").write_bytes((ROOT / "scripts/check-consistency.py").read_bytes())
        m = copy.deepcopy(comp)
        mutate(m)
        (d / "component.yml").write_text(yaml.safe_dump(m, allow_unicode=True, sort_keys=False), encoding="utf-8")
        r = subprocess.run([sys.executable, "-I", str(d / "scripts/check-consistency.py")], capture_output=True, text=True, cwd=d)
        return r.stdout + r.stderr


def mut_no_pv(m):
    del m["platform_var"]


def mut_bad_platform(m):
    m["actions"]["pve_firewall_apply"]["platforms"] = ["windows"]


def mut_req_gap(m):
    m["actions"]["pve_firewall_preview"]["platforms"] = ["raspberry-pi"]


def mut_required_hidden(m):
    next(v for v in m["vars"] if v["name"] == "hardening_pve_web_allow_from")["required"] = True


def mut_group_long(m):
    next(v for v in m["vars"] if v["name"] == "hardening_pve_apply")["group"] = "x" * 41


def mut_group_missing(m):
    del next(v for v in m["vars"] if v["name"] == "hardening_umask")["group"]


ok_out = consistency(lambda m: None)
check("denetim temiz manifestte gecer", "OK:" in ok_out, ok_out)
for name, fn, key in (("platform_var yok", mut_no_pv, "platform_var"), ("gecersiz platform", mut_bad_platform, "geçersiz"), ("requires platform bosluğu", mut_req_gap, "kapsamalı"),
                      ("platformlu + required", mut_required_hidden, "required"), ("group 41 karakter", mut_group_long, "group"), ("group yok", mut_group_missing, "group yok")):
    out = consistency(fn)
    check(f"denetim yakalar: {name}", "TUTARSIZLIK" in out and key in out, out)


check("her degiskenin group'u var (126/126)", all(v.get("group") for v in vars_.values()), [n for n, v in vars_.items() if not v.get("group")])

# ---- anahtarlar: gercek gorevler, hedef yollari gecici dizinde ----
def run(tasks_file, names, extra, tmp):
    tasks = yaml.safe_load((ROOT / tasks_file).read_text(encoding="utf-8"))
    keep = []
    for t in tasks:
        if t.get("name") in names:
            t = copy.deepcopy(t)
            t.pop("notify", None)
            mod = next(k for k in t if k.startswith("ansible.builtin."))
            args = t[mod]
            if args.get("src", "").endswith(".j2"):
                args["src"] = str(ROOT / "roles/hardening_kernel/templates" / args["src"])
            if "dest" in args:
                args["dest"] = str(tmp / Path(args["dest"]).name)
                args["owner"] = str(os.getuid())
                args["group"] = str(os.getgid())
            keep.append(t)
    defaults = {}
    for r in ("hardening_kernel", "hardening_base"):
        defaults.update(yaml.safe_load((ROOT / f"roles/{r}/defaults/main.yml").read_text(encoding="utf-8")) or {})
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": defaults, "tasks": keep}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb), "-e", json.dumps(extra)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
        return r.returncode, r.stdout + r.stderr


cases = [("roles/hardening_kernel/tasks/main.yml", "Apply sysctl hardening", "hardening_sysctl_hardening", "60-hardening.conf"),
         ("roles/hardening_kernel/tasks/main.yml", "Disable unused network protocols", "hardening_disable_network_protocols", "60-hardening-protocols.conf"),
         ("roles/hardening_kernel/tasks/main.yml", "Disable unused filesystem modules (CIS 1.1.1.x)", "hardening_disable_filesystem_modules", "60-hardening-filesystems.conf"),
         ("roles/hardening_base/tasks/main.yml", "Enable automatic security updates (otomatik reboot YOK)", "hardening_unattended_upgrades", "20auto-upgrades"),
         ("roles/hardening_base/tasks/main.yml", "Legal banner", "hardening_legal_banner", None),
         ("roles/hardening_base/tasks/main.yml", "Persistent, compressed journald storage", "hardening_journald_persistent", "60-hardening.conf")]
for tf, task, var, fname in cases:
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        extra = {"hardening_ssh_allow_from": ["192.0.2.0/24"]}
        if task == "Legal banner":
            # loop /etc/issue ve /etc/issue.net: item yolu gecici dizine cevrilemez, bu yuzden yalnizca atlama davranisi (skipped) denetlenir
            tasks = yaml.safe_load((ROOT / tf).read_text(encoding="utf-8"))
            tk = next(x for x in tasks if x.get("name") == task)
            check(f"{var}: gorev when ile bagli", "hardening_legal_banner | bool" in str(tk.get("when")), tk.get("when"))
            continue
        rc, out = run(tf, [task], {**extra, var: False}, t)
        check(f"{var}=false: gorev atlanir, dosya yazilmaz", rc == 0 and "skipped=1" in out and not (t / fname).exists(), out)
        rc, out = run(tf, [task], {**extra, var: True}, t)
        check(f"{var}=true: dosya yazilir (davranis ayni)", rc == 0 and (t / fname).exists(), out)
        rc, out = run(tf, [task], extra, t)
        check(f"{var} varsayilan: 2. kosu degisiklik yok", rc == 0 and "changed=0" in out, out)

# paket gorevi (apt) calistirilmaz; when baglantisi denetlenir
tasks = yaml.safe_load((ROOT / "roles/hardening_base/tasks/main.yml").read_text(encoding="utf-8"))
tk = next(x for x in tasks if x.get("name") == "Install unattended-upgrades")
check("unattended-upgrades kurulum gorevi anahtara bagli", "hardening_unattended_upgrades | bool" in str(tk.get("when")))
kb = [x for x in tasks if "pvebanner" in x.get("name", "") and "Keep" in x.get("name", "")]
check("Proxmox banner drop-in'i yasal uyari anahtarina da bagli", kb and "hardening_legal_banner | bool" in str(kb[0].get("when")))
sys.exit(1 if fails else 0)
