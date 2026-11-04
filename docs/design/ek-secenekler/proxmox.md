# Proxmox VE: aday ek seçenekler

**Durum:** ADAY LİSTESİ, kod yok. Genel kurallar: [README](README.md). İşaret: `[ ]` karar bekliyor, `[x]` yap, `[-]` yapma, `[?]` konuşalım.

Ortam: tek düğümlü Proxmox VE 9 (nested ya da fiziksel). **Küme desteklenmiyor / doğrulanmadı.** Misafir (VM/CT) çalışan hostta denenmemiş her şey ayrıca işaretlenir. Gerçek koşu için `hardening_pve_apply=true` ve snapshot gerekir.

## Zaten var (tekrar eklenmez)

`hardening_pve_strict`, `hardening_pve_keep_banner`, `hardening_aide_pve_excludes`, `hardening_pve_pveproxy_allow_from` (`DENY_FROM`/`ALLOW_FROM`), `hardening_pve_web_allow_from` ve `_exclusive`, `hardening_pve_firewall_extra_ports`, `hardening_fail2ban_pve_web` (8006 için fail2ban jail'i), `hardening_pve_pveproxy_enabled`, `hardening_pve_apply`.

## A. Sabit değeri değişkene çevir

| # | Aday | Not |
|---|---|---|
| [ ] P-A1 | `hardening_pve_firewall_policy_in`, `_policy_out`, `_log_level` (Datacenter düzeyi) | Şu an sabit; DROP/ACCEPT. Politikayı gevşetmek değil, görünür kılmak. DENENMEDİ: misafir güvenlik duvarı etkileşimi |
| [ ] P-A2 | Ortak ayarların Proxmox için ayrı geçersiz kılınması (bugün platforma özgü davranış `hardening_platform_relaxed` ile örtük; hangileri açık değişken olmalı) | Gözden geçirilecek: hangi ortak ayarlar Proxmox'ta farklı olmak zorunda |

## B. Yeni pasif seçenekler

| # | Aday | Ne yapar | Risk / koşul |
|---|---|---|---|
| [ ] P-B1 | **apt upgrade koruması** (`hardening_pve_apt_hold`) | `hardening_apt_upgrade` açıkken `proxmox-ve`, `pve-manager`, `pve-kernel-*` / `proxmox-kernel-*` paketlerini yükseltmeden hariç tutar (hold) | Güncelleme kaçar; kullanıcı Proxmox'u kendi yükseltir. **En çok önerdiğim madde**: `apt-get upgrade` pve servislerini yeniden başlatıp VM'leri etkileyebilir. Paket adları sürümde doğrulanmalı |
| [ ] P-B2 | **pveproxy TLS ince ayarı** (`hardening_pve_pveproxy_ciphers`, TLS sürümleri) | `/etc/default/pveproxy` içine şifre listesi yazar | Seçenek adları Proxmox belgesinden doğrulanacak (hafızadan, DOĞRULANMADI). Eski istemciler bağlanamaz |
| [ ] P-B3 | **spiceproxy'yi kapat** (`hardening_pve_disable_spiceproxy`) | 3128 portunu dinleyen servisi maskeler | SPICE konsolu kullanan VM kırılır. `pve_web_exclusive` güvenlik duvarıyla kapatıyor; bu servis düzeyinde ek |
| [ ] P-B4 | **rpcbind'i kapat** (`hardening_pve_disable_rpcbind`) | 111 portunu kapatır | NFS depolama kullanan host kırılır; depolama tespiti gerekir |
| [ ] P-B5 | **postfix yalnız yerel** (`hardening_pve_postfix_loopback`) | `inet_interfaces=loopback-only` | MTA'yı **değiştirmez** (kaldırmak pve-manager'ı kaldırır); dışarı yönlendirme/relay varsa bildirim e-postaları kırılır |
| [ ] P-B6 | **auditd'ye Proxmox kuralları** (`hardening_auditd_pve_rules`) | `qm`/`pct`/`pvesh` çağrıları ve yapılandırma yolları için kurallar | `/etc/pve` bir FUSE dosya sistemi (pmxcfs); inotify/audit izlemesi çalışmayabilir. DENENMEDİ, önce çalıştığı kanıtlanmalı |
| [ ] P-B7 | **VM/CT güvenlik duvarı varsayılanları** (Datacenter: `ebtables`, `ip_filter`, `macfilter` gibi) | Misafir düzeyi korumalar | Misafir ağını doğrudan etkiler; yalnız misafirli hostta denenmeli |

## C. Salt okunur rapor / ölçüm

| # | Aday | Ne yapar |
|---|---|---|
| [ ] P-C1 | **Misafir sağlık betiği** | Sertleştirmeden önce/sonra `qm list`, `pct list`, köprü/ağ, depolama ve Docker'lı misafir durumunu karşılaştırır. Fiziksel/misafirli hosta geçişten önce kontrol listesi |
| [ ] P-C2 | **Proxmox hesap raporu** | `pveum` ile kullanıcı/realm listesi, iki adımlı doğrulama (TFA) olmayan hesaplar. Hiçbir şeyi değiştirmez |
| [ ] P-C3 | **Kullanılmayan servis/port raporu** | `approved_listeners` ile birlikte Proxmox'a özgü beklenen port listesi (22, 8006 ve gerekenler) |

## D. Bilinmeyenler (aday değil, doğrulama işi)

- Kümeli Proxmox: `PermitRootLogin` ve `knet` modül yasağı davranışı **DENENMEDİ**, destek yok.
- Misafirli host: tam harden koşusunun misafirlere etkisi **DENENMEDİ** (sshpocket turunda bir CT ayaktayken preview ve apply başarılı oldu ve CT ayakta kaldı; başka senaryolar yok).
- UEFI+ZFS kurulumda GRUB yok (systemd-boot): önyükleyici parolası seçeneği Proxmox'ta uyarı verip atlamalı. Bu bir not, bir hostta doğrulanmadı.
