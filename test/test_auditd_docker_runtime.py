#!/usr/bin/env python3
"""hardening_auditd: /run altındaki (tmpfs) Docker yolları izlenmez (gerçek VM bulgusu V0121-S3-BULGU1).

Neden: reboot'ta /run/containerd/containerd.sock servis başlayana kadar yoktur, audit-rules.service ise kuralları ondan önce yükler;
var olmayan yola kural `auditctl -R`'yi o satırda durdurur (sonraki kurallar yüklenmez, birim başarısız olur).
Denetlenenler: varsayılan listede /run, /var/run yolu yok; set_fact süzgeci listeye elle yazılan /run yollarını da atlar.
"""
import sys
from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parent.parent
defaults = yaml.safe_load((ROOT / "roles/hardening_auditd/defaults/main.yml").read_text(encoding="utf-8"))
tasks = yaml.safe_load((ROOT / "roles/hardening_auditd/tasks/main.yml").read_text(encoding="utf-8"))
fails = 0


def check(name, ok, detail=""):
    global fails
    if ok:
        print(f"  ok   {name}")
    else:
        fails += 1
        print(f"  FAIL {name} {detail}")


paths = defaults["hardening_auditd_docker_paths"]
check("varsayılan listede /run ya da /var/run yolu yok", not [p for p in paths if p.startswith(("/run/", "/var/run/"))], str(paths))
check("kalıcı yollar duruyor (dockerd, docker.socket birimi)", "/usr/bin/dockerd" in paths and "/usr/lib/systemd/system/docker.socket" in paths)

task = next(t for t in tasks if t.get("name") == "Remember the Docker paths that exist")
expr = task["ansible.builtin.set_fact"]["hardening_auditd_docker_existing"]
env = jinja2.Environment()
env.tests["match"] = lambda v, pat: __import__("re").match(pat, v) is not None
env.filters["reject"] = lambda seq, test, *a: [x for x in seq if not env.tests[test](x, *a)]
env.filters["selectattr"] = lambda seq, attr, *a: [x for x in seq if x["stat"]["exists"]]
env.filters["map"] = lambda seq, attribute: [x[attribute] for x in seq]
results = [{"item": p, "stat": {"exists": True}} for p in ["/usr/bin/dockerd", "/run/docker.sock", "/var/run/docker.sock", "/run/containerd/containerd.sock", "/etc/docker"]]
results.append({"item": "/etc/default/docker", "stat": {"exists": False}})
out = env.from_string(expr).render(hardening_auditd_docker_stat={"results": results})
check("süzgeç /run, /var/run ve var olmayan yolları eler", out == "['/usr/bin/dockerd', '/etc/docker']", out)

sys.exit(1 if fails else 0)
