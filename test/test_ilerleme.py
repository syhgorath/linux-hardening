#!/usr/bin/env python3
"""SSHPOCKET_PROGRESS satirlari (callback_plugins/sshpocket_progress.py): gercek Ansible, sahte roller, ansible.cfg baska calisma dizininden."""
import os
import re
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
        print(f"  FAIL {name} {str(detail)[-900:]}")


def role(base, name, tasks):
    d = base / "roles" / f"hardening_{name}" / "tasks"
    d.mkdir(parents=True)
    (d / "main.yml").write_text(yaml.safe_dump(tasks), encoding="utf-8")


def run(base, roles, plan, check_mode=False):
    play = {"hosts": "localhost", "connection": "local", "gather_facts": False,
            "pre_tasks": [] if plan is None else [{"ansible.builtin.set_fact": {"hardening_progress_areas": plan}}],
            "roles": [f"hardening_{r}" for r in roles]}
    pb = base / "p.yml"
    pb.write_text(yaml.safe_dump([play]), encoding="utf-8")
    env = {**os.environ, "ANSIBLE_CONFIG": str(ROOT / "ansible.cfg"), "ANSIBLE_ROLES_PATH": str(base / "roles"), "ANSIBLE_NOCOLOR": "1", "ANSIBLE_BECOME": "False"}
    cmd = ["ansible-playbook", "-i", "localhost,", str(pb)] + (["--check"] if check_mode else [])
    r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env, cwd=base)  # cwd: paket koku DEGIL
    lines = [ln.strip() for ln in r.stdout.splitlines() if "SSHPOCKET_PROGRESS" in ln]
    return r.returncode, lines, r.stdout + r.stderr


with tempfile.TemporaryDirectory() as d:
    base = Path(d)
    role(base, "alpha", [{"name": "yazar", "ansible.builtin.command": "true", "changed_when": True}])
    role(base, "beta", [
        {"name": "uyari", "ansible.builtin.debug": {"msg": "UYARI: deneme"}},
        {"name": "atlanir", "ansible.builtin.debug": {"msg": "x"}, "when": False},
    ])
    role(base, "gamma", [{"name": "hata", "ansible.builtin.fail": {"msg": "bozuk"}}])
    role(base, "delta", [{"name": "hic", "ansible.builtin.debug": {"msg": "d"}}])
    role(base, "aide", [{"name": "uzun", "ansible.builtin.command": "sleep 4", "async": 30, "poll": 1}])
    plan = ["alpha", "beta", "gamma", "delta"]

    rc, lines, out = run(base, ["alpha", "beta"], plan)
    check("uygulama: rc=0", rc == 0, out)
    check("uygulama: alpha basladi/bitti, degisen=1 kesin=1", lines[:2] == [
        "SSHPOCKET_PROGRESS alan=alpha sira=1/4 durum=basladi",
        "SSHPOCKET_PROGRESS alan=alpha sira=1/4 durum=bitti degisen=1 atlanan=0 kesin=1"], lines)
    check("uygulama: beta atlanan=1 uyari=1, sira 2/4", lines[2:] == [
        "SSHPOCKET_PROGRESS alan=beta sira=2/4 durum=basladi",
        "SSHPOCKET_PROGRESS alan=beta sira=2/4 durum=bitti degisen=0 atlanan=1 kesin=1 uyari=1"], lines)
    check("satirlar tek satir, anahtar=deger, SSHPOCKET_RESULT sozcugu yok", all(
        re.fullmatch(r'SSHPOCKET_PROGRESS( [a-z_]+=[A-Za-z0-9_/.\-]+)+"?,?', ln) and "SSHPOCKET_RESULT" not in ln for ln in lines), lines)
    check("alan basina 'uyari' yalniz n>0 iken yazilir", "uyari=0" not in " ".join(lines), lines)

    rc, lines, out = run(base, ["alpha", "beta"], plan, check_mode=True)
    check("onizleme: komut gorevi atlanir -> degisen=0 atlanan=1 kesin=0", "SSHPOCKET_PROGRESS alan=alpha sira=1/4 durum=bitti degisen=0 atlanan=1 kesin=0" in lines, lines)
    check("onizleme: when=false atlama kesinligi bozmaz (beta kesin=1)", "SSHPOCKET_PROGRESS alan=beta sira=2/4 durum=bitti degisen=0 atlanan=1 kesin=1 uyari=1" in lines, lines)

    rc, lines, out = run(base, ["alpha", "gamma", "delta"], plan)
    check("hata: rc!=0, gamma icin basladi var, bitti YOK, delta hic yok", rc != 0 and any("alan=gamma" in x and "basladi" in x for x in lines)
          and not any("alan=gamma" in x and "bitti" in x for x in lines) and not any("alan=delta" in x for x in lines), lines)
    check("hata: onceki alan (alpha) yine de bitti yazdi", any("alan=alpha" in x and "bitti" in x for x in lines), lines)

    for ad, bozuk in (("bozuk json", "{bad"), ("bosluklu ad", ["a b"]), ("ascii disi", ["çay"])):
        rc, lines, out = run(base, ["alpha"], bozuk)
        check(f"plan {ad}: Ansible dusmez, satir yazilmaz, uyari de basmaz", rc == 0 and lines == [] and "Callback dispatch" not in out, (rc, lines, out))
    rc, lines, out = run(base, ["alpha"], None)
    check("plan yok: Ansible dusmez, satir yazilmaz", rc == 0 and lines == [], (rc, lines, out))

    rc, lines, out = run(base, ["aide"], ["aide"])
    check("AIDE: ilk async poll'da bekle_tahmin satiri (bir kez)", sum("bekle_tahmin=300" in x for x in lines) == 1, lines)
    check("AIDE: ayni alan basladi -> basladi(bekle_tahmin) -> bitti sirasi", [x.split("durum=")[1].split()[0] for x in lines] == ["basladi", "basladi", "bitti"], lines)
    rc, lines, out = run(base, ["aide"], ["aide"], check_mode=True)
    check("AIDE onizleme: bekle_tahmin yok (calismadi)", not any("bekle_tahmin" in x for x in lines), lines)

