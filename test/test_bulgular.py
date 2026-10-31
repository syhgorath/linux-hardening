#!/usr/bin/env python3
"""bulgular.tsv uretimi (filter_plugins + playbooks/tasks/bulgular.yml + vars/bulgular-eslesme.tsv): gercek Ansible, gercek Lynis satirlari."""
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "test/fixtures/lynis-report-ornek.dat"
fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {str(detail)[-900:]}")


HEADER = ["kimlik", "risk", "tur", "aciklama", "ayrinti", "oneri", "alan", "deger", "kapanir_varsayilan", "platform"]


def run(report, scan_dir, mapping_path=None):
    """Gercek gorev dosyasini calistirir. mapping_path verilirse vars/bulgular-eslesme.tsv yerine onu okutmak icin kopyalanmis bir playbook dizini kullanilir."""
    base = Path(tempfile.mkdtemp())
    (base / "playbooks").mkdir()
    (base / "vars").mkdir()
    subprocess.run(["cp", "-R", str(ROOT / "playbooks/tasks"), str(base / "playbooks/tasks")], check=True)
    src = Path(mapping_path) if mapping_path else ROOT / "vars/bulgular-eslesme.tsv"
    if src.exists():
        (base / "vars/bulgular-eslesme.tsv").write_bytes(src.read_bytes())
    play = [{"hosts": "localhost", "connection": "local", "gather_facts": False,
             "vars": {"hardening_audit_report": report, "scan_dir": str(scan_dir)},
             "tasks": [{"ansible.builtin.include_tasks": "tasks/bulgular.yml"}]}]
    (base / "playbooks/t.yml").write_text(yaml.safe_dump(play), encoding="utf-8")
    env = {**os.environ, "ANSIBLE_CONFIG": str(ROOT / "ansible.cfg"), "ANSIBLE_FILTER_PLUGINS": str(ROOT / "filter_plugins"), "ANSIBLE_BECOME": "False"}
    r = subprocess.run(["ansible-playbook", "-i", "localhost,", str(base / "playbooks/t.yml")], capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env, cwd=base)
    return r, r.stdout + r.stderr


def table(path):
    lines = Path(path).read_text(encoding="utf-8").split("\n")
    assert lines[-1] == ""
    return [ln.split("\t") for ln in lines[:-1]]


report = FIX.read_text(encoding="utf-8")
comp = yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))
variables = {v["name"]: v for v in comp["vars"]}
areas = {"base", "auth", "fail2ban", "files", "ssh", "kernel", "apparmor", "auditd", "aide", "docker", "ufw", "sudo", "time", "report", "pve_pveproxy", "pam_faillock"}

with tempfile.TemporaryDirectory() as d:
    r, out = run(report, d)
    check("uretim: rc=0", r.returncode == 0, out)
    f = Path(d) / "bulgular.tsv"
    check("dosya 0600", f.exists() and stat.S_IMODE(f.stat().st_mode) == 0o600)
    rows = table(f)
    check("baslik tam olarak sozlesmedeki 10 sutun", rows[0] == HEADER, rows[0])
    body = rows[1:]
    check("her satir 10 sutun", all(len(x) == 10 for x in body), [x for x in body if len(x) != 10])
    check("satir sayisi = rapordaki warning[] + suggestion[] sayisi", len(body) == len(re.findall(r"(?m)^(warning|suggestion)\[\]=", report)), len(body))
    # sshpocket'in satir kurallari (onlarin dogrulamasi: gecersiz satir atlanir)
    check("tur yalniz uyari|oneri", all(x[2] in ("uyari", "oneri") for x in body))
    check("risk yalniz yuksek|orta|dusuk|bilgi|bilinmiyor", all(x[1] in ("yuksek", "orta", "dusuk", "bilgi", "bilinmiyor") for x in body))
    check("platform yalniz ubuntu|proxmox|hepsi", all(x[9] in ("ubuntu", "proxmox", "hepsi") for x in body))
    check("kapanir_varsayilan yalniz evet|hayir|bos, alan bossa bos", all(x[8] in ("evet", "hayir", "") and (x[6] != "" or x[8] == "") for x in body))
    check("deger yalniz ad=deger|bos", all(x[7] == "" or re.fullmatch(r"[a-z0-9_]+=\S+", x[7]) for x in body), [x[7] for x in body])
    check("kimlik hic bos degil", all(x[0] for x in body))
    check("Lynis '-' yer tutucusu bos yazilir (oneri/ayrinti)", not any(x[4] == "-" or x[5] == "-" for x in body))
    ssh = [x for x in body if x[0] == "SSH-7408"]
    check("SSH-7408 iki satir: MaxSessions eslenir, Port eslenmez", len(ssh) == 2 and ssh[0][6:9] == ["ssh", "hardening_ssh_max_sessions=2", "hayir"] and ssh[1][6:9] == ["", "", ""], ssh)
    check("eslemesiz bulgu (BOOT-5122) listelenir, alan bos", any(x[0] == "BOOT-5122" and x[6] == "" for x in body))
    check("kimliksiz maddeler GENEL-1, GENEL-2", [x[0] for x in body if x[0].startswith("GENEL-")] == ["GENEL-1", "GENEL-2"], [x[0] for x in body])
    check("sekmeli aciklama boslukla birlestirildi", any(x[3] == "Kimliksiz genel uyari sekmeli" for x in body))
    check("warning uyari, suggestion oneri", [x[2] for x in body if x[0] == "PKGS-7392"] == ["uyari"] and [x[2] for x in body if x[0] == "DEB-0811"] == ["oneri"])

