# linux-hardening

Ansible ile Linux sunucu sertleştirme (hardening). Rolleri tek repoda tutar; her dağıtım/sürüm için
destek açıkça listelenir, desteklenmeyen sistemde çalışmayı durdurur.

**Şu an desteklenen:** Ubuntu 26.04 LTS (hedef: CIS Level 1 Server yaklaşımı).
Başka sürüm/dağıtım ekleme yolu açık: bkz. [docs/SUPPORT.md](docs/SUPPORT.md).

## Akış
1. `playbooks/audit.yml` — baseline tarama (Lynis)
2. `playbooks/harden.yml --check --diff` — ne değişecek, önce gör
3. `playbooks/harden.yml` — uygula (önce snapshot/yedek al)
4. `playbooks/audit.yml` — tekrar tara, öncesi/sonrası karşılaştır

## Başlangıç
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp inventory/hosts.example.yml inventory/hosts.yml   # kendi makinelerini yaz
source .venv/bin/activate
ansible-playbook playbooks/audit.yml
```

Ayrıntılı kullanım, sudo/üretim notları ve sorun giderme: **[HOWTO.md](HOWTO.md)**.
Alınan kararlar ve istisnalar: [docs/decisions.md](docs/decisions.md).

> Sunucunun ağ ayarını (`hardening_ssh_allow_from`) doğru vermezseniz firewall sizi dışarıda bırakır.
> Önce test sunucusunda deneyin, snapshot alın, `--check --diff` ile bakın.

## Lisans

MIT, bkz. [LICENSE](LICENSE). Kullanım sorumluluğu size aittir: sertleştirme erişimi kesebilir; önce test sunucusunda deneyin.
