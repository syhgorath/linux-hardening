#!/usr/bin/env python3
"""Kalici kapatma (hardening_remove rolu, kaldir_onizle / kaldir / kaldir_geri_yukle): gercek Ansible, yollar gecici dizinde."""
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
        print(f"  FAIL {name} {detail[-900:]}")


defaults = yaml.safe_load((ROOT / "roles/hardening_remove/defaults/main.yml").read_text(encoding="utf-8"))
catalog = defaults["hardening_remove_catalog"]
# systemd yerelde yok: yeniden baslatma anahtari testte kaldirilir (katalogda var olmasi asagida ayrica denetlenir)
test_catalog = {k: {kk: vv for kk, vv in v.items() if kk != "restart"} for k, v in catalog.items()}


def run(root, extra, tasks_from=None, apply=False, check_mode=False):
    play = {"hosts": "localhost", "connection": "local", "gather_facts": False, "vars": {"hardening_remove_apply": apply}}
    if tasks_from:   # roles: tasks_from desteklemez
        play["tasks"] = [{"ansible.builtin.include_role": {"name": "hardening_remove", "tasks_from": tasks_from}}]
    else:
        play["roles"] = ["hardening_remove"]
    base = {"hardening_remove_root": str(root), "hardening_remove_owner": str(os.getuid()), "hardening_remove_group": str(os.getgid()), "hardening_remove_catalog": test_catalog}
    with tempfile.TemporaryDirectory() as d:
        pb = Path(d) / "p.yml"
        pb.write_text(yaml.safe_dump([play]), encoding="utf-8")
        cmd = ["ansible-playbook", "-i", str(ROOT / "test/inventory-local.yml"), str(pb), "-e", json.dumps({**base, **extra})]
        if check_mode:
            cmd.append("--check")
        r = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           env={**os.environ, "ANSIBLE_CONFIG": str(ROOT / "test/ansible-test.cfg"), "ANSIBLE_ROLES_PATH": str(ROOT / "roles")})
        return r.returncode, r.stdout + r.stderr


def put(root, rel, text):
    p = root / rel.lstrip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


OURS = {
    "unattended_upgrades": ('APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\n', "/etc/apt/apt.conf.d/20auto-upgrades"),
    "disable_network_protocols": ("# Ansible tarafından yönetilir\ninstall atm /bin/false\n", "/etc/modprobe.d/60-hardening-protocols.conf"),
    "disable_filesystem_modules": ("# Ansible tarafından yönetilir\ninstall cramfs /bin/false\n", "/etc/modprobe.d/60-hardening-filesystems.conf"),
    "sysctl_hardening": ("# Ansible tarafından yönetilir.\nkernel.sysrq = 0\n", "/etc/sysctl.d/60-hardening.conf"),
    "journald_persistent": ("# Ansible tarafından yönetilir\n[Journal]\nStorage=persistent\n", "/etc/systemd/journald.conf.d/60-hardening.conf"),
}

# ---- katalog ----
check("katalog yolu rollerin yazdigi yolla ayni", all(catalog[k]["path"] == v[1] for k, v in OURS.items()), str({k: catalog[k]["path"] for k in catalog}))
check("katalogda legal_banner YOK (ozgun /etc/issue yedegi yok)", "legal_banner" not in catalog)
check("journald icin yeniden baslatma tanimli", catalog["journald_persistent"].get("restart") == "systemd-journald")
for k, (_, path) in OURS.items():
    written = any(path in (ROOT / "roles" / r / "tasks/main.yml").read_text(encoding="utf-8") for r in ("hardening_base", "hardening_kernel"))
    check(f"{k}: yol rollerde yaziliyor", written)

# ---- satir desenleri gercek rol ciktisiyla ayni mi (rol degisip desen eskirse dosya "bizim degil" sayilirdi) ----
import itertools
import re

import jinja2

