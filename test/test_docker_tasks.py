#!/usr/bin/env python3
"""hardening_docker: rol görevleri. Gerçek Docker gerekmez: okuma görevlerinin ÇIKTILARI (register) sahte verilir, geri kalan görevler (hazırlık, betik çağrısı, yazma) gerçek
`ansible-playbook` ile geçici dizinde çalışır. Hedefler: varsayılan KAPALI, Docker yoksa atla, okumalar salt okunur, rapor girdisi doğru kurulur, daemon.json yalnızca
değişince ve hata yokken yazılır (yedekle), yeniden başlatma yalnızca hardening_docker_restart=true iken.
"""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ROLE = ROOT / "roles/hardening_docker"
fails = 0


def check(name, want, got):
    global fails
    if want == got:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name}: beklenen={want!r} gercek={got!r}")


def flat(tasks):
    for t in tasks or []:
        yield t
        for k in ("block", "rescue", "always"):
            yield from flat(t.get(k))


tasks = yaml.safe_load((ROLE / "tasks/main.yml").read_text(encoding="utf-8"))
allt = list(flat(tasks))
by = {t.get("name"): t for t in allt}
defaults = yaml.safe_load((ROLE / "defaults/main.yml").read_text(encoding="utf-8"))
handlers = yaml.safe_load((ROLE / "handlers/main.yml").read_text(encoding="utf-8"))

# 1) varsayılanlar ve statik yapı
check("varsayilan: rol KAPALI, daemon birlestirme KAPALI, yeniden baslatma KAPALI", (False, False, False),
      (defaults["hardening_docker_enabled"], defaults["hardening_docker_daemon_manage"], defaults["hardening_docker_restart"]))
check("varsayilan izinli yayinlanan portlar: 80, 443", [80, 443], defaults["hardening_docker_allowed_published"])
check("varsayilan ayarlar: live-restore, json-file + log-opts max-size/max-file", True,
      defaults["hardening_docker_daemon_settings"]["live-restore"] is True and set(defaults["hardening_docker_daemon_settings"]["log-opts"]) == {"max-size", "max-file"})
check("tum gorevler hardening_docker_enabled ile kapanir", True, "hardening_docker_enabled" in str(tasks[0]["when"]))
check("Docker kurulu degilse (dockerd yok) kontroller atlanir", True, "hardening_docker_bin.stat.exists" in str(by["Docker checks"]["when"]))
reads = [by[n] for n in ("Read daemon.json", "Docker group members", "Published container ports (read-only)", "Listening TCP sockets (read-only)")]
check("okuma gorevleri: --check'te de calisir, degisiklik saymaz, basarisiz olsa rol durmaz", True,
      all(t.get("check_mode") is False and t.get("failed_when") is False for t in reads) and all(t.get("changed_when") is False for t in reads[1:]))
check("hicbir gorev docker komutuyla degisiklik yapmaz (run/rm/stop/kill/exec/pull/build/prune yok)", True,
      not any(re.search(r"\bdocker\s+(run|rm|stop|kill|exec|pull|build|prune|restart|rmi|network|volume)\b", str(t.get("ansible.builtin.command", ""))) for t in allt))
check("daemon.json birlestirme kendi degiskeniyle (daemon_manage) kapanir", True,
      all("hardening_docker_daemon_manage" in str(by[n]["when"]) for n in ("Compute the merged daemon.json", "Merge settings into daemon.json")))
w = by["Merge settings into daemon.json"]
check("yazma: yalnizca DEGISINCE ve HATA YOKKEN, yedek alinir, 0644 root", True,
      "merge.changed" in str(w["when"]) and "error | length == 0" in str(w["when"]) and w["ansible.builtin.copy"]["backup"] is True and w["ansible.builtin.copy"]["mode"] == "0644")
check("yazma bildirimi 'Restart docker' handler'ina gider", True, w["notify"] == "Restart docker" and handlers[0]["name"] == "Restart docker")
check("handler yalnizca hardening_docker_restart=true iken calisir", True, "hardening_docker_restart" in str(handlers[0]["when"]))

# 2) uçtan uca: sahte register + gerçek betik çağrıları
SS = ["LISTEN 0      4096         0.0.0.0:2375       0.0.0.0:*", "LISTEN 0      4096       127.0.0.53%lo:53       0.0.0.0:*", "LISTEN 0      4096            [::]:22          [::]:*"]
PS = ["proxy|0.0.0.0:80->80/tcp, :::80->80/tcp", "redis|0.0.0.0:6379->6379/tcp, :::6379->6379/tcp", "db|3306/tcp"]
DJ = '{"iptables": false, "data-root": "/srv/docker"}'