# eslemenin dogrulugu: her satir component.yml ile capraz denetlenir
mrows = [ln.split("\t") for ln in (ROOT / "vars/bulgular-eslesme.tsv").read_text(encoding="utf-8").splitlines() if ln and not ln.startswith("#")]
check("eslesme basligi", mrows[0] == ["kimlik", "ayrinti_icerir", "risk", "alan", "deger", "kapanir_varsayilan", "platform"], mrows[0])
for kimlik, icerir, risk, alan, deger, kapanir, platform in mrows[1:]:
    ad = f"eslesme {kimlik}{'/' + icerir if icerir else ''}"
    ok = alan in areas and risk in ("yuksek", "orta", "dusuk", "bilgi", "bilinmiyor") and platform in ("ubuntu", "proxmox", "hepsi") and kapanir in ("evet", "hayir")
    if deger:
        var, _, val = deger.partition("=")
        spec = variables.get(var)
        ok = ok and spec is not None
        if spec is not None:
            same = str(spec["default"]).lower() == val.lower()
            ok = ok and (same == (kapanir == "evet"))   # evet <=> onerilen deger paketin varsayilani
    check(ad + ": alan/degisken/varsayilan component.yml ile tutarli", ok, (alan, deger, kapanir))
check("eslesmede ayni (kimlik, ayrinti_icerir) iki kez yok", len({(m[0], m[1]) for m in mrows[1:]}) == len(mrows) - 1)

# bozuk/eksik girdiler denetimi etkilemez
with tempfile.TemporaryDirectory() as d:
    r, out = run("", d)
    check("bos rapor: yalniz baslik satiri", r.returncode == 0 and table(Path(d) / "bulgular.tsv") == [HEADER], out)
with tempfile.TemporaryDirectory() as d:
    r, out = run("\x00\x01garbage\nwarning[]\nsuggestion[]=\n", d)
    check("cop girdi: Ansible dusmez", r.returncode == 0, out)
with tempfile.TemporaryDirectory() as d:
    r, out = run(report, d, mapping_path=d + "/yok.tsv")
    rows = table(Path(d) / "bulgular.tsv")
    check("eslesme dosyasi yok: yine uretilir, eslesme sutunlari bos", r.returncode == 0 and len(rows) > 1 and all(x[6] == "" and x[1] == "bilinmiyor" for x in rows[1:]), out)
with tempfile.TemporaryDirectory() as d:
    bad = Path(d) / "bad.tsv"
    bad.write_text("kimlik\trisk\talan\tdeger\tkapanir_varsayilan\tplatform\nSSH-7408\tkorkunc\tssh\tx\tbelki\tmars\n\n\tfoo\n", encoding="utf-8")
    r, out = run(report, d, mapping_path=bad)
    row = next(x for x in table(Path(d) / "bulgular.tsv")[1:] if x[0] == "SSH-7408")
    check("gecersiz eslesme degerleri varsayilana duser (risk/platform/kapanir)", r.returncode == 0 and row[1] == "bilinmiyor" and row[9] == "hepsi" and row[8] == "", row)
with tempfile.TemporaryDirectory() as d:
    bad = Path(d) / "alansiz.tsv"
    bad.write_text("kimlik\tayrinti_icerir\trisk\talan\tdeger\tkapanir_varsayilan\tplatform\nDEB-0811\t\tbilinmiyor\t\t\tevet\thepsi\n", encoding="utf-8")
    r, out = run(report, d, mapping_path=bad)
    row = next(x for x in table(Path(d) / "bulgular.tsv")[1:] if x[0] == "DEB-0811")
    check("alan bosken kapanir_varsayilan bos yazilir", r.returncode == 0 and row[6] == "" and row[8] == "", row)
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / "p.yml"
    p.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_audit_report": {"bu": "dict"}, "scan_dir": d},
                                  "tasks": [{"ansible.builtin.include_tasks": str(ROOT / "playbooks/tasks/bulgular.yml")}]}]), encoding="utf-8")
    env = {**os.environ, "ANSIBLE_CONFIG": str(ROOT / "ansible.cfg"), "ANSIBLE_FILTER_PLUGINS": str(ROOT / "filter_plugins"), "ANSIBLE_BECOME": "False"}
    r = subprocess.run(["ansible-playbook", "-i", "localhost,", str(p)], capture_output=True, text=True, stdin=subprocess.DEVNULL, env=env, cwd=d)
    check("uretim hatasi: rc=0, dosya yok, atlandi iletisi (rescue)", r.returncode == 0 and not (Path(d) / "bulgular.tsv").exists() and "bulgular.tsv üretilemedi" in r.stdout, r.stdout + r.stderr)

# audit.yml gercekten gorevi cagiriyor ve check modunda atliyor
audit = (ROOT / "playbooks/audit.yml").read_text(encoding="utf-8")
check("audit.yml bulgular gorevini cagirir, check modunda degil", re.search(r"include_tasks: tasks/bulgular.yml\n\s+when: not ansible_check_mode", audit) is not None)
cp = (ROOT / "ansible.cfg").read_text(encoding="utf-8")
check("ansible.cfg filter_plugins tanimli", "filter_plugins = ./filter_plugins" in cp)

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