env = jinja2.Environment(undefined=jinja2.StrictUndefined)
env.filters["bool"] = bool


def lines_ok(item, text):
    pat = re.compile(catalog[item]["line_pattern"])
    return [ln for ln in (x.strip() for x in text.splitlines()) if ln and not ln.startswith("#") and not pat.match(ln)]


tmpl = (ROOT / "roles/hardening_kernel/templates/sysctl.conf.j2").read_text(encoding="utf-8")
bad = []
for relaxed, ra, extra, mods in itertools.product([False, True], repeat=4):
    out = env.from_string(tmpl).render(hardening_platform_relaxed=relaxed, hardening_kernel_disable_ipv6_ra=ra,
                                       hardening_kernel_extra_sysctl=extra, hardening_kernel_modules_disabled=mods)
    bad += lines_ok("sysctl_hardening", out)
check("sysctl deseni sablonun tum ciktilarina uyar", not bad, str(bad))
for item, rel, role in (("disable_network_protocols", "60-hardening-protocols.conf", "hardening_kernel"),
                        ("disable_filesystem_modules", "60-hardening-filesystems.conf", "hardening_kernel"),
                        ("journald_persistent", "60-hardening.conf", "hardening_base")):
    tasks = yaml.safe_load((ROOT / f"roles/{role}/tasks/main.yml").read_text(encoding="utf-8"))
    body = next(t["ansible.builtin.copy"]["content"] for t in tasks
                if isinstance(t.get("ansible.builtin.copy"), dict) and t["ansible.builtin.copy"].get("dest", "").endswith(rel)
                and catalog[item]["path"] == t["ansible.builtin.copy"]["dest"])
    rendered = env.from_string(body, ).render()
    check(f"{item}: deseni rolun yazdigi icerige uyar", not lines_ok(item, rendered) and catalog[item]["marker"] in rendered, rendered)

