# Siber Güvenlik İş Yönetimi — Hackathon MVP Planı

## Amaç

Siber güvenlik ekibinin günlük işlerini, ana ve yedek sorumlularını, etkinlik katılımlarını ve yetkinliklerini tek uygulamada takip etmek. Hedef, hackathon sonunda temel akışı çalışan ve kolayca gösterilebilen bir demo hazırlamak.

## Teknoloji

- Backend: Django + Django REST Framework
- Frontend: React + Vite ve hazır bir arayüz bileşen kütüphanesi
- Veritabanı: Takım kararı olan DuckDB
- Giriş: Turkcell LDAP test entegrasyonu — Alper
- Veri paylaşımı: REST API; MCP sonraki aşama için TODO

İlk teknik adımda DuckDB ile Django kullanıcı kaydı, veri okuma/yazma ve migration uyumu denenmeli. Django'nun yerleşik DuckDB desteği olmadığı için entegrasyon MVP'yi geciktirirse ekip kararıyla SQLite kullanılabilir.

## MVP Kapsamı

| Alan | Minimum özellik |
|---|---|
| Giriş | LDAP ile doğrulama, kullanıcı ve takım bilgilerinin alınması |
| İş yönetimi | İş oluşturma, ana/yedek sorumlu atama, durum ve öncelik güncelleme, son tarih |
| Etkinlikler | Eğitim veya konferans kaydı, bireysel/kurumsal katılım, katılımcılar ve iletişim kişisi |
| Profil | Temel bilgiler, yetkinlik ve sertifika ekleme/güncelleme |
| Ekibim | Takım üyeleri, iş sayıları ve uygulama rolleri |
| Dashboard | Bekleyen, devam eden, tamamlanan ve geciken iş sayıları; yaklaşan etkinlikler |
| Raporlama | İşleri kişi ve duruma göre filtreleme, Excel ve basit PDF çıktısı |
| Bildirim | İş atandığında uygulama içinde bildirim gösterme |
| Veri paylaşımı | Kullanıcının yetkisiyle sınırlı REST API erişimi |

İş durumları: **Bekliyor → Devam ediyor → Tamamlandı**.

Öncelikler: **Düşük / Orta / Yüksek / Kritik**.

İşler basit bir tablo ve oluşturma/düzenleme formuyla yönetilecek. Dashboard yalnızca özet ve ilgili ekranlara bağlantı içerecek.

## Roller

| Rol | Yetki |
|---|---|
| Çalışan | Kendi ana/yedek işlerini görür, durum günceller; kendi yetkinliklerini ve etkinlik katılımını yönetir |
| Yönetici | Kendi takımının işlerini oluşturur, atar ve raporlar |
| Direktör | Tüm takımları ve raporları görür; uygulama rollerini atar |

Takım hiyerarşisi LDAP'tan gelir. Uygulama rolü kullanıcı üzerinde ayrı tutulur. Yetkiler backend'de kontrol edilir; API ve dışa aktarımlar aynı kurallara uyar.

## Basit Veri Modeli

| Tablo | Temel alanlar |
|---|---|
| User | LDAP kimliği, ad, e-posta, takım, yönetici, rol |
| Task | Başlık, açıklama, durum, öncelik, ana sorumlu, yedek sorumlu, son tarih, oluşturan |
| TaskHistory | İş, işlemi yapan, değişiklik, tarih |
| Activity | Ad, tür, tarih, organizasyon, iletişim kişisi |
| ActivityParticipant | Etkinlik, kullanıcı, katılım durumu |
| UserSkill | Kullanıcı, yetkinlik/sertifika adı, seviye |
| Notification | Kullanıcı, ilgili iş, mesaj, okunma durumu |

Üç sabit rol için ayrı bir izin yönetim sistemi kurulmayacak. Her işte bir ana ve isteğe bağlı bir yedek sorumlu olacak.

## Geliştirme Sırası

1. **Temeli kur:** Django/React projeleri, DB uyum denemesi, veri modeli ve örnek kayıtlar.
2. **Ana akışı çalıştır:** LDAP giriş, rol kontrolü, iş oluşturma/atama ve durum güncelleme.
3. **Özetleri ekle:** Dashboard, takım listesi, iş geçmişi ve uygulama içi bildirim.
4. **Diğer minimum gereksinimleri tamamla:** Etkinlikler, yetkinlikler, filtreli rapor ve Excel/PDF çıktısı.
5. **Demoyu doğrula:** Üç rolle giriş, takım dışı veriye erişim kontrolü ve uçtan uca iş akışı.

LDAP entegrasyonu sürerken diğer ekranlar yerel geliştirme ortamında örnek kullanıcı verileriyle hazırlanabilir.

## Örnek İş Bölümü

- **Alper:** LDAP, kullanıcı/takım aktarımı ve giriş akışı.
- **Backend geliştirici:** İş API'si, yetkilendirme, geçmiş ve bildirim.
- **Frontend geliştirici:** Dashboard, iş listesi/formu ve takım ekranı.
- **Diğer geliştirici:** Etkinlik/yetkinlik akışları ve Excel/PDF çıktısı.
- **Tüm ekip:** Entegrasyon ve demo kontrolü.

## Demo Senaryosu

1. Yönetici, “Kritik zafiyetin giderilmesini takip et” işini açar ve ana/yedek sorumlu atar.
2. Çalışan bildirimi görür, işi başlatır ve tamamlar.
3. Yönetici dashboard ve iş geçmişinde güncel durumu gösterir.
4. Bir güvenlik eğitimi, katılımcıları ve bir kullanıcı yetkinliği eklenir.
5. Direktör filtreli iş raporunu Excel/PDF olarak alır; verinin REST API üzerinden okunabildiği gösterilir.

## Kapsam Dışı

Teams/e-posta entegrasyonu, MCP implementasyonu, otomatik tekrarlanan işler, sürükle-bırak pano, gelişmiş grafikler ve onay akışları bu MVP'ye dahil değildir.

## Tamamlanma Kriteri

Yukarıdaki demo akışı gerçek kayıtlarla çalışır; rol ve takım sınırları uygulanır; Excel/PDF çıktısı alınır ve yetkili API erişimi gösterilir.
