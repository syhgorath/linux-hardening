# Güvenlik politikası / Security policy

Bu depo, sunucularda **kök yetkisiyle** çalışan ve SSH/firewall ayarlarını değiştiren bir sertleştirme aracıdır.
Hatalı bir davranış sunucuya erişimi kesebilir ya da güvenliği sessizce zayıflatabilir; bu yüzden güvenlik
açıklarını ciddiye alıyoruz.

## Açık bildirme

**Lütfen güvenlik açıklarını herkese açık issue olarak açmayın.**
GitHub'daki **Security → Report a vulnerability** (özel bildirim) yolunu kullanın:
<https://github.com/syhgorath/linux-hardening/security/advisories/new>
*Please do not open public issues for vulnerabilities; use GitHub's private "Report a vulnerability" form.*

Bildirimde şunlar yardımcı olur: etkilenen rol/dosya, hangi değişkenlerle/komutla tekrarlandığı, etkisi
(erişim kaybı mı, koruma atlatma mı, gizli bilgi sızıntısı mı). **Gerçek IP, anahtar, parola veya sunucu
bilgisi eklemeyin**; örnek aralık olarak `192.0.2.x` kullanın.

Proje tek kişilik ve gönüllü bir çalışma; yanıt süresi için söz veremem ama makul sürede bakmaya çalışırım.

## Kapsam

- **Kapsam içi:**
  - Erişim kaybı korumalarının atlanması (`hardening_ssh_allow_from`, kaynak IP/root kontrolü, bağlantı
    doğrulaması ve geri alma).
  - Güvenli varsayılanların sessizce zayıflaması (ör. `PasswordAuthentication`, `PermitRootLogin`,
    `AuthenticationMethods`, firewall varsayılanları).
  - Gizli bilginin diske, log'a veya komut satırına sızması (parola, anahtar, `summary.json`/tarama çıktısı izinleri).
  - Komut/şablon enjeksiyonu (değişken değerlerinin kabuğa ya da yapılandırma dosyasına doğrulanmadan yazılması).
  - Tedarik zinciri: hash'li `requirements.txt`, imzalı sürüm paketi (`docs/RELEASING.md`) atlatma.
- **Kapsam dışı:**
  - Sunucuyu kendi yapılandırmanızla (ör. `hardening_ssh_allow_from` yanlış) kilitlemek; bu bir yapılandırma hatasıdır.
  - Desteklenmeyen sistem/sürümlerde (`docs/SUPPORT.md`) çalıştırmak (`hardening_allow_unsupported=true`).
  - Bu araç tarafından **yapılmayan** sertleştirmeler (GRUB parolası, disk bölümleme, uzak log...); bkz. `docs/decisions.md`.
  - Üçüncü taraf bileşenlerin (Ansible, Lynis, OS paketleri) kendi açıkları; bunları ilgili projeye bildirin.

## Desteklenen sürümler

Yalnızca `main` dalının son hâli ve en son etiketli sürüm.

## Sınırlar (dürüst not)

Araç, gerçek sunucularda her yapılandırmada denenmiş bir ürün değildir. Önce test sunucusunda deneyin,
yedek/snapshot alın, `--check --diff` ile ne değişeceğine bakın (bkz. `README.md`, `HOWTO.md`).
