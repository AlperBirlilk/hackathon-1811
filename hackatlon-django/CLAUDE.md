# hackatlon-django — Frontend / BFF

Django artık **frontend / BFF**: LDAP login, JWT üretimi ve server-rendered template'ler. **Domain verisinin sahibi Java backend'dir** (`hackatlon-be`); Django domain verisine yalnızca `core/api_client.py` üzerinden erişir. Endpoint sözleşmesi: `../docs/api-contract.md`.

Komutlar bu dizinden çalıştırılır: `.venv/bin/python manage.py <cmd>`. Java (`:8080`) önce ayakta olmalı; env: `PORTAL_API_URL`, `PORTAL_JWT_SECRET`, `PORTAL_SERVICE_KEY`.

## Kimlik akışı
1. `/login/`: `core/ldap_backend.py` (LDAP) veya yerel demo hesabı doğrular.
2. `POST /internal/users/sync` (`X-Service-Key`) → Java kullanıcının id'sini ve yetkilerini döner.
3. Django HS256 JWT üretir (`sub`, `username`, `perms`, `exp`=8 saat) ve **session'da** saklar. JWT template'e, JS'e veya cookie'ye ham olarak konmaz (Veri Paylaşımı sayfasındaki uzun ömürlü token hariç; o da yalnızca sahibine gösterilir).

## Yapı
| Dosya | Sorumluluk |
|---|---|
| `config/settings.py` | Ayarlar; env: `DJANGO_*`, `LDAP_*`, `LOCAL_AUTH_ENABLED`, `PORTAL_*` |
| `core/api_client.py` | **Java API'ye tek HTTP kapısı:** session'daki JWT'yi `Authorization: Bearer` olarak ekler, API hatalarını (`{"error": {...}}`) Türkçe mesajlı exception'a çevirir, 401'de login'e yönlendirir |
| `core/views.py` | Function-based view'lar: view → `api_client` → template |
| `core/forms.py` | `TaskForm`, `ActivityForm`, `ProfileForm`, `SkillForm` (plain Form; yalnızca validasyon) |
| `core/urls.py` | Tüm URL'ler; isimli route'lar (`task_list`, `team` vb.) |
| `core/ldap_backend.py` | LDAP kimlik doğrulama (ldap3). Korumaları kaldırılmaz |
| `core/context_processors.py` | Template'lere `perm.task/activity/role/report/data` bayrakları |
| `core/models.py`, `core/services.py` | **Kullanımdan kalkıyor.** Domain modelleri (`Task`, `Activity` vb.) ve `services` geçiş bitince silinir; yeni kod bunlara bağlanmaz |
| `templates/`, `static/` | `base.html` → `app.html` → `core/*.html`; `portal.css`, `portal.js` (açık/koyu tema) |

## Desen: view → `api_client` → template
```python
@portal_perm_required('TASK_MANAGEMENT')
def task_list(request):
    try:
        tasks = api_client.list_tasks(request, status=request.GET.get('status'))
    except api_client.ApiError as e:
        messages.error(request, e.message)
        tasks = []
    return render(request, 'core/task_list.html', {'tasks': tasks})
```
- Yeni endpoint çağrısı = `api_client`'a bir fonksiyon (sözleşmedeki path ve JSON'la birebir). View içinde `requests`/`httpx` doğrudan kullanılmaz.
- **Yeni domain ORM kodu yazılmaz.** Görünürlük ve yetki kuralları Java'da; Django bunları tekrar uygulamaz, yalnızca menü/erişim için bayrak kontrol eder.
- **Yazma işlemleri:** `@require_POST`, `api_client` çağrısı, `messages.success(...)` / hata için `messages.error(e.message)`, ardından `redirect(...)` (PRG).
- Nesne bulunamadı / görünmüyor (API 404) → `Http404`; API 403 → `PermissionDenied`.

## Yeniden kullan
- **Yetki dekoratörü** `@portal_perm_required(<kod>)`: login + 403. **Hedef durum:** yetkileri ORM'den değil, session'daki kullanıcı bilgisinden (`/api/me` yanıtı) okur. Geçiş sürerken mevcut ORM tabanlı sürüm kalabilir; yeni kod bu davranışa bağımlı olmaz.
- **Template bayrakları:** `{% if perm.role %}` vb. (context processor, aynı kaynaktan).
- **Etiketler:** Durum/önem Türkçe etiketleri API yanıtındaki değerlerden üretilir; sözleşmedeki kodlarla eşleşen tek bir sözlükte tutulur.

## Template ve tasarım (değişmedi)
- `{% extends "app.html" %}`, `heading` / `subheading` / `content` blokları; form alanları `{% include "_field.html" %}`; her POST formunda `{% csrf_token %}`.
- `portal.css` sınıfları ve tema değişkenleri; yeni tasarım dili açılmaz. Görsel kararlar için `frontend-design` skill'i.
- Tüm metinler Türkçe; `|safe` yok. Ayrıntı: `.claude/rules/templates.md`.

## Testler
- `manage.py test core` her PR öncesi yeşil olmalı.
- View testlerinde `api_client` fonksiyonları mock'lanır (Java'ya gerçek istek yok). Yetkili kullanıcı 200, yetkisiz 403; API hatasında mesaj gösterimi.
- Migration'lar yalnızca auth/session içindir.
