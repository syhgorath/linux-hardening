# Tasarım notu: Proxmox VE güvenlik duvarı (`pve-firewall`) yönetimi ve geri alma kapsamı (aşama 4)

**Durum:** UYGULANDI (birim testleri + nested ÖNİZLEME); GERÇEK koşu henüz yapılmadı. Karar: tek düğüm, kullanıcı dosyasına dokunma, ek portlar kapalı, `hardening_pve_apply` kapısı (öneriler benimsendi). Kod: `playbooks/pve-firewall.yml`, `roles/hardening_pve_firewall`. Proxmox'ta bu paketin yazacağı ilk DEĞİŞİKLİK YAPAN iş budur; yanlış bir kural hem yönetim arayüzünü (8006) hem SSH'ı hem VM'leri keser. Bu yüzden kod yazılmadan önce kullanıcı onayı alınır.
Kapsam: **tek düğümlü** Proxmox VE 9 (küme desteklenmez, reddedilir). Gerçek veriler iç içe Proxmox 9.2.21'den alındı (salt okunur, 2026-10-22).

## 1. Gerçekler (nested Proxmox 9.2.21'de görüldü)
- `pve-firewall` servisi çalışıyor ama güvenlik duvarı **devre dışı** (`Status: disabled/running`); `/etc/pve/firewall/` BOŞ (ne `cluster.fw` ne `host.fw` var); `iptables` politikaları `ACCEPT`, kural yok.
- Arka uç `iptables-legacy` (pve-firewall servisi kendisi ayarlıyor); `/etc/pve` bir **FUSE** dosya sistemi (`pmxcfs`), `root:www-data`; dosya sahibi/izni `chown`/`chmod` ile değiştirilemez.
- `pve-firewall localnet`: yönetim ağı **otomatik** algılanıyor (düğümün kendi yerel /24 ağı). Proxmox, güvenlik duvarı açılınca **8006 ve 22'ye bu yerel ağdan** erişimi kendiliğinden bırakır ("management").
- `pve-firewall compile`: kuralları üretip yazdırır, **hiçbir şeyi uygulamaz** → yazdığımız kuralların söz dizimini ETKİNLEŞTİRMEDEN doğrulamak için kullanılabilir.
- Tek düğümde `corosync` yok, VM/CT yok.

## 2. Ne yazacağız (öneri)
`/etc/pve/firewall/cluster.fw` (datacenter düzeyi) — `hardening_ssh_allow_from` ağlarından türetilir:
```
[OPTIONS]
enable: 1
policy_in: DROP
policy_out: ACCEPT

[IPSET management]
<allow_from içindeki her ağ>

[RULES]
IN SSH(ACCEPT) -source +management
IN ACCEPT -p tcp -dport 8006 -source +management
IN ACCEPT -p icmp -source +management
```
- `management` adlı IP kümesini kendimiz tanımlamak, Proxmox'un varsayılan "yerel ağ" kuralını bizim `allow_from` listemizle DEĞİŞTİRİR (VPN + LAN gibi birden çok ağ).
- Politika `DROP` (gelen): SSH, web arayüzü ve ping yalnızca yönetim ağlarından; geri kalan her şey (rpcbind 111, spiceproxy 3128, vb.) kapanır. Giden `ACCEPT`.
- **VM/CT güvenlik duvarları DEĞİŞMEZ** (VM düzeyinde `enable` ayrı bir karar; bu tasarımın kapsamı dışı). Datacenter politikası yalnızca güvenlik duvarı açık VM'lere uygulanır. *DENENMEDİ: nested'da VM yok.*
- `hardening_ufw_extra_allow` (ufw biçimi) Proxmox'a ÇEVRİLMEZ; başka port gerekirse `hardening_pve_firewall_extra_ports` (liste; varsayılan boş).

