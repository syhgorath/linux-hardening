# Deneme matrisi (sshpocket'te seçenek seçenek denenenler)

Amaç: her seçeneği **sshpocket üzerinden**, gerçek kullanım senaryosunda (Ubuntu, Proxmox, Raspberry Pi; web, MySQL, Docker iş yükü) açıp kapatarak denemek ve sonucu burada tutmak.
Bir seçenek **varsayılan AÇIK** yapılmadan önce üç platformda ve en az web + MySQL + Docker iş yükünde sorun çıkarmamış olmalıdır; bir platformda bozuyorsa o platformda gevşetilir ya da KAPALI kalır.
Not satırlarını sshpocket'te denedikçe ekleyin (kısa: "seçenek, platform, iş yükü, sonuç, ne oldu").

Sonuç: ✅ sorunsuz | ⚠️ sorunlu (nasıl) | 💥 bozdu (nasıl) | ⏳ denenmedi | — uygulanmaz

**Son tur:** sshpocket 3.6.10, linux-hardening 0.8.0, gerçek Ubuntu 26.04 VM ve Proxmox VE (Debian 13) VM. **İş yükü yoktu** (web/MySQL/Docker denenmedi): "sorunsuz" yalnızca servis ve erişim denetimi demektir.

| Seçenek | Varsayılan | Colima (Ubuntu 26.04) | Ubuntu sshpocket | Proxmox sshpocket | Pi sshpocket | Not |
|---|---|---|---|---|---|---|
| `hardening_debsums` (+ `_cron_check`) | açık | ✅ kurulur, `CRON_CHECK=weekly` | ✅ varsayılan koşu `failed=0`, 2. önizleme `changed=0` | ✅ varsayılan koşu `failed=0` | ⏳ | haftalık kontrolün e-posta çıktısı izlenmedi |
| `hardening_apt_show_versions` | açık | ✅ | ✅ | ✅ | ⏳ | puan için yükseltilebilir paket de kalmamalı |
| `hardening_process_accounting` | açık | ✅ `acct` etkin | ✅ | ✅ | ⏳ |  |
| `hardening_fail2ban_jail_local` | açık | ✅ | ✅ | ✅ | ⏳ |  |
| `hardening_ufw_log_martians` | açık | ✅ hata yeniden üretildi (0) ve düzeltildi (1) | ✅ Lynis KRNL-6000 kapandı | — (ufw yok) | ⏳ |  |
| `hardening_apt_upgrade` | KAPALI | ✅ | ⚠️ güncel sistemde değişiklik yok; 2 ubuntu-pro-client paketi kademeli (phased) güncellemede kaldı | ⏳ | ⏳ | PKGS-7392 için bekleyen güncellemesi olan VM gerekir (doğrulanamadı); phased paketler apt-show-versions puanını da engelleyebilir |
| `hardening_kernel_modules_disabled` | KAPALI | ⏳ | 💥 (v0.8.0) ufw yeniden başlatmada AÇILMADI, güvenlik duvarı sessizce kapalı; netfilter + binfmt_misc elle önyüklenince ✅. v0.8.1'de düzeltme: önyükleme öncesi modül listesi (yeniden DENENMELİ) | ⏳ (KVM/bridge modülleri) | ⏳ | açıkken: yeniden başlatmadan sonra `ufw status` ve `systemctl --failed` ile doğrula |
| `hardening_auditd_conf_cis` | KAPALI | ✅ | ✅ apply hatasız, auditd aktif | ⏳ | ⏳ | Lynis doğrudan ölçmüyor; kapatınca değerler geri alınmaz |
| `hardening_auditd_disk_full_halt` | KAPALI | ✅ | ⚠️ apply hatasız; disk doldurulmadı, `halt` davranışı DENENMEDİ | ⏳ | ⏳ | disk dolunca sunucu kapanır |
| `hardening_auditd_backlog_limit` (8192) | 0 | ✅ GRUB yok uyarısı (konteyner) | ✅ yeniden başlatma sonrası `/proc/cmdline` içinde `audit_backlog_limit=8192` | ⏳ | ⏳ |  |
| `hardening_auditd_immutable` | KAPALI | ✅ dosya yazılır/silinir | ✅ kilitliyken 2. önizleme `changed=0`, paket algılayıp uyarıyor (`-e 2` etkisi `auditctl` ile ayrıca doğrulanmadı) | ⏳ | ⏳ | yeniden başlatmaya kadar kural değişmez |
| `hardening_aide_audit_tools` | KAPALI | ✅ dosya yazılır/silinir | ✅ kuruldu, hata yok (AIDE'nin kuralı uyguladığı ölçülmedi) | ⏳ | ⏳ |  |
| `hardening_ssh_max_sessions` (2) | 4 | ✅ | ✅ sshpocket bağlantı biçimiyle yeni SSH doğrulaması geçti; SSH-7408 iki satırdan bire | ⏳ | ⏳ | Port satırı (SSH-7408) kalır: port değiştirme desteklenmez |
| `hardening_ufw_outgoing_deny` | KAPALI | ✅ | ✅ 443/80 bağlandı, 8080/25/2222/8443 DROP, SSH ve audit sorunsuz, 2. önizleme `changed=0` | — (ufw yok) | ⏳ | Proxmox'ta uygulanmaz |
| `hardening_restrict_compilers` | KAPALI | ⏳ (gcc yok) | ✅ HRDN-7222 kapandı (yalnız `/usr/bin/as` vardı; gerçek gcc/clang iş yükü DENENMEDİ) | ⏳ | ⏳ | root olmayan derleme bozulur |
| `hardening_apparmor_enforce` | KAPALI | ⏳ (konteynerde AppArmor kapalı) | ✅ complain→enforce; DNS, NTP, https, ssh sağlam | ⏳ (LXC profilleri) | ⏳ | Docker/LXC etkisi iş yüküyle denenmeli |
| `hardening_malware_scanner` (rkhunter) | none | ✅ | ✅ HRDN-7230 kapandı | ⏳ | ⏳ | günlük kontrolün yanlış alarmı izlenmedi |
| `pve_firewall_preview` / `pve_firewall_apply` | — | — | — | ✅ önizleme `apply=true` ile `changed=0`; uygulama: cluster.fw yazıldı, ssh, 8006, ping sağlam, FIRE-4512 kapandı | ⏳ | kümeli Proxmox denenmedi |

## Lynis hardening index (sshpocket 3.6.10)

| Platform | Taban | 0.7.0 | 0.8.0 varsayılan | Seçenekler açılınca |
|---|---|---|---|---|
| Ubuntu 26.04 VM | 61 | 82 | 83 | 84 → 85 → 85 (ufw giden DROP) → 85 (öneri 47 → 15, KRNL-6000 kapandı) |
| Proxmox VE VM | 62 | 81 | 83 | 83 (`pve_firewall_apply`: uyarı 4 → 3, FIRE-4512 kapandı, FIRE-4513 öneri geldi) |

Seçenek grupları (G1/G2/G3) sshpocket tarafının test gruplarıdır; hangi seçenekleri içerdiği sürüm notlarında yok. Kalan Ubuntu önerileri: apt-listbugs (Ubuntu'da yok), GRUB parolası (karar: yok), bölüm ayrımı, DNS alan adı, eski paket temizliği, SSH-7408 (Port), uzak log sunucusu, silinmiş dosyalar, AIDE sha256 (FINT-4402 yanlış pozitif), sysctl farkları.

## Henüz denenmeyenler

Proxmox'ta bu seçenekler (özellikle `kernel_modules_disabled`: KVM/bridge modülleri), Raspberry Pi, kümeli Proxmox, gerçek donanım; web/MySQL/Docker iş yükleri; `apt_upgrade` bekleyen güncellemeyle (PKGS-7392); `auditd_disk_full_halt` davranışı; silahlı (armed) geri alma gerçek VM'de; `ufw_outgoing_deny` Proxmox'ta (ufw yok).
