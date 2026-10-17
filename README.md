# linux-hardening

🇹🇷 Türkçe · 🇬🇧 [English](README.en.md)

Ansible ile Linux sunucu sertleştirme (hardening). Rolleri tek repoda tutar; her dağıtım/sürüm için
destek açıkça listelenir, desteklenmeyen sistemde çalışmayı durdurur.

**Şu an desteklenen:** Ubuntu 26.04 LTS (hedef: CIS Level 1 Server yaklaşımı).
Başka sürüm/dağıtım ekleme yolu açık: bkz. [docs/SUPPORT.md](docs/SUPPORT.md).

> **Durum (0.x):** Ubuntu 26.04.1 LTS test VM'inde **canlı doğrulandı**: temiz sunucuda ilk kurulum, ikinci
> koşuda `changed=0`, `--check` (`failed=0`), erişim kaybı korumaları ve geri alma güvenlik ağı (doğrulama
> başarısızlığı, kontrol makinesinin ölmesi, sunucunun yeniden başlaması). Lynis hardening index 77, uyarı 0.
> **Doğrulanmayanlar:** tek bir VM/yapılandırma dışı sunucular, gerçek ağ düzeyi kesinti, Raspberry Pi/Proxmox,
> tam CIS Benchmark uyumu (bilerek "yaklaşım"). Önce test sunucusunda deneyin, snapshot alın.

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
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.txt   # hash'li, Python >= 3.12
cp inventory/hosts.example.yml inventory/hosts.yml   # kendi makinelerini yaz
source .venv/bin/activate
ansible-playbook playbooks/audit.yml
```

Ayrıntılı kullanım, sudo/üretim notları ve sorun giderme: **[HOWTO.md](HOWTO.md)**.
Alınan kararlar ve istisnalar: [docs/decisions.md](docs/decisions.md).
Canlı doğrulama kayıtları: [docs/verification-log.md](docs/verification-log.md). Yol haritası: [docs/ROADMAP.md](docs/ROADMAP.md).

> **`hardening_ssh_allow_from` zorunludur** (varsayılanı bilerek boş). Boşsa, geçersizse ya da Ansible'ın bağlandığı
> kaynak IP bu ağlarda değilse `harden.yml` firewall/SSH'a dokunmadan durur. Ayrıca root olarak bağlanılamaz.
> Örn: `-e '{"hardening_ssh_allow_from": ["192.168.1.0/24"]}'`
> Önce test sunucusunda deneyin, snapshot alın, `--check --diff` ile bakın.

## Testler
`test/` altındaki testler her PR'da CI'da (`.github/workflows/ci.yml`) çalışır; yerelde:

```bash
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.txt
PATH="$PWD/.venv/bin:$PATH" test/run-all.sh          # hepsi
PATH="$PWD/.venv/bin:$PATH" test/run-all.sh summary  # adı "summary" içerenler
```

| Test | Neyi korur |
|---|---|
| `test_lint.sh` | `--syntax-check`, `yamllint --strict`, `ansible-lint` (0 bulgu), shellcheck |
| `test_access_guards.sh` | `allow_from` boş/geçersiz/kaynak dışı, `SSH_CONNECTION` yok, root, IPv4/IPv6 |
| `test_expressions.py` | sshd portlarının `ss` çıktısından türetilmesi, efektif fail2ban `ignoreip` |
| `test_templates.py` | Şablonların varsayılan çıktısı (golden dosyalar) ve güvenli varsayılanlar |
| `test_summary.py` | `summary.json` alanları, `null` davranışı, dizin/dosya izinleri |
| `test_tags_and_hosts.sh` | `--tags` ile preflight/korumaların atlanmaması, `hardening`/`ubuntu` grubu seçimi ve olmayan grup için uyarı çıkmaması |
| `test_facts_namespace.sh` | Fact'ler yalnızca `ansible_facts[...]` ile okunur (`INJECT_FACTS_AS_VARS=False` altında OS denetimi), üst düzey fact adı yasağı |
| `test_handlers.py` | Her `notify` bir handler'a bağlı |
| `test_vars_defined.py` | `group_vars` olmadan değişkenler tanımlı, güvenli varsayılanlar |
| `test_consistency.sh` | `VERSION`/`component.yml`/destek matrisi tutarlılığı (kasıtlı bozmalar yakalanır) |
| `test_rollback_script.sh` | geri alma betiği: arm/disarm/restore (önceki içeriği geri yükler, silmez), sahte komutlarla |
| `test_release_script.sh` | `scripts/release.sh`: gerçek imzalama/doğrulama, reddedilme senaryoları |
| `test_repo_hygiene.sh`, `test_ip_addresses.py` | Anahtar/token/IP sızıntısı, paket içeriği |

CI ayrıca Python 3.12/3.13/3.14'te hash'li kurulumu dener ve gerçek bir Linux'ta (`linux-smoke`) `harden.yml --check` çalıştırır.

> **Sınır:** CI canlı sunucu testi yerine geçmez; firewall/SSH değişiklikleri uygulanmaz (runner'ın kendi bağlantısını keserdi).
> Golden dosyaları bilerek değiştirirseniz: `UPDATE_GOLDEN=1 python3 -I test/test_templates.py` ve farkı PR'da inceleyin.

## Lisans

MIT, bkz. [LICENSE](LICENSE). Kullanım sorumluluğu size aittir: sertleştirme erişimi kesebilir; önce test sunucusunda deneyin.
