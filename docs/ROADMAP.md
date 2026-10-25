# Yol haritası

Sıra bağlayıcı değildir. Kararlar ve istisnalar: [decisions.md](decisions.md); denenenler: [verification-log.md](verification-log.md).

## Yakın
| İş | Not |
|---|---|
| CIS Grup 2 kalanları | Grup 2'nin kodlanan kısmı (core dump, `TMOUT`, `INACTIVE`, günlük dosyası izinleri, `telnet`/`ftp` kaldırma) birleşti, hepsi varsayılan KAPALI. **Kalan, tasarım gerekir:** `/tmp` ve `/dev/shm` `noexec` (sistemde `tmp.mount` ya da fstab, yeniden bağlama, PHP/kurulum etkisi), `su` kısıtı (PAM düzenleme, kilitlenme), kullanıcı dot dizinleri (kullanıcıları habersiz etkiler; CIS kendisi uyarıyor). `telnet`/`ftp` notu: port açmazlar ama `telnet host port` ile port yoklayan betikleri ve `ftp` yedek akışlarını kırar; kaldırma `apt remove`, geri alma `apt install` |
| Docker sunucusu rolü | **İlk dilim kodlandı** (`hardening_docker`: rapor + `daemon.json` birleştirme, dosya izinleri, auditd; varsayılan kapalı). **Kalan:** gerçek Docker'la doğrulama (mini labda kurulum, indirme: boyut/kaynak önceden sorulur), `no-new-privileges`/`userland-proxy`/`icc` seçenekleri. Tasarım: [design/docker-sunucusu.md](design/docker-sunucusu.md) (CIS Docker Benchmark v1.9.0 bölüm 1-3: dosya izinleri, auditd kuralları, `daemon.json` birleştirme, ufw/Docker riski). Önce notun açık soruları cevaplanmalı; test için Docker kurulumu (indirme) gerekir, boyut ve kaynak önceden sorulur |
| Senaryo (3 sunucu) kalanları | `extra_allow` sshpocket'e açıldı, liste birleşmesi ve `examples/` hazır (#65, #67). Yedek PULL yönü için örnek yazıldı: [examples/yedek-pull.md](../examples/yedek-pull.md) (**denenmedi**, yedek sunucusu yok; kullanıcı/anahtar yönetimi bu projenin kapsamı dışı). **Kalan:** örneğin gerçek bir yedek sunucusunda denenmesi, Redis/nginx/Docker'ın kendi ayarları için yalnızca belge |
| Küçük Lynis maddeleri | Lynis önce/sonra ölçüldü (58 → 73, [verification-log.md](verification-log.md) madde 21). Kalan **küçük ve güvenli** olanlar: `fs.protected_fifos=2`, `kernel.sysrq=0`, `net.core.bpf_jit_harden=2`, AIDE SHA256/SHA512, `libpam-tmpdir`. `apt-listchanges` eklendi (apt-listbugs Ubuntu'da yok). Düşük değerli: `debsums`, `apt-show-versions`, `acct`. Sunucu davranışını değiştirir: canlı doğrulama gerekir |
| Eski `ubuntu` grubunu kaldır | Uyarı artık çıkmıyor (#35, olmayan grup seçilmiyor); kaldırmak yalnızca bir temizlik ve BREAKING olarak işaretlenir |
| Tarama klasörü zaman damgası | Klasör adı yerel saatle, `summary.json` UTC; tek biçime getirilebilir |
| v0.3.0 yayını | Yayımlandı (CIS Ubuntu 26.04 Level 1 Server eşlemesi, `hardening_files`/`hardening_sudo`/`hardening_docker` rolleri, zaman raporu, `examples/`, README "Dikkat") |
| v0.4.0 yayını | Yayımlandı (küçük Lynis maddeleri, `apt-listchanges`, AIDE zamanlayıcı, `su` kısıtı, Docker `daemon.json` seçenekleri, root ortamı ve `/tmp` raporları, Grup 3 tasarım notu) |
| v0.5.0 yayını | Yayımlandı (`/tmp` ve `/dev/shm` noexec varsayılan açık, `pam_faillock`, `pam_pwhistory`, geri alma PAM kapsamı, Proxmox koruması, `hardening_time_makestep`, sudo-rs + Ansible bulgusu). Etiket, imza ve Release bakımcıda; sonra sshpocket `components.lock` |
| v0.6.0 yayını | Yayımlandı (Debian 13, Proxmox VE tek düğüm: pve-firewall ve tam sertleştirme, Raspberry Pi platformu, CIS Level 1 kalan maddeler: salt okunur rapor, pwquality/journald/sshd erişim seçenekleri, menüye 15 eksik ayar, cron sırası düzeltmesi) |
| v0.7.0 yayını | Yayımlandı (Proxmox güvenlik duvarı için `pve_firewall_preview`/`pve_firewall_apply` eylemleri, CIS Level 1 Server'da kalan son 3 madde, opt-in `hardening_auditd_cis_l2`, `hardening_motd_disable_scripts`) |
| v0.7.1 | Yayımlanmadı: içeriği v0.8.0'a katıldı |
| v0.8.0 yayını | Yayımlandı (Lynis puanı için seçenekler, `log_martians` ve `pve_firewall_preview` düzeltmeleri, CIS Level 2 seçenekleri: auditd/AIDE, ufw giden DROP, AppArmor, derleyici kısıtı, rkhunter; `docs/deneme-matrisi.md`) |
| v0.8.1 yayını | Yayımlandı (`kernel_modules_disabled` + ufw önyükleme modül listesi, `verify_access` ssh-agent ipucu ve ek bağımsız değişken, manifest sınırları, deneme matrisi) |
| v0.8.2 yayını | Hazırlandı (Proxmox'ta `kernel_modules_disabled` reddi, `hardening_fail2ban_pve_web`, `hardening_pve_pveproxy_allow_from`) |

## Orta
| İş | Not |
|---|---|
| Gerçek ağ/ufw düzeyi kesinti denemesi | Mevcut denemeler sshd katmanında engelle yapıldı |
| İkinci sunucu/yapılandırma | Tek VM ile sınırlı kanıtı genişletmek |
| CIS eşlemesinin devamı | Madde numaralı eşleme var: [cis-esleme.md](cis-esleme.md). Kalan ❌ maddeler "Grup 2" ve "Grup 3" olarak ayrıldı (aşağıdaki "Yakın" satırı ve PAM/zaman/AIDE tasarım notları) |
| auditd kapsamı | Kurallar play sonunda yükleniyor (P3), auditd'den önce başlayan süreçler denetlenmiyor (P1), `time-change` kuralı chrony'yi kapsamıyor (P2). **Tasarım notu var (kod yok):** [design/auditd-kapsam.md](design/auditd-kapsam.md) |
| Grup 3: `/tmp`+`/dev/shm` noexec, `su` kısıtı, root ortamı | CIS 5.2.7 ve 1.1.2 / 5.4.2 altındaki `noexec` ile root ortamı maddeleri (numaralar tasarım notunda). **Tasarım notu var (kod yok):** [design/grup3-tmp-su-root.md](design/grup3-tmp-su-root.md) |
| `pam_faillock` / `pam_pwhistory` | CIS 5.3 PAM maddeleri; kilitlenme riski yüksek. **Tasarım notu var (kod yok):** [design/pam-faillock.md](design/pam-faillock.md) |
| Zaman senkronizasyonu rolü | Snapshot dönüşünde saat geride kaldı; `chrony` yapılandırması bir hardening maddesi olabilir. **Tasarım notu var (kod yok):** [design/zaman-ntp.md](design/zaman-ntp.md) |
| Çok sunuculu çalıştırma | `serial`/`any_errors_fatal`: bir sunucudaki hata diğerlerini durdurmalı mı |

## Uzak
| İş | Not |
|---|---|
| Raspberry Pi / Proxmox profilleri | Firewall (Proxmox `pve-firewall`), `ip_forward`, SD kart yazım aşınması farklı; ayrı roller. **Proxmox hostu:** tasarım notu ve boş iskelet var, işlevsiz: [design/proxmox-host.md](design/proxmox-host.md) |
| Başka Ubuntu sürümü (24.04) | `docs/SUPPORT.md` adımları |
| Tarama sonuçlarını karşılaştırma | `summary.json`'dan öncesi/sonrası (sshpocket arayüzü ile) |

## sshpocket entegrasyonu (o repoda)
Bileşen yükleyici, sözleşmeyi okuyan ayrıştırıcı, menü ve güvenlik kapıları sshpocket tarafında; takip:
syhgorath/sshpocket#3.
