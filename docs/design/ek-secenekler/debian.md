# Debian: aday ek seçenekler

**Durum:** ADAY LİSTESİ, kod yok. Genel kurallar: [README](README.md). İşaret: `[ ]` karar bekliyor, `[x]` yap, `[-]` yapma, `[?]` konuşalım.

Ortam: Debian 13. Ubuntu listesindeki seçeneklerin çoğu ([ubuntu.md](ubuntu.md): A bölümü, U-B1, U-B3, U-B6, U-C1) Debian'a da aynen uyar; bu belge yalnızca **farkları** ve Debian'a özgü adayları listeler.

Bilinen: bu proje Debian 13'ü bir konteyner labında (`ufw` yok, `auditd` çalışmıyor) denedi; **gerçek Debian VM'de auditd'li koşu yapılmadı.** Aşağıdakilerin hepsi gerçek VM gerektirir.

| # | Aday | Fark / not |
|---|---|---|
| [ ] D-1 | **Güvenlik duvarı arka ucu** | Debian'da `ufw` kurulu gelmiyor; bugün atlanıyor. Aday: `nftables` ile eşdeğer yönetim. Büyük iş; ayrı tasarım gerekir |
| [ ] D-2 | **`apt-listbugs`** | Zaten var (`hardening_apt_listbugs`, pasif). Debian'a özgü; Ubuntu'da anlamsız. Platform süzmesi gözden geçirilecek |
| [ ] D-3 | **`ENCRYPT_METHOD`** | Debian varsayılanı yescrypt; `hardening_encrypt_method` (U-A14) ile görünür kılınır |
| [ ] D-4 | **Gerçek VM'de auditd'li tam koşu** | Doğrulama işi, aday değil |
| [ ] D-5 | **Sürüm farkı** | `ansible_distribution_version` alt sürümle gelir (13.7); sabitler ana sürüme bağlı kalmalı (bugün öyle) |

Debian için yeni seçenek listesi bilerek kısa tutuldu: önce Ubuntu ve Proxmox'ta sistem oturur, Debian farkları sonra gerçek VM bulgularıyla genişler.
