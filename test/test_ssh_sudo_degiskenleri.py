#!/usr/bin/env python3
"""Eskiden sabit olan sshd (MaxAuthTries, LoginGraceTime, LogLevel, MaxStartups, ClientAlive*, X11/Agent forwarding) ve sudo (use_pty, timestamp_timeout) degerleri artik degisken.
Varsayilanlar ESKI sabitlerle ayni olmali (davranis degismez); gecersiz degerler yazilmadan reddedilir. Gercek Ansible ile."""
import os
import subprocess
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
        print(f"  FAIL {name} {detail[-500:]}")


def load(p):
    return yaml.safe_load((ROOT / p).read_text(encoding="utf-8"))


sd, ud = load("roles/hardening_ssh/defaults/main.yml"), load("roles/hardening_sudo/defaults/main.yml")
OLD = {"hardening_ssh_max_auth_tries": 3, "hardening_ssh_login_grace_time": 60, "hardening_ssh_log_level": "VERBOSE", "hardening_ssh_max_startups": "10:30:60",
       "hardening_ssh_client_alive_interval": 300, "hardening_ssh_client_alive_count_max": 2, "hardening_ssh_x11_forwarding": False, "hardening_ssh_agent_forwarding": False}
check("sshd varsayilanlari ESKI sabitlerle ayni", all(sd[k] == v and type(sd[k]) is type(v) for k, v in OLD.items()), str({k: sd.get(k) for k in OLD}))
check("sudo varsayilanlari ESKI sabitlerle ayni (use_pty, timestamp_timeout=15)", ud["hardening_sudo_use_pty"] is True and ud["hardening_sudo_timestamp_timeout"] == 15)


def play(tasks, vars_):
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([{"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": vars_, "tasks": tasks}]), encoding="utf-8")
        r = subprocess.run(["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb)], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg")})
    return r.returncode, r.stdout + r.stderr


# --- dogrulama gorevleri (rollerin gercek assert gorevleri) ---
ssh_assert = next(t for t in load("roles/hardening_ssh/tasks/main.yml") if t.get("name") == "Validate the sshd tuning values")
sudo_block = next(t for t in load("roles/hardening_sudo/tasks/main.yml") if t.get("name") == "Sudo settings (CIS)")["block"]
sudo_assert = next(t for t in sudo_block if t.get("name") == "Validate the sudo tuning values")
SSH_OK = {**sd}
for ad, extra, ok in (
    ("varsayilanlar", {}, True),
    ("MaxAuthTries 1 ve 10 gecerli", {"hardening_ssh_max_auth_tries": 10}, True), ("MaxAuthTries 0 reddedilir", {"hardening_ssh_max_auth_tries": 0}, False),
    ("MaxAuthTries 11 reddedilir", {"hardening_ssh_max_auth_tries": 11}, False), ("MaxAuthTries metin reddedilir", {"hardening_ssh_max_auth_tries": "uc"}, False),
    ("LoginGraceTime 0 (sinirsiz) reddedilir", {"hardening_ssh_login_grace_time": 0}, False), ("LoginGraceTime 601 reddedilir", {"hardening_ssh_login_grace_time": 601}, False),
    ("LogLevel INFO gecerli", {"hardening_ssh_log_level": "INFO"}, True), ("LogLevel DEBUG3 reddedilir (hassas bilgi)", {"hardening_ssh_log_level": "DEBUG3"}, False),
    ("LogLevel kucuk harf reddedilir", {"hardening_ssh_log_level": "verbose"}, False),
    ("MaxStartups '20' gecerli", {"hardening_ssh_max_startups": "20"}, True), ("MaxStartups '5:50:30' gecerli", {"hardening_ssh_max_startups": "5:50:30"}, True),
    ("MaxStartups '10:30' reddedilir", {"hardening_ssh_max_startups": "10:30"}, False), ("MaxStartups 'cok' reddedilir", {"hardening_ssh_max_startups": "cok"}, False),
    ("ClientAliveInterval 0 gecerli (kapali)", {"hardening_ssh_client_alive_interval": 0}, True), ("ClientAliveInterval -1 reddedilir", {"hardening_ssh_client_alive_interval": -1}, False),
    ("ClientAliveInterval 3601 reddedilir", {"hardening_ssh_client_alive_interval": 3601}, False), ("ClientAliveCountMax 11 reddedilir", {"hardening_ssh_client_alive_count_max": 11}, False),
    ("X11Forwarding metin ('yes') reddedilir", {"hardening_ssh_x11_forwarding": "yes"}, False), ("AgentForwarding true gecerli", {"hardening_ssh_agent_forwarding": True}, True),
):
    rc, out = play([ssh_assert], {**SSH_OK, **extra})
    check(f"sshd dogrulama: {ad}", (rc == 0) == ok, out)
