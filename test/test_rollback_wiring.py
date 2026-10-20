#!/usr/bin/env python3
"""Geri alma güvenlik ağının playbook/rol bağlantısı (yapısal): arm sırası, disarm başarıda, restore rescue'da.

Arm eden ama disarm etmeyen bir sürüm N sn sonra sertleştirmeyi geri alırdı; bu test o hatayı yakalar.
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
fails = 0


def check(name, cond, detail=""):
    global fails
    if cond:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail}")


# ---- harden.yml: rol sirasi ----
pb = yaml.safe_load((ROOT / "playbooks/harden.yml").read_text(encoding="utf-8"))
roles = [r["role"] if isinstance(r, dict) else r for r in pb[0]["roles"]]
tags_of = {(r["role"] if isinstance(r, dict) else r): (r.get("tags", []) if isinstance(r, dict) else []) for r in pb[0]["roles"]}
check("hardening_rollback harden.yml'de var", "hardening_rollback" in roles)
if "hardening_rollback" in roles:
    i = roles.index("hardening_rollback")
    check("arm, aide'den SONRA", i > roles.index("hardening_aide"))
    check("arm, ufw'den ONCE", i < roles.index("hardening_ufw"))
    check("arm, ssh'tan ONCE", i < roles.index("hardening_ssh"))
    check("arm etiketleri ufw ve ssh icerir", {"ufw", "ssh"} <= set(tags_of["hardening_rollback"]),
          str(tags_of["hardening_rollback"]))
check("verify_access post_tasks'ta", any("hardening_verify_access" in str(t) for t in pb[0].get("post_tasks", [])))

# ---- PAM (faillock) ayni arm penceresinin ICINDE: arm'dan SONRA, ufw'den ONCE; ayni etiketle arm ve disarm ----
check("arm etiketleri 'pam' icerir (--tags pam yalniz faillock'u calistirinca da arm edilir)", "pam" in tags_of.get("hardening_rollback", []))
check("hardening_pam_faillock harden.yml'de var, etiketi pam", "hardening_pam_faillock" in roles and tags_of.get("hardening_pam_faillock") == ["pam"])
if "hardening_pam_faillock" in roles and "hardening_rollback" in roles:
    check("faillock, arm'dan SONRA (arm penceresinin icinde)", roles.index("hardening_pam_faillock") > roles.index("hardening_rollback"))
    check("faillock, ufw'den ONCE", roles.index("hardening_pam_faillock") < roles.index("hardening_ufw"))
    check("faillock, aide'den SONRA (AIDE ilk veritabani dakikalar surer, zamanlayici erken tetiklenmesin)", roles.index("hardening_pam_faillock") > roles.index("hardening_aide"))
va = next((t for t in pb[0].get("post_tasks", []) if "hardening_verify_access" in str(t)), {})
check("verify_access (disarm) 'pam' etiketiyle de calisir (yoksa --tags pam armed birakir ve sure dolunca HER SEYI geri alir)",
      "pam" in (va.get("tags") or []) and "pam" in str((va.get("ansible.builtin.include_role") or {}).get("apply", {})))


# ---- verify rolu ----
def walk(tasks):
    for t in tasks or []:
        if isinstance(t, dict):
            yield t
            for k in ("block", "rescue", "always"):
                yield from walk(t.get(k))


def role_ref(t):
    ir = t.get("ansible.builtin.include_role")
    return (ir.get("name"), ir.get("tasks_from")) if isinstance(ir, dict) else None


v = yaml.safe_load((ROOT / "roles/hardening_verify_access/tasks/main.yml").read_text(encoding="utf-8"))
top = v[0]
block = top.get("block", [])
rescue = top.get("rescue", [])
block_refs = [role_ref(t) for t in walk(block)]
rescue_refs = [role_ref(t) for t in walk(rescue)]
check("blok icinde DISARM var", ("hardening_rollback", "disarm") in block_refs, str(block_refs))
names = [str(t.get("name", "")) for t in block]
disarm_idx = next((i for i, t in enumerate(block) if role_ref(t) == ("hardening_rollback", "disarm")), -1)
conn_idx = max((i for i, n in enumerate(names) if n.startswith(("Open a NEW SSH", "Verify a NEW TCP"))), default=-1)
check("disarm, baglanti testlerinden SONRA", disarm_idx > conn_idx >= 0, f"disarm={disarm_idx} conn={conn_idx}")
check("rescue'da RESTORE var", ("hardening_rollback", "restore") in rescue_refs, str(rescue_refs))
check("rescue'da yedek betik kontrolu (stat)", any("ansible.builtin.stat" in t for t in rescue))
check("rescue SON gorevi fail (durur)",
      any("ansible.builtin.fail" in t for t in rescue[-2:]))
check("rescue'da DISARM YOK (basarisizlikta disarm edilmez, restore kendini disarm eder)",
      ("hardening_rollback", "disarm") not in rescue_refs)

# ---- rol dosyalari ----
for f in ("main.yml", "disarm.yml", "restore.yml"):
    check(f"hardening_rollback/tasks/{f} var", (ROOT / "roles/hardening_rollback/tasks" / f).exists())
main_text = (ROOT / "roles/hardening_rollback/tasks/main.yml").read_text(encoding="utf-8")
check("arm --check'te atlanir", "not ansible_check_mode" in main_text)
check("systemd yoksa durur (assert)", "systemctl --version" in main_text and "ansible.builtin.assert" in main_text)
disarm_text = (ROOT / "roles/hardening_rollback/tasks/disarm.yml").read_text(encoding="utf-8")
check("disarm betik yoksa atlanir (stat)", "ansible.builtin.stat" in disarm_text)

print("TAMAM" if fails == 0 else f"BASARISIZ: {fails}")
sys.exit(1 if fails else 0)