with tempfile.TemporaryDirectory() as d:
    root = Path(d)
    # ---- dogrulama ----
    rc, out = run(root, {"hardening_remove_items": []})
    check("bos secim reddedilir", rc != 0 and "boş ya da geçersiz" in out, out)
    rc, out = run(root, {"hardening_remove_items": ["legal_banner"]})
    check("katalog disi ad reddedilir", rc != 0 and "geçersiz" in out, out)
    rc, out = run(root, {"hardening_remove_items": "sysctl_hardening"})
    check("liste olmayan secim reddedilir", rc != 0, out)

    # ---- onizleme: yazmaz, silmez ----
    for k, (text, path) in OURS.items():
        put(root, path, text)
    put(root, "/etc/sysctl.d/60-hardening.conf", "baska bir yonetici yazdi\n")   # bizim degil
    sel = list(OURS)
    before = {p: Path(root / p.lstrip("/")).read_text() for _, (_, p) in OURS.items()}
    rc, out = run(root, {"hardening_remove_items": sel})
    check("onizleme: SSHPOCKET_RESULT silinecek=4 atlanan=1", rc == 0 and "SSHPOCKET_RESULT linux-hardening.kaldir_onizle silinecek=4 atlanan=1" in out, out)
    check("onizleme: SİLİNECEK satirlari yol ile", "SİLİNECEK: /etc/modprobe.d/60-hardening-protocols.conf" in out and "SİLİNECEK: /etc/apt/apt.conf.d/20auto-upgrades" in out, out)
    check("onizleme: bizim olmayan dosya ATLANDI", "ATLANDI (içerik bu paketin yazdığı gibi değil): /etc/sysctl.d/60-hardening.conf" in out, out)
    check("onizleme: hicbir dosya degismedi, yedek yok", all(Path(root / p.lstrip("/")).read_text() == t for p, t in before.items()) and not (root / "var/backups").exists())
    check("onizleme: canli durum uyarisi", "çalışan sistemi geri almaz" in out, out)

    # ---- isaret satiri duruyor ama elle satir eklenmis: dosya bizim sayilmaz, atlanir ----
    put(root, "/etc/sysctl.d/60-hardening.conf", "# Ansible tarafından yönetilir.\nkernel.sysrq = 0\nvm.swappiness = 1\n")
    put(root, "/etc/apt/apt.conf.d/20auto-upgrades", 'APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";\nAPT::Periodic::Download-Upgradeable-Packages "1";\n')
    rc, out = run(root, {"hardening_remove_items": sel})
    check("onizleme: isaret var ama elle satir eklenmis -> ATLANDI (silinecek=3 atlanan=2)",
          rc == 0 and "silinecek=3 atlanan=2" in out and "ATLANDI (içerik bu paketin yazdığı gibi değil): /etc/sysctl.d/60-hardening.conf" in out
          and "ATLANDI (içerik bu paketin yazdığı gibi değil): /etc/apt/apt.conf.d/20auto-upgrades" in out, out)
    put(root, "/etc/apt/apt.conf.d/20auto-upgrades", OURS["unattended_upgrades"][0])
    put(root, "/etc/sysctl.d/60-hardening.conf", "baska bir yonetici yazdi\n")
    before = {p: Path(root / p.lstrip("/")).read_text() for _, (_, p) in OURS.items()}

    # ---- check modunda apply bile yazmaz ----
    rc, out = run(root, {"hardening_remove_items": sel}, apply=True, check_mode=True)
    check("--check: apply true olsa bile silmez", rc == 0 and all((root / p.lstrip("/")).exists() for _, (_, p) in OURS.items()) and not (root / "var/backups").exists(), out)

    # ---- uygulama ----
    rc, out = run(root, {"hardening_remove_items": sel}, apply=True)
    gone = [k for k, (_, p) in OURS.items() if not (root / p.lstrip("/")).exists()]
    check("kaldir: 4 dosya silindi, bizim olmayan DURUYOR", rc == 0 and sorted(gone) == sorted(k for k in OURS if k != "sysctl_hardening") and (root / "etc/sysctl.d/60-hardening.conf").exists(), out)
    check("kaldir: SSHPOCKET_RESULT silinen=4 atlanan=1", "SSHPOCKET_RESULT linux-hardening.kaldir silinen=4 atlanan=1" in out, out)
    bdirs = sorted((root / "var/backups/linux-hardening").glob("kaldir-*"))
    check("kaldir: tek yedek klasoru, 0700", len(bdirs) == 1 and oct(bdirs[0].stat().st_mode & 0o777) == "0o700" and oct(bdirs[0].parent.stat().st_mode & 0o777) == "0o700", str(bdirs))
    if bdirs:
        b = bdirs[0]
        check("kaldir: yedek dosyalari 0600 ve icerik ayni", all((b / f"{k}.bak").read_text() == OURS[k][0] and oct((b / f"{k}.bak").stat().st_mode & 0o777) == "0o600" for k in gone))
        check("kaldir: manifest 4 satir, yol ile", len((b / "manifest.txt").read_text().splitlines()) == 4 and "unattended_upgrades\t/etc/apt/apt.conf.d/20auto-upgrades" in (b / "manifest.txt").read_text())
        check("kaldir: bizim olmayan dosya yedeklenmedi", not (b / "sysctl_hardening.bak").exists())
    rc, out = run(root, {"hardening_remove_items": sel}, apply=True)
    check("2. kaldir: silinecek=0 (idempotent), yeni yedek klasoru yok", rc == 0 and "kaldir silinen=0 atlanan=1" in out and len(list((root / "var/backups/linux-hardening").glob("kaldir-*"))) == 1, out)

    # ---- geri yukleme ----
    rc, out = run(root, {}, tasks_from="restore")
    back = all((root / p.lstrip("/")).exists() and (root / p.lstrip("/")).read_text() == t for k, (t, p) in OURS.items() if k != "sysctl_hardening")
    check("geri yukle: 4 dosya ozgun icerikle geri geldi", rc == 0 and back and "geri_yuklenen=4" in out, out)
    check("geri yukle: bizim olmayan dosyaya dokunmadi", (root / "etc/sysctl.d/60-hardening.conf").read_text() == "baska bir yonetici yazdi\n")
    rc, out = run(root, {"hardening_remove_restore_from": "../../etc"}, tasks_from="restore")
    check("geri yukle: yol gezdirme reddedilir", rc != 0 and "geçersiz" in out, out)
    rc, out = run(root, {"hardening_remove_restore_from": "kaldir-20200101T000000Z"}, tasks_from="restore")
    check("geri yukle: olmayan yedek hata verir", rc != 0, out)

    # ---- manifest'e sokulan yabanci yol geri yuklenmez ----
    b = sorted((root / "var/backups/linux-hardening").glob("kaldir-*"))[0]
    (b / "manifest.txt").write_text("sysctl_hardening\t/etc/passwd\nunattended_upgrades\t/etc/apt/apt.conf.d/20auto-upgrades\n")
    (root / "etc/passwd").parent.mkdir(parents=True, exist_ok=True)
    (root / "etc/passwd").write_text("dokunma\n")
    (b / "sysctl_hardening.bak").write_text("kotu\n")
    rc, out = run(root, {}, tasks_from="restore")
    check("geri yukle: katalog disi yol (/etc/passwd) yok sayilir", rc == 0 and (root / "etc/passwd").read_text() == "dokunma\n" and "geri_yuklenen=1" in out, out)

