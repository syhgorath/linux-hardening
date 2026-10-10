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

## Inventory grubu
Sunucuları inventory'de **`hardening`** grubuna yazın (dışarıdan üretilen inventory'ler de bunu kullanabilir).
Eski **`ubuntu`** grubu geçiş için hâlâ kabul edilir. Desteklenen sistem/sürüm kontrolü grup adıyla değil,
`hardening_preflight` ile yapılır.

> **2FA uyarısı:** `hardening_ssh_kbdinteractive: true` yazmak yalnızca bir anahtarı çevirir. Sunucuda PAM'ın
> 2FA'yı (örn. `libpam-google-authenticator`) ayrıca yapılandırılması gerekir; yanlışsa erişim kesilir. Açıkken
> sshd `AuthenticationMethods publickey,keyboard-interactive` ile (anahtar VE PAM istemi) çalışır; böylece
> `PasswordAuthentication no` iken PAM üzerinden **tek başına parola girişi** açılmaz. Bu durumda bağlantı doğrulaması
> yalnızca SSH banner'ını sınar (2FA istemi otomatik cevaplanamaz). Önce test sunucusunda deneyin.

## Başlangıç
```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp inventory/hosts.example.yml inventory/hosts.yml   # kendi makinelerini yaz
source .venv/bin/activate
ansible-playbook playbooks/audit.yml
```

Ayrıntılı kullanım, sudo/üretim notları ve sorun giderme: **[HOWTO.md](HOWTO.md)**.
Alınan kararlar ve istisnalar: [docs/decisions.md](docs/decisions.md).

> **`hardening_ssh_allow_from` zorunludur** (varsayılanı bilerek boş). Boşsa, geçersizse ya da Ansible'ın bağlandığı
> kaynak IP bu ağlarda değilse `harden.yml` firewall/SSH'a dokunmadan durur. Ayrıca root olarak bağlanılamaz.
> Örn: `-e '{"hardening_ssh_allow_from": ["192.168.1.0/24"]}'`
> Önce test sunucusunda deneyin, snapshot alın, `--check --diff` ile bakın.

## Lisans

MIT, bkz. [LICENSE](LICENSE). Kullanım sorumluluğu size aittir: sertleştirme erişimi kesebilir; önce test sunucusunda deneyin.
