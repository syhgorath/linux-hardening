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


tasks = yaml.safe_load((ROOT / "roles/hardening_pve_firewall/tasks/main.yml").read_text(encoding="utf-8"))
names = [t["name"] for t in tasks]
mod = lambda t: next((k for k in t if k.startswith("ansible.builtin.")), "block")
block = next(t for t in tasks if "block" in t)
b = block["block"]
bn = [t["name"] for t in b]

check("yazan her sey `apply` blogunun icinde (blok disinda copy/file/systemd/command-yazan yok)",
      all(mod(t) in {"ansible.builtin.stat", "ansible.builtin.slurp", "ansible.builtin.command", "ansible.builtin.script", "ansible.builtin.set_fact", "ansible.builtin.fail", "ansible.builtin.debug"} for t in tasks if "block" not in t))
check("blok kosulu: plan apply + hardening_pve_apply + --check degil", all(x in block["when"] for x in ("== 'apply'", "hardening_pve_apply | bool", "not ansible_check_mode")))
check("sira: enable 0 yaz -> compile -> enable 1 yaz -> restart -> durum", bn == ["Write the file DISABLED first (enable 0)", "Validate the rules without applying them (pve-firewall compile)", "Write the file ENABLED (enable 1)", "Apply now (pve-firewall restart)", "Verify the firewall is enabled and running"], bn)
check("ilk yazim enable: 0 icerigi, ikinci enable: 1 icerigi", "content_disabled" in b[0]["ansible.builtin.copy"]["content"] and b[2]["ansible.builtin.copy"]["content"].endswith("fw_plan.content }}"))
check("copy: unsafe_writes (pmxcfs) ve sahip/izin VERILMEZ", all(t["ansible.builtin.copy"].get("unsafe_writes") is True and not ({"owner", "group", "mode"} & set(t["ansible.builtin.copy"])) for t in (b[0], b[2])))
check("compile uygulamaz (yalniz `pve-firewall compile`) ve hatada blok durur", b[1]["ansible.builtin.command"] == "pve-firewall compile" and "failed_when" not in b[1] and "ignore_errors" not in b[1])
check("durum `enabled/running` degilse basarisiz", "enabled/running" in b[4]["failed_when"])
rescue = block["rescue"]
check("rescue: onceki icerigi geri yazar, yoksa siler, sonra DURUR (fail)",
      "ansible.builtin.copy" in rescue[0] and "b64decode" in rescue[0]["ansible.builtin.copy"]["content"] and rescue[1]["ansible.builtin.file"]["state"] == "absent" and "ansible.builtin.fail" in rescue[-1])
check("okuma gorevleri --check'te de calisir", all(t.get("check_mode") is False for t in tasks if mod(t) in {"ansible.builtin.stat", "ansible.builtin.slurp", "ansible.builtin.script"} or t["name"].startswith("Client address")))
fail_idx = names.index("Stop because the Proxmox firewall cannot be managed safely")
check("ret (refuse) gorevi, blok ve onizlemeden ONCE ve plan 'refuse' iken calisir", fail_idx < names.index(block["name"] if "name" in block else "Apply the Proxmox firewall") and "== 'refuse'" in tasks[fail_idx]["when"])
d = yaml.safe_load((ROOT / "roles/hardening_pve_firewall/defaults/main.yml").read_text(encoding="utf-8"))
check("hardening_pve_apply varsayilan KAPALI (kazara gercek kosu olmaz)", d["hardening_pve_apply"] is False)
check("ek portlar varsayilan bos", d["hardening_pve_firewall_extra_ports"] == [])

# ---- playbook ----
pb = yaml.safe_load((ROOT / "playbooks/pve-firewall.yml").read_text(encoding="utf-8"))[0]
roles = [r if isinstance(r, str) else r["role"] for r in pb["roles"]]
check("rol sirasi: hardening_rollback (arm) -> hardening_pve_firewall", roles == ["hardening_rollback", "hardening_pve_firewall"], str(roles))
check("arm yalniz gercek kosuda (hardening_pve_apply)", "hardening_pve_apply" in pb["roles"][0]["when"])
pt = " ".join(str(t) for t in pb["pre_tasks"])
check("Proxmox olmayan hedefte DURUR", "pveversion" in pt and "/etc/pve" in pt and "Stop when the target is not a Proxmox VE host" in pt)
check("gercek kosu geri alma aginsiz reddedilir", "hardening_rollback_enabled" in pt)
post = pb["post_tasks"][0]
check("dogrulama: hardening_verify_access + 8006 portu, yalniz gercek kosuda", post["ansible.builtin.include_role"]["name"] == "hardening_verify_access" and post["vars"]["hardening_verify_access_tcp_ports"] == [8006] and "hardening_pve_apply" in post["when"])
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
              "hardening_pve_firewall_extra_ports": extra or [], "hardening_pve_apply": apply}
        pbk = td / "p.yml"
        pbk.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "tasks": [
            {"ansible.builtin.include_role": {"name": "hardening_pve_firewall"}}]}]), encoding="utf-8")
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

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
