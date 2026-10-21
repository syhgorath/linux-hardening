#!/usr/bin/env python3
"""hardening_pve_firewall: görev zinciri. Yazma yalnızca `hardening_pve_apply` AÇIKKEN ve --check değilken; sıra: enable 0 yaz -> compile -> enable 1 yaz -> restart -> durum;
başarısızlıkta önceki içerik geri yazılır; reddedilen planda HİÇBİR şey yazılmaz (gerçek ansible çalıştırması, geçici dizinde); playbook yapısı; harden.yml'e bağlı değil."""
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
        print(f"  FAIL {name} {detail}")


plan_tasks = yaml.safe_load((ROOT / "roles/hardening_pve_firewall/tasks/plan.yml").read_text(encoding="utf-8"))
tasks = plan_tasks + yaml.safe_load((ROOT / "roles/hardening_pve_firewall/tasks/main.yml").read_text(encoding="utf-8"))
names = [t["name"] for t in tasks]
mod = lambda t: next((k for k in t if k.startswith("ansible.builtin.")), "block")
block = next(t for t in tasks if "block" in t)
b = block["block"]
guard = b[:2]
b = b[2:]
bn = [t["name"] for t in b]
check("yazmadan once armed kontrolu: armed degilse DURUR", guard[0]["ansible.builtin.stat"]["path"].endswith("_armed_file }}") and "not hardening_pve_fw_armed.stat.exists" in guard[1]["when"] and "ansible.builtin.fail" in guard[1])

check("yazan her sey `apply` blogunun icinde (blok disinda copy/file/systemd/command-yazan yok)",
      all(mod(t) in {"ansible.builtin.stat", "ansible.builtin.slurp", "ansible.builtin.command", "ansible.builtin.script", "ansible.builtin.set_fact", "ansible.builtin.fail", "ansible.builtin.debug"} for t in tasks if "block" not in t))
check("blok kosulu: plan apply + hardening_pve_apply + --check degil", all(x in block["when"] for x in ("== 'apply'", "hardening_pve_apply | bool", "not ansible_check_mode")))
check("sira: enable 0 yaz -> compile -> enable 1 yaz -> restart -> durum", bn == ["Write the file DISABLED first (enable 0)", "Validate the rules without applying them (pve-firewall compile)", "Write the file ENABLED (enable 1)", "Apply now (pve-firewall restart)", "Verify the firewall is enabled and running"], bn)
check("ilk yazim enable: 0 icerigi, ikinci enable: 1 icerigi", "content_disabled" in b[0]["ansible.builtin.command"]["stdin"] and b[2]["ansible.builtin.command"]["stdin"].endswith("fw_plan.content }}"))
check("pmxcfs: yazma `tee` ile (copy pmxcfs'te 'Operation not permitted' verdi) ve hedef cluster.fw", all(t["ansible.builtin.command"]["argv"][0] == "tee" and "firewall_file" in t["ansible.builtin.command"]["argv"][1] for t in (b[0], b[2])))
check("tee yeni satir EKLEMEZ (stdin_add_newline: false), yoksa her kosuda dosya farkli sayilir", all(t["ansible.builtin.command"].get("stdin_add_newline") is False for t in (b[0], b[2])))
check("copy modulu hic kullanilmaz (pmxcfs'te basarisiz)", all("ansible.builtin.copy" not in (ROOT / "roles/hardening_pve_firewall/tasks" / f).read_text(encoding="utf-8") for f in ("main.yml", "plan.yml")))
check("compile uygulamaz (yalniz `pve-firewall compile`) ve hatada blok durur", b[1]["ansible.builtin.command"] == "pve-firewall compile" and "failed_when" not in b[1] and "ignore_errors" not in b[1])
check("durum `enabled/running` degilse basarisiz", "enabled/running" in b[4]["failed_when"])
rescue = block["rescue"]
check("rescue: geri alma betigi (restore) calisir, sonra DURUR (fail)",
      rescue[0]["ansible.builtin.include_role"] == {"name": "hardening_rollback", "tasks_from": "restore"} and "ansible.builtin.fail" in rescue[-1] and len(rescue) == 2)
check("okuma gorevleri --check'te de calisir", all(t.get("check_mode") is False for t in tasks if mod(t) in {"ansible.builtin.stat", "ansible.builtin.slurp", "ansible.builtin.script"} or t["name"].startswith("Client address")))
fail_idx = names.index("Stop because the Proxmox firewall cannot be managed safely")
check("ret (refuse) gorevi, blok ve onizlemeden ONCE ve plan 'refuse' iken calisir", fail_idx < names.index(block["name"] if "name" in block else "Apply the Proxmox firewall") and "== 'refuse'" in tasks[fail_idx]["when"])
d = yaml.safe_load((ROOT / "roles/hardening_pve_firewall/defaults/main.yml").read_text(encoding="utf-8"))
check("hardening_pve_apply varsayilan KAPALI (kazara gercek kosu olmaz)", d["hardening_pve_apply"] is False)
check("ek portlar varsayilan bos", d["hardening_pve_firewall_extra_ports"] == [])

