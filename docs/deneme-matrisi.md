# Deneme matrisi (sshpocket'te seçenek seçenek denenenler)

Amaç: her seçeneği **sshpocket üzerinden**, gerçek kullanım senaryosunda (Ubuntu, Proxmox, Raspberry Pi; web, MySQL, Docker iş yükü) açıp kapatarak denemek ve sonucu burada tutmak.
Bir seçenek **varsayılan AÇIK** yapılmadan önce üç platformda ve en az web + MySQL + Docker iş yükünde sorun çıkarmamış olmalıdır; bir platformda bozuyorsa o platformda gevşetilir ya da KAPALI kalır.
Not satırlarını sshpocket'te denedikçe ekleyin (kısa: "seçenek, platform, iş yükü, sonuç, ne oldu").

Sonuç: ✅ sorunsuz | ⚠️ sorunlu (nasıl) | 💥 bozdu (nasıl) | ⏳ denenmedi

| Seçenek | Varsayılan | Colima (Ubuntu 26.04) | Ubuntu sshpocket | Proxmox sshpocket | Pi sshpocket | Not |
|---|---|---|---|---|---|---|
| `hardening_debsums` (+ `_cron_check`) | açık | ✅ kurulur, `CRON_CHECK=weekly`, 2. koşu `changed=0` | ⏳ | ⏳ | ⏳ | |
| `hardening_apt_show_versions` | açık | ✅ | ⏳ | ⏳ | ⏳ | |
| `hardening_process_accounting` | açık | ✅ `acct` etkin, `pacct` yazılıyor | ⏳ | ⏳ | ⏳ | |
| `hardening_fail2ban_jail_local` | açık | ✅ | ⏳ | ⏳ | ⏳ | |
| `hardening_apt_upgrade` | KAPALI | ✅ 1. koşu `changed=1`, 2. `changed=0` | ⏳ | ⏳ | ⏳ | servis yeniden başlatma etkisi sshpocket'te bakılacak |
| `hardening_auditd_conf_cis` | KAPALI | ✅ değerler yazılır, 2. koşu `changed=0` | ⏳ | ⏳ | ⏳ | kapatınca değerler geri alınmaz |
| `hardening_auditd_disk_full_halt` | KAPALI | ✅ | ⏳ | ⏳ | ⏳ | disk dolunca sunucu kapanır |
| `hardening_auditd_backlog_limit` | 0 | ✅ GRUB yok uyarısı (konteyner) | ⏳ | ⏳ | ⏳ | yeniden başlatma gerekir |
| `hardening_auditd_immutable` | KAPALI | ✅ dosya yazılır/silinir; kilit davranışı VM'de denenmeli | ⏳ | ⏳ | ⏳ | `-e 2`: yeniden başlatmaya kadar kural değişmez |
| `hardening_aide_audit_tools` | KAPALI | ✅ dosya yazılır/silinir; AIDE'nin kuralı gerçekten uyguladığı VM'de denenmeli | ⏳ | ⏳ | ⏳ | |
| `hardening_ssh_max_sessions` (2) | 4 | ✅ Mac'ten `MaxSessions 2` ile 4 koşu sorunsuz | ⏳ | ⏳ | ⏳ | sshpocket'in bağlantı biçimiyle denenmeli |
| `hardening_ufw_outgoing_deny` | KAPALI | ✅ giden varsayılan deny, SSH düşmedi, kapatınca allow | ⏳ | — (ufw yok) | ⏳ | izin listesi dışı yeni giden bağlantılar kesilir |
| `hardening_restrict_compilers` | KAPALI | ⏳ konteynerde gcc yok (birim testi gerçek chmod) | ⏳ | ⏳ | ⏳ | root olmayan derleme bozulur |
| `hardening_apparmor_enforce` | KAPALI | ⏳ konteynerde AppArmor kapalı (NOT verir) | ⏳ | ⏳ (LXC profilleri) | ⏳ | Docker/LXC etkisi VM'de bakılacak |
