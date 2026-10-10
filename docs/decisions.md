# Kararlar ve istisnalar

| Tarih | Kontrol | Karar | Gerekçe |
|---|---|---|---|
| 2026-10-09 | login.defs aging/umask | Sadece yeni hesapları etkiler; mevcut kullanıcılara chage uygulanmadı | Test kullanıcısının kilitlenmesini önlemek |
| 2026-10-09 | sysctl net.ipv4.ip_forward | Bilerek dokunulmadı | LXD/konteyner/router kullanımını bozmamak |
| 2026-10-09 | fail2ban ignoreip | 10.0.0.0/8 muaf | Yönetim ağından kendini banlamamak; ortama göre daralt |
| 2026-10-09 | NOPASSWD sudo (test VM) | Geçici, hardening sonunda kaldırılacak | Ansible'ın non-interactive çalışması |
| BEKLEYEN | CIS 26.04 hazır rol / SSG 26.04 datastream | Çıkınca karşılaştır | 26.04'e özel hazır içerik henüz yok |
| 2026-10-09 | MTA | postfix purge, dma kuruldu | postfix kaldırınca apt courier-mta (25/tcp) kurdu; dma port dinlemez, MTA bağımlılığını karşılar |
| 2026-10-09 | SSH PasswordAuthentication | no (sadece anahtar) | cloud-init drop-in'i yes veriyordu; 00-hardening.conf önceliklidir |
| 2026-10-09 | SSH MaxSessions | 4 (Lynis önerisi 2) | Ansible bağlantı çoklamasıyla uyum |
| 2026-10-09 | SSH Port | 22 bırakıldı | Firewall ile yönetim ağına kısıtlı; port değişikliği ek güvenlik katmanı sayılmadı |
| 2026-10-09 | ufw | default deny incoming; SSH sadece 10.0.0.0/8 | Yönetim ağı (VPN) 10.0.0.0/8 içinde |
| 2026-10-09 | GRUB parolası, /home /var ayrı bölüm, uzak log, process accounting | Uygulanmadı | VM ortamında getirisi düşük / altyapı kararı gerektirir |
| 2026-10-10 | **BREAKING** hardening_ssh_allow_from varsayılanı | `10.0.0.0/8` kaldırıldı, varsayılan boş; boşsa harden.yml durur | Kilitlenme koruması. Eskiden belirtmeden çalıştırılan kullanım artık değişkeni vermek zorunda |
| 2026-10-10 | Kaynak IP kontrolü | Ansible'ın bağlandığı adres (SSH_CONNECTION) allow_from içinde değilse durur | ufw enable bağlantıyı keserdi. NAT/jump host'ta sunucunun gördüğü adres yazılmalı |
| 2026-10-10 | root ile çalışma | ansible_user/giriş kullanıcısı root ise durur | PermitRootLogin no yazılıyor; root ile devam etmek erişimi keser |
| 2026-10-10 | authorized_keys yolu | getent passwd ile gerçek home dizini | /home/<kullanıcı> varsayımı özel home'larda yanlış sonuç veriyordu |
| 2026-10-10 | Uygulama sonrası bağlantı doğrulaması | Yeni ssh bağlantısı testi; başarısızsa sshd drop-in sil + sshd reload + ufw disable | Geri alma SADECE ssh drop-in ve ufw'yi kapsar; paketler/sysctl/auditd/fail2ban/AIDE geri alınmaz; eski oturum canlı olmalı |
| 2026-10-10 | Değişken varsayılanlarının yeri | `hardening_*` varsayılanları rol `defaults/main.yml`'e taşındı; `inventory/group_vars/all.yml` yalnızca yorumlu örnek | `group_vars` yalnızca varsayılan inventory ile yüklenir; `-i /tmp/geçici.yml` ile (sshpocket) tüm değişkenler tanımsız kalıp roller düşüyordu. Efektif değerler DEĞİŞMEDİ; kullanılmayan `hardening_profile` kaldırıldı |