# harden.yml: plan, roles: ile ayni sira ve adlar (rollback altyapi, listede yok)
pb = yaml.safe_load((ROOT / "playbooks/harden.yml").read_text(encoding="utf-8"))[0]
roles = [(r["role"] if isinstance(r, dict) else r) for r in pb["roles"]]
want = [r[len("hardening_"):] for r in roles if r not in ("hardening_rollback",)]
task = next(t for t in pb["pre_tasks"] if t.get("name", "").startswith("İlerleme planı"))
got = re.findall(r"'id': '([a-z_0-9]+)'", task["ansible.builtin.set_fact"]["hardening_progress_areas"])
check("harden.yml: ilerleme plani roles: ile ayni sirada", want == got, f"roles={want} plan={got}")
check("harden.yml: plan gorevi always etiketli (--tags ile atlanmaz)", "always" in task.get("tags", []), task)


# Gercek plan gorevi: alan anahtarlari ve platform plana yansiyor (gercek Ansible, harden.yml'deki gorevin kendisi)
def plan_of(extra):
    with tempfile.TemporaryDirectory() as d:
        pbk = Path(d) / "q.yml"
        pbk.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": extra,
                                        "tasks": [task, {"ansible.builtin.debug": {"msg": "PLAN={{ hardening_progress_areas | join(',') }}"}}]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", "localhost,", str(pbk)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "ansible.cfg"), "ANSIBLE_BECOME": "False"}, cwd=d)
        m = re.search(r"PLAN=([a-z_0-9,]*)", r.stdout)
        return m.group(1).split(",") if m and m.group(1) else None if not m else []


default_plan = plan_of({})
check("plan varsayilan: docker ve pam_faillock KAPALI, digerleri acik", default_plan == [w for w in want if w not in ("docker", "pam_faillock")], default_plan)
check("plan: proxmox-host'ta ufw yok", plan_of({"hardening_platform": "proxmox-host"}) == [w for w in default_plan if w != "ufw"], plan_of({"hardening_platform": "proxmox-host"}))
check("plan: alan anahtarlari yansir (ssh/aide kapali, docker acik)", plan_of({"hardening_ssh_enabled": False, "hardening_aide_enabled": False, "hardening_docker_enabled": True})
      == [w for w in want if w not in ("ssh", "aide", "pam_faillock")], plan_of({"hardening_ssh_enabled": False, "hardening_aide_enabled": False, "hardening_docker_enabled": True}))

import configparser
cp = configparser.ConfigParser(interpolation=None)
cp.read(ROOT / "ansible.cfg", encoding="utf-8")
check("ansible.cfg: eklenti etkin ve yol pakete gore goreli", (cp.get("defaults", "callbacks_enabled"), cp.get("defaults", "callback_plugins")) == ("sshpocket_progress", "./callback_plugins"))

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