## 3. Güvenlik katmanları (sırayla)
1. **Ön koşullar (hiçbiri sağlanmazsa HİÇBİR ŞEY yazılmaz):** platform `proxmox-host`; tek düğüm (küme → reddet); `hardening_ssh_allow_from` dolu ve **kontrol makinesinin adresini kapsıyor** (mevcut erişim koruması); `cluster.fw` yok ya da `[RULES]`/`enable: 1` içermiyor (kullanıcının kendi kuralları VARSA DOKUNULMAZ, rapor edilir); `/etc/pve` yazılabilir (`pmxcfs` quorum'lu).
2. **Önce doğrula, sonra etkinleştir:** dosya `enable: 0` ile yazılır → `pve-firewall compile` çalıştırılır (söz dizimi hatası = DUR, dosya silinir) → ancak sonra `enable: 1`.
3. **Geri alma ağı (zamanlı):** `hardening_rollback` arm anında `/etc/pve/firewall/` ve `/etc/pve/nodes/*/host.fw` dosyalarını yedekler; süre dolunca: yedeği geri yaz (arm'da olmayan dosya SİLİNİR), `pve-firewall restart`; olmazsa `pve-firewall stop` (kuralları kaldırır). `pmxcfs` yazılamıyorsa bile `pve-firewall stop` bağımsız son çaredir.
4. **Yeni bağlantı doğrulaması:** mevcut `hardening_verify_access` (kontrol makinesinden YENİ ssh) + 8006'ya TCP bağlantısı; başarısızsa geri alma devreye girer, başarılıysa disarm.
5. **Gerçek koşu kapısı:** Proxmox'ta gerçek koşu yalnızca açık `hardening_pve_apply: true` (varsayılan false, `warn_if: true`) ile; hipervizör olduğu için kazara çalışmasın.

## 4. Ne YAPMAYACAĞIZ
Küme (corosync/ceph/SDN kuralları), VM/CT güvenlik duvarları, `nftables` modu, IPv6 özel kuralları, web arayüzü 2FA, `root@pam` yönetimi, `pveproxy` TLS. Hepsi ayrı karar ya da ayrı iş.

## 5. Bilinmeyenler (nested'da deneyip belgelenecek)
1. `ansible.builtin.copy` ile `/etc/pve/firewall/cluster.fw` yazılabilir mi (FUSE: atomik rename, sahip/izin)? Olmazsa `unsafe_writes` ya da `pvesh` (API) yolu.
2. `[IPSET management]` tanımı varsayılan "yerel ağ" kuralını gerçekten ezip yalnızca bizim ağlara izin veriyor mu (`pve-firewall compile` çıktısıyla görülecek).
3. Etkinleştirmeden sonra yeni SSH bağlantısı ve 8006 gerçekten çalışıyor mu; kontrol makinesi `management` dışındaysa kesiliyor mu (geri alma tetiklenmeli).
4. Geri alma: `pmxcfs`'ten dosya silme/yazma, `pve-firewall restart` sonrası kuralların kalkması.
5. `fail2ban` (iptables) ile `pve-firewall` birlikte: zincir sırası bozuluyor mu.
6. İlk gerçek koşu için **snapshot şart**; konsol erişimi (dış Proxmox üzerinden nested VM konsolu) kurtarma yoludur.

## 6. Test planı (nested Proxmox, snapshot'tan)
1. `--check`: dosyalar yazılmaz, ön koşul mesajları doğru (küme, allow_from, kullanıcı kuralı).
2. Gerçek koşu: `enable: 0` yazımı → `compile` → etkinleştirme; `pve-firewall status` `enabled/running`; `iptables -S` beklenen kurallar; yeni SSH ve 8006 çalışır; ikinci koşu `changed=0`.
3. **Bilerek bozuk senaryolar:** (a) söz dizimi hatalı kural → compile DURUR, dosya silinir; (b) kontrol makinesini kapsamayan `allow_from` → ön koşul reddeder; (c) kuralı etkinleştirip doğrulamayı atlatma (ağı kapat) → zamanlı geri alma süre dolunca kuralları kaldırır; (d) kullanıcının mevcut `cluster.fw` dosyası → dokunulmaz.
4. Geri alma sonrası `pve-firewall status` `disabled/running`, SSH ve 8006 erişilebilir.

## 7. Açık sorular (kullanıcı kararı)
1. Yalnızca **tek düğüm**, küme reddedilsin mi? (öneri: evet)
2. Mevcut `cluster.fw`'de kullanıcı kuralı varsa **dokunma ve rapor et** mi, birleştir mi? (öneri: dokunma)
3. Ek portlar varsayılan **kapalı** mı (3128 SPICE ve 111 rpcbind kapanır)? (öneri: kapalı, `hardening_pve_firewall_extra_ports` ile açılır)
4. Gerçek koşu için ayrı `hardening_pve_apply: true` kapısı olsun mu? (öneri: evet)