# ---- playbook ----
pb = yaml.safe_load((ROOT / "playbooks/pve-firewall.yml").read_text(encoding="utf-8"))[0]
inc = lambda x: x["ansible.builtin.include_role"]
seq = [(inc(x)["name"], inc(x).get("tasks_from")) for x in pb["tasks"]]
check("sira: plan -> geri alma arm -> uygula -> dogrula(disarm)", seq == [("hardening_pve_firewall", "plan"), ("hardening_rollback", None), ("hardening_pve_firewall", None), ("hardening_verify_access", None)], str(seq))
check("arm yalniz plan 'apply' iken ve gercek kosuda (reddedilen/noop kosu armed BIRAKMAZ)", "== 'apply'" in pb["tasks"][1]["when"] and "hardening_pve_apply" in pb["tasks"][1]["when"])
check("dogrulama (disarm) yalniz arm edildiyse ve --check degilken", "== 'apply'" in pb["tasks"][3]["when"] and "hardening_pve_apply" in pb["tasks"][3]["when"] and "not ansible_check_mode" in pb["tasks"][3]["when"])
pt = " ".join(str(x) for x in pb["pre_tasks"])
check("Proxmox olmayan hedefte DURUR", "pveversion" in pt and "/etc/pve" in pt and "Stop when the target is not a Proxmox VE host" in pt)
check("gercek kosu geri alma aginsiz reddedilir", "hardening_rollback_enabled" in pt)
check("dogrulama: 8006 portu da denenir", pb["tasks"][3]["vars"]["hardening_verify_access_tcp_ports"] == [8006])
va = (ROOT / "roles/hardening_verify_access/tasks/main.yml").read_text(encoding="utf-8")
check("verify_access ek TCP portlarini kontrol makinesinden dener, disarm'dan ONCE", va.index("Verify extra TCP ports") < va.index("Disarm rollback safety net"))
hy = (ROOT / "playbooks/harden.yml").read_text(encoding="utf-8")
check("harden.yml bu role BAGLI DEGIL", "hardening_pve_firewall" not in hy)

# ---- gercek zincir (apply KAPALI): okuma + plan + ret/onizleme, gecici dizinde ----
def run(allow, marker_exists=False, existing=None, client="192.0.2.10", extra=None, apply=False):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        fw = td / "cluster.fw"
        if existing is not None:
            fw.write_text(existing, encoding="utf-8")
        cm = td / "corosync.conf"
        if marker_exists:
            cm.write_text("x", encoding="utf-8")
        ev = {"hardening_ssh_allow_from": allow, "hardening_pve_firewall_file": str(fw), "hardening_pve_cluster_marker": str(cm),
              "hardening_pve_firewall_extra_ports": extra or [], "hardening_pve_apply": apply, "hardening_pve_rollback_armed_file": str(td / "armed")}
        pbk = td / "p.yml"
        pbk.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "tasks": [
            {"ansible.builtin.include_role": {"name": "hardening_pve_firewall", "tasks_from": "plan"}}]}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pbk), "-e", json.dumps(ev)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg"), "ANSIBLE_ROLES_PATH": str(ROOT / "roles"), "SSH_CONNECTION": f"{client} 50000 198.51.100.1 22"})
        return r.returncode, r.stdout + r.stderr, (fw.read_text(encoding="utf-8") if fw.exists() else None)


rc, out, fw = run(["192.0.2.0/24"])
check("onizleme: basarili, dosya YAZILMADI, icerik gosterilir", rc == 0 and fw is None and "ÖNİZLEME (yazılmadı)" in out and "+management" in out, out[-400:])
rc, out, fw = run([])
check("allow_from bos -> durur, dosya yok", rc != 0 and fw is None and "hiçbir şey yazılmadı" in out and "allow_from" in out, out[-300:])
rc, out, fw = run(["192.0.2.0/24"], client="203.0.113.9")
check("istemci kapsanmiyor -> durur", rc != 0 and fw is None and "Kontrol makinesinin adresi" in out)
rc, out, fw = run(["192.0.2.0/24"], marker_exists=True)
check("kume isareti var -> durur", rc != 0 and "Küme düğümü" in out)
rc, out, fw = run(["192.0.2.0/24"], existing="[RULES]\nIN ACCEPT -p tcp -dport 80\n")
check("kullanici cluster.fw -> durur ve DOKUNMAZ", rc != 0 and fw == "[RULES]\nIN ACCEPT -p tcp -dport 80\n" and "kullanıcıya ait" in out)
rc, out, fw = run(["192.0.2.0/24"], extra=["3128/tcp"])
check("ek port onizlemede", rc == 0 and "-dport 3128" in out)
# noop: ayni icerik
plan = subprocess.run([sys.executable, str(ROOT / "roles/hardening_pve_firewall/files/pve_firewall_plan.py"), json.dumps({"allow_from": ["192.0.2.0/24"], "client_ip": "192.0.2.10", "clustered": False, "existing": None, "extra_ports": []})], capture_output=True, text=True)
same = json.loads(plan.stdout)["content"]
rc, out, fw = run(["192.0.2.0/24"], existing=same)
check("zaten istenen icerik -> noop mesaji, dosya ayni", rc == 0 and "zaten istenen içerikte" in out and fw == same)

# armed olmadan uygulama: role tek basina (main.yml) cagrilirsa HIC yazmaz
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    plan_pb = td / "p.yml"
    plan_pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "tasks": [
        {"ansible.builtin.include_role": {"name": "hardening_pve_firewall", "tasks_from": "plan"}},
        {"ansible.builtin.include_role": {"name": "hardening_pve_firewall"}}]}]), encoding="utf-8")
    ev = {"hardening_ssh_allow_from": ["192.0.2.0/24"], "hardening_pve_firewall_file": str(td / "cluster.fw"), "hardening_pve_cluster_marker": str(td / "nope"),
          "hardening_pve_apply": True, "hardening_pve_rollback_armed_file": str(td / "armed")}
    r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(plan_pb), "-e", json.dumps(ev)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg"), "ANSIBLE_ROLES_PATH": str(ROOT / "roles"), "SSH_CONNECTION": "192.0.2.10 50000 198.51.100.1 22"})
    check("armed degilken uygulama DURUR ve dosya YAZILMAZ", r.returncode != 0 and "armed değil" in r.stdout + r.stderr and not (td / "cluster.fw").exists(), (r.stdout + r.stderr)[-300:])

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