# ---- playbook'lar ----
pb_apply = (ROOT / "playbooks/kaldir.yml").read_text(encoding="utf-8")
pb_prev = (ROOT / "playbooks/kaldir-onizle.yml").read_text(encoding="utf-8")
check("silme kapisi yalniz kaldir.yml'de play degiskeni", "hardening_remove_apply: true" in pb_apply and "hardening_remove_apply" not in pb_prev)
check("harden.yml kaldir rolunu CALISTIRMAZ", "hardening_remove" not in (ROOT / "playbooks/harden.yml").read_text(encoding="utf-8").replace("hardening_remove_legacy_clients", ""))
comp = yaml.safe_load((ROOT / "component.yml").read_text(encoding="utf-8"))["actions"]
tasks = (ROOT / "roles/hardening_remove/tasks/main.yml").read_text(encoding="utf-8") + (ROOT / "roles/hardening_remove/tasks/restore.yml").read_text(encoding="utf-8")
for act, keys in (("kaldir_onizle", ["silinecek", "atlanan"]), ("kaldir", ["silinen", "atlanan"]), ("kaldir_geri_yukle", ["geri_yuklenen"])):
    o = comp[act]["outputs"]
    line = [ln for ln in tasks.splitlines() if o["prefix"] + " " in ln]
    check(f"{act}: outputs.keys sonuc satiriyla ayni", o["keys"] == keys and len(line) == 1 and all(f" {k}=" in line[0] for k in keys), str(line))
check("kaldir requires kaldir_onizle, type-server-name", comp["kaldir"]["requires"] == ["kaldir_onizle"] and comp["kaldir"]["confirm"] == "type-server-name" and comp["kaldir_geri_yukle"]["confirm"] == "type-server-name")
check("kaldir silen eylem: effects changes-config + destructive, geri yukleme ve onizlemede destructive YOK", {"changes-config", "destructive"} <= set(comp["kaldir"]["effects"]) and "destructive" not in comp["kaldir_geri_yukle"]["effects"] and "destructive" not in comp["kaldir_onizle"]["effects"])
check("kaldir_onizle salt okunur (effects bos, confirm none)", comp["kaldir_onizle"]["effects"] == [] and comp["kaldir_onizle"]["confirm"] == "none")
sys.exit(1 if fails else 0)