def play(extra_tasks, vars_, pre_regs):
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        tl = [{"ansible.builtin.set_fact": pre_regs}] + extra_tasks
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": vars_, "tasks": tl}], allow_unicode=True), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg"), "ANSIBLE_ROLES_PATH": str(ROOT / "roles")})
        return r.returncode, r.stdout + r.stderr


def script_task(t):
    cp = dict(t)
    sc = dict(cp["ansible.builtin.script"])
    sc["cmd"] = sc["cmd"].replace("docker_report.py", str(ROLE / "files/docker_report.py")).replace("docker_daemon_merge.py", str(ROLE / "files/docker_daemon_merge.py"))
    cp["ansible.builtin.script"] = sc
    return cp


regs = {
    "hardening_docker_daemon_raw": {"content": base64.b64encode(DJ.encode()).decode()},
    "hardening_docker_group": {"stdout": "docker:x:999:alice,bob"},
    "hardening_docker_ps": {"stdout_lines": PS},
    "hardening_docker_ss": {"stdout_lines": SS},
}
vars_ = {"hardening_docker_allowed_published": [80, 443], "hardening_docker_daemon_settings": defaults["hardening_docker_daemon_settings"]}
dbg = {"ansible.builtin.debug": {"msg": "INPUT={{ hardening_docker_report_input | to_json | b64encode }}"}}
rc, out = play([by["Prepare the Docker report input"], dbg], vars_, regs)
m = re.search(r"INPUT=(\S+?)\"?\s*$", out, re.M)
inp = json.loads(base64.b64decode(m.group(1))) if m else {}
check("rapor girdisi: docker grubu uyeleri ayrisir (alice, bob)", ["alice", "bob"], inp.get("group_members"))
check("rapor girdisi: ss ciktisindan YEREL adresler cikarilir (0.0.0.0:2375, [::]:22)", ["0.0.0.0:2375", "127.0.0.53%lo:53", "[::]:22"], inp.get("listening"))
check("rapor girdisi: daemon.json metni base64'ten cozulur, portlar ve izinli liste aktarilir", (DJ, PS, [80, 443]), (inp.get("daemon_text"), inp.get("ports"), inp.get("allowed_published")))
rc, out = play([by["Prepare the Docker report input"], script_task(by["Evaluate the Docker setup"]), by["Parse the Docker report"],
                {"ansible.builtin.debug": {"msg": "REP={{ hardening_docker_report | to_json | b64encode }}"}}], vars_, regs)
m = re.search(r"REP=(\S+?)\"?\s*$", out, re.M)
rep = json.loads(base64.b64decode(m.group(1))) if m else {}
txt = " ".join(rep.get("warnings", []))
check("uctan uca rapor: warn; redis:6379 yayinli, docker grubu, 2375 API, iptables:false hepsi yakalanir", (True, True, True, True, True),
      (rep.get("status") == "warn", "redis:6379/tcp" in txt, "alice, bob" in txt, "2375" in txt, "iptables" in txt))
check("uctan uca rapor: izinli 80 uyari degil, yayinlanmamis db (3306) uyari degil", (False, False), ("proxy:80" in txt, "3306" in txt))
regs2 = {**regs, "hardening_docker_group": {"stdout": ""}, "hardening_docker_ps": {"stdout_lines": [PS[0]]}, "hardening_docker_ss": {"stdout_lines": SS[2:]},
         "hardening_docker_daemon_raw": {"failed": True}}
rc, out = play([by["Prepare the Docker report input"], script_task(by["Evaluate the Docker setup"]), by["Parse the Docker report"],
                {"ansible.builtin.debug": {"msg": "REP={{ hardening_docker_report | to_json | b64encode }}"}}], vars_, regs2)
m = re.search(r"REP=(\S+?)\"?\s*$", out, re.M)
rep = json.loads(base64.b64decode(m.group(1))) if m else {}
check("temiz sunucu (grup yok, yalniz izinli port, daemon.json okunamadi): ok", ("ok", []), (rep.get("status"), rep.get("warnings")))

