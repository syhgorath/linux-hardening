#!/usr/bin/env python3
"""hardening_auditd: denetim kuralları, auditd BAŞLADIKTAN HEMEN SONRA yüklenmeli (play sonunda değil).

Neden: `augenrules --load` bir handler olduğunda play bitene kadar çalışmıyor; test VM'inde auditd başlangıcı ile ilk kural yükleme kaydı
arasında 652 sn vardı (docs/design/auditd-kapsam.md P3). Bu sürede sonraki roller (fail2ban, aide, ufw, ssh) izlenmiyordu.

Denetlenenler (statik, tasks/main.yml): handler ile yükleme yok, yükleme görevi şablondan VE servis başlatmadan sonra geliyor, `--check`'te atlanıyor,
`meta: flush_handlers` kullanılmıyor (önceki rollerin bekleyen handler'larını da öne çekerdi).
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
tasks = yaml.safe_load((ROOT / "roles/hardening_auditd/tasks/main.yml").read_text(encoding="utf-8"))
fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail}")


def module_of(t):
    for k in t:
        if k.startswith("ansible.builtin.") or k == "meta":
            return k
    return None


def idx(pred):
    return next((i for i, t in enumerate(tasks) if pred(t)), None)


template_i = idx(lambda t: module_of(t) == "ansible.builtin.template" and "hardening.rules" in str(t.get("ansible.builtin.template", {}).get("src", "")))
start_i = idx(lambda t: module_of(t) == "ansible.builtin.systemd" and t["ansible.builtin.systemd"].get("name") == "auditd" and t["ansible.builtin.systemd"].get("state") == "started")
load_i = idx(lambda t: module_of(t) == "ansible.builtin.command" and "augenrules --load" in str(t["ansible.builtin.command"]))

check("kural şablonu görevi var", template_i is not None)
check("auditd başlatma görevi var", start_i is not None)
check("augenrules --load GÖREV olarak var (handler değil)", load_i is not None)

notified = [t.get("notify") for t in tasks if t.get("notify")]
check("hiçbir görev kural yüklemeyi handler'a bırakmıyor (notify yok)", not notified, f"notify={notified}")
check("meta: flush_handlers kullanılmıyor", all(not (module_of(t) == "meta" and "flush_handlers" in str(t)) for t in tasks))

if None not in (template_i, start_i, load_i):
    check("yükleme, şablon yazıldıktan sonra", load_i > template_i)
    check("yükleme, auditd başlatıldıktan sonra", load_i > start_i)
    load = tasks[load_i]
    when = str(load.get("when"))
    check("`--check` modunda atlanıyor", "ansible_check_mode" in when, f"when={when}")
    check("şablon değiştiyse yüklüyor", "changed" in when, f"when={when}")
    check("kural yoksa ('No rules') yeniden yüklüyor", "No rules" in when, f"when={when}")
    read_i = idx(lambda t: module_of(t) == "ansible.builtin.command" and "auditctl -l" in str(t["ansible.builtin.command"]))
    check("mevcut kurallar okunuyor (auditctl -l), yüklemeden önce", read_i is not None and read_i < load_i)
    if read_i is not None:
        r = tasks[read_i]
        check("okuma görevi değişiklik sayılmıyor ve --check'te de güvenli", r.get("changed_when") is False)

sys.exit(1 if fails else 0)
