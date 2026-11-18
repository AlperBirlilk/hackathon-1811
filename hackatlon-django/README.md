# CyberOps Portal (Django · Monolith · SQLite)

Siber güvenlik ekipleri için task & aktivite yönetim portalı.

## Kurulum

```powershell
myenv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed          # demo veriler (--reset ile task/etkinlikleri sıfırlar)
python manage.py runserver
```

http://127.0.0.1:8000

### Giriş (LDAP)
Kurumsal kullanıcı adı / parola ile giriş yapılır. LDAP **yalnızca kimlik doğrular**:
1. `uid=<kullanıcı>,ou=People,...` DN'i ile LDAPS bind (TLS sertifikası doğrulanır)
2. Ad, soyad, mail okunur → `user` tablosuna eklenir/güncellenir, `last_login` yazılır
3. Yetkiler LDAP gruplarından **değil**, `user_permission` tablosundan gelir (ilk girişte yetkisiz)

İlk yöneticiyi atamak için (kullanıcı önce bir kez giriş yapmalı):
```powershell
python manage.py grant_perm alper.birlik --all
python manage.py grant_perm ali.veli TASK_MANAGEMENT DATA_ACCESS
python manage.py grant_perm ali.veli DATA_ACCESS --revoke
```
Sonrasında yönetici, LDAP kullanıcılarını **Ekibim → Üye Ekle** ile ekibine alıp **Yetki** ekranından yetki verebilir.

Ayarlar (env): `LDAP_ENABLED`, `LDAP_URL`, `LDAP_USER_SEARCH_BASE`, `LDAP_TLS_VERIFY`, `LDAP_CA_CERT_FILE`,
`LDAP_TIMEOUT`, `LOCAL_AUTH_ENABLED` (yerel demo hesapları; DEBUG'da açık, prod'da kapalı).

### Yerel demo hesapları (LOCAL_AUTH_ENABLED=1) — parola: `Cyber2026!`

| Kullanıcı | Rol | Yetkiler |
|---|---|---|
| `yonetici` | SOC Manager (Yönetici) | Tümü |
| `mert` | SOC Analyst | Data Access |
| `alper` | Pentester | Task Management |
| `berkay` | Malware Analyst | Report & Analysis |
| `aykun` | Cloud Sec. Eng. | Activity Management |
| `admin` | Superuser | Tümü + /admin |

## Entity'ler (`core/models.py`)

| Tablo | Alanlar |
|---|---|
| `user` | AbstractUser + title, department, phone, location, bio, manager (ekip ilişkisi) |
| `permission_type` | id, code, permission_name, description |
| `user_permission` | user_id, permission_type_id, granted_by, granted_date |
| `user_skill` | id, user_id, skill_name, kind (yetenek/sertifika), create_date |
| `task` | id, task_status, task_severity, task_title, task_description, assignees (M2M), create/modified date/by |
| `task_history` | id, task_id, action_type (`created`, `status_change`, `description_change`, `assignment_change`, `severity_change`), action_description, action_by, action_date |
| `activity` | id, activity_name, activity_description, activity_date, location, create_date, created_by, attendees (M2M) |

Task değişiklikleri `core/services.py` üzerinden yapılır ve her değişiklik otomatik olarak `task_history`'ye yazılır.

## Ekranlar

- **Login**: brute-force koruması (5 hatalı deneme → 5 dk kilit)
- **Dashboard**: İşlerim (Bekleyen / Tamamlanan), Etkinliklerim, Ekibim (yönetici: açık-devam-biten sayıları), Report & Analysis, canlı aktivite logu
- **İşler**: filtreleme, oluşturma, düzenleme, durum değiştirme, history
- **Etkinlikler**: listeleme, katıl/ayrıl, oluşturma (Activity Management)
- **Veri Paylaşımı**: Data Access yetkisi
- **Ekibim** (Role Management): üye ekle/çıkar, yetki yönetimi, üye profili
- **Profilim**: ana bilgiler, iletişim, yetenek/sertifika, güncelle

## Güvenlik notları

- CSRF, HttpOnly/SameSite cookie, X-Frame-Options DENY, nosniff, referrer policy
- Sunucu tarafında yetki kontrolü (`portal_perm_required`), IDOR korumalı sorgular
- Yönetici sahip olmadığı yetkiyi başkasına veremez (privilege escalation koruması)
- `next` parametresinde open-redirect kontrolü
- Prod: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS` env değişkenleri
- LDAP: boş parola (anonymous bind) engellenir, kullanıcı adı whitelist + DN/filter escape (LDAP injection),
  yerel hesaplar LDAP ile eşleştirilmez (hesap ele geçirme koruması), pasif kullanıcı giriş yapamaz
- Testler: `python manage.py test core`

## E-posta bildirimleri

`mailTemplate.msg` şablonu `templates/emails/notification.html` olarak alındı. Şu durumlarda mail gider:

- **Task ataması:** task oluşturulurken veya düzenlenirken (toplu işlem dahil) *yeni eklenen* atananlara
- **Etkinlik daveti:** etkinlik oluşturulurken seçilen katılımcılara

İşlemi yapan kişiye mail gitmez. Alıcı adresi LDAP girişinde `user.email` alanına yazılan adrestir.
Mailler DB işlemi tamamlandıktan sonra arka planda gönderilir; SMTP hatası ekranı etkilemez, loglanır.

| Ayar (env) | Varsayılan | Açıklama |
|---|---|---|
| `MAIL_FROM` | `TEAM-SMA@smtp.turkcell.com.tr` | Gönderen |
| `MAIL_HOST` / `MAIL_PORT` | `smtp.turkcell.com.tr` / `25` | SMTP (auth/TLS yok, saportal-be ile aynı) |
| `MAIL_ALLOWED_DOMAINS` | `turkcell.com.tr` | Yalnızca bu domainlere gönderilir |
| `MAIL_TEST_RECIPIENT` | boş | Doluysa tüm mailler bu adrese yönlendirilir |
| `MAIL_ENABLED` | `1` | `0` ile tamamen kapatılır |
| `PORTAL_BASE_URL` | `http://127.0.0.1:8000` | Maildeki linklerin adresi |

Deneme maili: `python manage.py send_test_mail <kullanıcı> [--activity]`
