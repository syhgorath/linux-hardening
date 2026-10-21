# CIS Debian Linux 13 Benchmark eşlemesi ve Proxmox VE notları (taslak)

Bu belge **CIS Debian Linux 13 Benchmark v1.1.0** (08-26-2026) için [Ubuntu eşlemesine](cis-esleme.md) bağlanır. Amaç iddia değil **boşlukları görmek**: proje tam CIS uyumu iddia etmez. CIS metni bu depoda yoktur; yalnızca madde **numaraları** ve kendi sözlerimiz var.

## Debian 13 için eşleme = Ubuntu eşlemesi (madde madde)

Debian 13 v1.1.0 ile Ubuntu 26.04 v1.0.0 PDF'lerinin içindekiler listeleri betikle karşılaştırıldı (2026-10-22): **341 madde, numaraları, başlıkları ve profilleri (Level 1/2, Server/Workstation) birebir aynı**; Level 1 - Server maddeleri de aynı. Gövdede (denetim/düzeltme betikleri) ~33 bin satırdan ~850'si farklı; bunların büyük kısmı biçim ve paket adları. İçerik farkı olarak gördüklerimiz: Level 2 auditd kuralında `execve,execveat` (Ubuntu'da yalnızca `execve`) ve APT/dpkg ayrıntıları. Bütün farklar tek tek incelenmedi.

Sonuç: **[cis-esleme.md](cis-esleme.md) tablosundaki numara → durum eşlemesi Debian 13 için de geçerlidir**, çünkü aynı roller aynı ayarları yazar. Dikkat:
- Debian 13 **konteynerde** sınandı (docs/SUPPORT.md, verification-log); Ubuntu tablosundaki ✅ ve ⚪ durumları Debian için **ölçülmedi**. ⚪ ("varsayılan uygun") özellikle Ubuntu varsayılanına dayanır, Debian'da farklı olabilir.
- Debian'da `ufw` kurulu gelmez (4.1.x): rol kurar ve `failed_when` ile ayrıca ele alır; kurulum sonrası eşleme aynıdır.
- `auditd` konteynerde çalışamaz; gerçek Debian 13 VM'inde `auditd` ile henüz DENENMEDİ.
- 1.5.7 (apport) ve 1.6.11/12 (`update-notifier-motd`) Ubuntu'ya özgü paketlerdir; Debian'da bu paketler yoksa madde zaten sağlanır; Debian konteyner koşusunda bu görevler hata vermedi.
- CIS-CAT/OpenSCAP taraması yapılmadı; tablo koddan okunarak çıkarıldı.

## Proxmox VE hostu için

Proxmox VE 9, Debian 13 üzerine kuruludur; CIS'in Proxmox'a özgü bir benchmark'ı **yok** (araştırılmadı, indirme yapılmadı). Temel olarak Debian 13 maddeleri kullanılır, ama aşağıdaki Level 1 - Server maddeleri Proxmox'ta farklı ele alınır. Hepsi iç içe Proxmox 9.2'de **bu yüzden böyle kodlandı**; yalnızca güvenlik duvarı gerçek koşuda denendi (verification-log 43).

| Madde | Konu | Proxmox'ta ne yapıyoruz |
|---|---|---|
| 4.1.1-4.1.3, 4.1.5 | ufw kurulu, servis, gelen varsayılan, yönlendirme varsayılanı | `ufw` HİÇ çalışmaz; güvenlik duvarı `pve-firewall`. `playbooks/pve-firewall.yml` gelen politikasını `DROP` yapar (4.1.3'ün amacı); maddelerin **denetim komutları ufw'yi aradığı için** CIS-CAT bunları geçmez. 🟡 |
| 2.1.22 | MTA yalnızca yerel | postfix → dma değişimi YAPILMAZ (postfix'i kaldırmak `pve-manager` ve `proxmox-ve`'yi kaldırır). Postfix yerel dinler; elle doğrulayın |
| 2.1.9, 2.1.23 | NFS kullanılmıyor, yalnızca onaylı servisler dinler | rpcbind (111) `pve-firewall` ile kapanır; spiceproxy (3128) yönetim ağlarına açık kalır |
| 3.3.1.1-3.3.1.3 | IPv4 yönlendirme | Köprü/NAT'lı VM ağı için gerekebilir. Rol `ip_forward`'a HİÇBİR platformda dokunmaz (bilerek, ⏸️ Ubuntu tablosunda) |
| 3.3.1.12, 3.3.1.13 | rp_filter | Proxmox'ta `2` (gevşek, asimetrik yönlendirme için); `hardening_pve_strict` ile `1` |
| 1.1.2.1.4, 1.1.2.2.4 | `/tmp` ve `/dev/shm` noexec | Proxmox'ta varsayılan KAPALI (yedek diski ve şablon çalıştırma iş akışı); `hardening_pve_strict=true` ile açılır |
| 1.1.1.10 | usb-storage | Proxmox'ta varsayılan KAPALI (USB yedek diski); `hardening_pve_strict=true` ile açılır |
| 5.1.22 | sshd PermitRootLogin kapalı | Tek düğümde `no`. KÜMEDE düğümler arası işlem kökten SSH ister: `hardening_ssh_permit_root_login=prohibit-password` (preflight kümede `no` ile durur) |
| 1.3.1.1, 1.3.1.2 | AppArmor | LXC profilleri AppArmor kullanır; dokunulmaz, kapatılmaz |
| 6.3 (AIDE) | bütünlük denetimi | `/etc/pve`, `/var/lib/pve-cluster`, `/var/lib/vz` vb. dışlanır (FUSE ve değişken veri) |

Proxmox'ta tam hardening koşusu (`harden.yml`) hâlâ **reddedilir** (`--check` önizlemesi hariç); yalnızca `pve-firewall` ayrı bir playbook'la yönetilir. SSH, kernel ve kalan roller için gerçek koşu kararı ayrı bir iştir.