for ad, extra, ok in (
    ("sudo varsayilanlar", {}, True), ("timestamp_timeout 0 gecerli", {"hardening_sudo_timestamp_timeout": 0}, True),
    ("timestamp_timeout -1 (suresiz) reddedilir", {"hardening_sudo_timestamp_timeout": -1}, False), ("timestamp_timeout 121 reddedilir", {"hardening_sudo_timestamp_timeout": 121}, False),
    ("timestamp_timeout metin reddedilir", {"hardening_sudo_timestamp_timeout": "on"}, False), ("use_pty metin reddedilir", {"hardening_sudo_use_pty": "yes"}, False),
):
    rc, out = play([sudo_assert], {**ud, **extra})
    check(f"sudo dogrulama: {ad}", (rc == 0) == ok, out)

# --- sudoers icerigi (gercek gorevin content'i render edilir) ---
write = next(t for t in sudo_block if t.get("name", "").startswith("Write sudoers drop-in"))
content = write["ansible.builtin.copy"]["content"]


with tempfile.TemporaryDirectory() as d:
    def render(extra, rs=False):
        dst = Path(d) / "s"
        if dst.exists():
            dst.unlink()
        rc, out = play([{"ansible.builtin.copy": {"dest": str(dst), "content": content}}], {**ud, "hardening_sudo_is_rs": rs, **extra})
        return dst.read_text() if dst.exists() else out
    base = render({})
    check("sudoers varsayilan: use_pty ve timestamp_timeout=15 (ESKI cikti)", "Defaults use_pty\n" in base and "Defaults timestamp_timeout=15\n" in base and 'logfile="/var/log/sudo.log"' in base, base)
    check("   sudoers varsayilan cikti ESKISIYLE bayt bayt ayni", base == '# Ansible tarafından yönetilir\nDefaults use_pty\nDefaults logfile="/var/log/sudo.log"\nDefaults timestamp_timeout=15\n', repr(base))
    check("   sudo-rs: logfile yok", "logfile" not in render({}, rs=True))
    t = render({"hardening_sudo_use_pty": False, "hardening_sudo_timestamp_timeout": 5})
    check("use_pty=false: satir yazilmaz; timestamp_timeout=5", "use_pty" not in t and "Defaults timestamp_timeout=5\n" in t, t)

# --- sablon baglantisi: her degisken sablonda kullaniliyor ---
tpl = (ROOT / "roles/hardening_ssh/templates/sshd-hardening.conf.j2").read_text(encoding="utf-8")
for k in OLD:
    check(f"sshd sablonu {k} kullanir (sabit kalmadi)", k in tpl)
for lit in ("MaxAuthTries 3", "LoginGraceTime 60", "LogLevel VERBOSE", "MaxStartups 10:30:60", "ClientAliveInterval 300", "ClientAliveCountMax 2", "X11Forwarding no", "AllowAgentForwarding no"):
    check(f"sshd sablonunda sabit '{lit}' kalmadi", lit not in tpl)

# --- component.yml ---
cv = {v["name"]: v for v in load("component.yml")["vars"]}
for k in list(OLD) + ["hardening_sudo_use_pty", "hardening_sudo_timestamp_timeout"]:
    d = cv[k]["default"]
    check(f"component.yml {k}: varsayilan koddakiyle ayni", d == {**OLD, **ud}[k] and type(d) is type({**OLD, **ud}[k]))
check("x11/agent forwarding: true warn_if; sudo use_pty false warn_if", cv["hardening_ssh_x11_forwarding"]["warn_if"] is True and cv["hardening_ssh_agent_forwarding"]["warn_if"] is True and cv["hardening_sudo_use_pty"]["warn_if"] is False)

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
raise SystemExit(1 if fails else 0)
