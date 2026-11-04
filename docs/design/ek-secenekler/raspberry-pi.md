# Raspberry Pi: aday ek seçenekler

**Durum:** ADAY LİSTESİ, kod yok. Genel kurallar: [README](README.md). İşaret: `[ ]` karar bekliyor, `[x]` yap, `[-]` yapma, `[?]` konuşalım.

Ortam: Raspberry Pi OS (Debian tabanlı, arm64). Gerçek cihaz **mevcut** ama sıra en sonda: önce Ubuntu, Proxmox, Debian oturur. Bugüne kadar yalnız arm64 Debian konteynerinde denendi; **Pi donanımında hiçbir şey denenmedi.** Aşağıdakilerin hepsi cihaz gerektirir ve "DENENMEDİ" olarak başlar.

Zaten var: platform `raspberry-pi` (`auto_detect` kapalı, kullanıcı seçer), `hardening_rpi_strict` (varsayılan gevşek; `true` usb-storage engelini uygular), `/etc/default/grub` yoksa GRUB ayarlarına dokunulmaması.

| # | Aday | Ne yapar | Risk / koşul |
|---|---|---|---|
| [ ] R-1 | **SD kart yazımını azalt** (`hardening_rpi_volatile_logs`) | journald'i bellekte tutar / `/var/log` için tmpfs | Yeniden başlatmada günlük kaybolur; kalıcı günlük seçeneğiyle çelişir. Uyarılı |
| [ ] R-2 | **Wi-Fi / Bluetooth'u kapat** (`hardening_rpi_disable_wifi`, `_bluetooth`) | Önyükleme yapılandırmasına overlay satırı / `rfkill` | Wi-Fi ile bağlı Pi'de erişimi keser; kablosuz yönetilen cihazda tehlikeli. Geri alma ağı kapsamaz |
| [ ] R-3 | **Varsayılan kullanıcı raporu** | Fabrika kullanıcısı (`pi`) ya da parolasız hesap var mı (salt okunur) | Rapor, risk yok |
| [ ] R-4 | **Saat kaynağı** | RTC olmayan Pi'de `chrony` ve ilk açılış saati davranışı | DENENMEDİ; zaman bölümüyle birlikte |
| [ ] R-5 | **Güvenlik duvarı** | Raspberry Pi OS'ta `ufw` varsayılan gelmiyor; Debian listesi D-1 ile aynı iş | Büyük iş, ortak |

Pi tarafında seçenek eklemeden önce **cihazda bir ölçüm turu** (Lynis, `systemd-analyze security`, açık portlar) yapılması önerilir; liste bu ölçümden sonra daraltılır.