# 3) birleştirme: gerçek betik + yazma
with tempfile.TemporaryDirectory() as d:
    dest = Path(d) / "daemon.json"
    dest.write_text('{"data-root": "/srv/docker"}', encoding="utf-8")
    merge_tasks = [script_task(by["Compute the merged daemon.json"]), by["Parse the merged daemon.json"]]
    cp = dict(w); cpm = dict(cp["ansible.builtin.copy"]); cpm["dest"] = str(dest); cpm.pop("owner"); cpm.pop("group"); cp["ansible.builtin.copy"] = cpm; cp.pop("notify")
    v = {**vars_, "hardening_docker_daemon_manage": True}
    regs3 = {"hardening_docker_daemon_raw": {"content": base64.b64encode(dest.read_bytes()).decode()}}
    rc, out = play(merge_tasks + [cp], v, regs3)
    got = json.loads(dest.read_text(encoding="utf-8"))
    check("birlestirme gercek calisir: mevcut data-root KORUNUR, live-restore eklenir", (0, "/srv/docker", True), (rc, got.get("data-root"), got.get("live-restore")))
    check("birlestirme: yedek dosya alinir (daemon.json.*~)", True, len(list(Path(d).glob("daemon.json.*"))) == 1)
    regs3 = {"hardening_docker_daemon_raw": {"content": base64.b64encode(dest.read_bytes()).decode()}}
    before = dest.read_text(encoding="utf-8")
    rc, out = play(merge_tasks + [cp], v, regs3)
    check("birlestirme ikinci kosu: dosya degismez, yeni yedek yok (idempotent)", (before, 1), (dest.read_text(encoding="utf-8"), len(list(Path(d).glob("daemon.json.*")))))
    dest.write_text("{ bozuk", encoding="utf-8")
    regs3 = {"hardening_docker_daemon_raw": {"content": base64.b64encode(b"{ bozuk").decode()}}
    rc, out = play(merge_tasks + [by["Refuse to touch an unreadable daemon.json"], cp], v, regs3)
    check("bozuk daemon.json: UYARI yazilir, dosyaya DOKUNULMAZ", (0, "{ bozuk", True), (rc, dest.read_text(encoding="utf-8"), "daemon.json birleştirilemedi" in out))

# 4) auditd Docker kuralları: yalnızca VAR OLAN yollar
atasks = yaml.safe_load((ROOT / "roles/hardening_auditd/tasks/main.yml").read_text(encoding="utf-8"))
aby = {t.get("name"): t for t in atasks}
adef = yaml.safe_load((ROOT / "roles/hardening_auditd/defaults/main.yml").read_text(encoding="utf-8"))
check("auditd: Docker kurallari varsayilan ACIK ama yalniz var olan yollar icin", True, adef["hardening_auditd_docker_rules"] is True)
check("auditd: /var/lib/docker izlenecek yollarda YOK (gurultulu)", True, not any("/var/lib/docker" in x for x in adef["hardening_auditd_docker_paths"]))
check("auditd: kural dosyasi gorevinden ONCE yollar taranir", True, [t.get("name") for t in atasks].index("Remember the Docker paths that exist") < [t.get("name") for t in atasks].index("Audit rules"))
with tempfile.TemporaryDirectory() as d:
    (Path(d) / "dockerd").write_text("x"); (Path(d) / "etc-docker").mkdir()
    paths = [f"{d}/dockerd", f"{d}/etc-docker", f"{d}/yok-1", f"{d}/yok-2"]
    tl = [aby["Look for Docker files to audit"], aby["Remember the Docker paths that exist"],
          {"ansible.builtin.debug": {"msg": "EX={{ hardening_auditd_docker_existing | to_json | b64encode }}"}}]
    rc, out = play(tl, {"hardening_auditd_docker_rules": True, "hardening_auditd_docker_paths": paths}, {"unused": 1})
    m = re.search(r"EX=(\S+?)\"?\s*$", out, re.M)
    got = json.loads(base64.b64decode(m.group(1))) if m else None
    check("auditd: yalnizca var olan yollar kurala girer (dosya ve dizin; olmayanlar atlanir)", [f"{d}/dockerd", f"{d}/etc-docker"], got)
    rc, out = play(tl[:2] + [{"ansible.builtin.debug": {"msg": "TANIMLI={{ hardening_auditd_docker_existing is defined }}"}}], {"hardening_auditd_docker_rules": False, "hardening_auditd_docker_paths": paths}, {"unused": 1})
    check("auditd: hardening_auditd_docker_rules=false iken hicbir yol taranmaz/eklenmez", True, "TANIMLI=False" in out)

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
