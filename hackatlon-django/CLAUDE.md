# hackatlon-django — Django uygulaması

Komutlar bu dizinden çalıştırılır:
- macOS/Linux: `.venv/bin/python manage.py <cmd>`
- Windows: `myenv\Scripts\python.exe manage.py <cmd>` (Git Bash: `myenv/Scripts/python.exe`)

## Yapı
| Dosya | Sorumluluk |
|---|---|
| `config/settings.py` | Ayarlar; env değişkenleri: `DJANGO_*`, `LDAP_*`, `LOCAL_AUTH_ENABLED`, `MAIL_*`, `PORTAL_BASE_URL`, `API_TOKEN_TTL_HOURS` |
| `core/models.py` | `User` (AbstractUser + `manager` self-FK, `auth_source`, `is_on_leave`), `PermissionType`, `UserPermission`, `UserSkill`, `Task` (`assignees` M2M, `backup_assignee`, `due_date`, `is_overdue`), `TaskHistory`, `Activity` (`attendees` M2M, tür, katılım, iletişim kişisi), `Notification` |
| `core/services.py` | **Task yazma işlemlerinin tek kapısı:** `create_task(...)`, `update_task(task, user=..., **changes)`; `TaskHistory` kaydını otomatik yazar, bildirimleri tetikler |
| `core/notifications.py` | **Bildirimlerin tek kapısı:** uygulama içi `Notification` + e-posta (`templates/emails/notification.html`). SMTP arka planda, `transaction.on_commit` sonrası |
| `core/views.py` | Function-based view'lar ve yardımcılar (aşağıda) |
| `core/api/` | Salt okunur DRF API (`/api/...`), Bearer token, DATA_ACCESS; MCP bunu kullanır |
| `core/forms.py` | `TaskForm` (plain Form, önem `RadioSelect`), `ActivityForm`, `ProfileForm`, `SkillForm` |
| `core/urls.py` | Tüm URL'ler; isimli route'lar (`task_list`, `team` vb.) |
| `core/ldap_backend.py` | LDAP kimlik doğrulama (ldap3). Yetkiler LDAP'tan değil, DB'den gelir |
| `core/context_processors.py` | Template'lere `perm.task/activity/role/report/data` bayraklarını verir |
| `core/management/commands/` | `seed` (demo verisi), `grant_perm`, `send_test_mail` |
| `core/tests.py`, `core/test_*.py` | LDAP, `PageRenderTests`, kanban/AJAX, toplu işlem, mail, API testleri |
| `templates/` | `base.html` → `app.html` (sidebar + topbar) → `core/*.html`; partial'lar: `_field.html`, `_severity_picker.html`, `_distribution_panel.html`, `_theme_toggle.html` |
| `static/css/portal.css`, `static/js/portal.js` | Tasarım sistemi, açık/koyu tema, kanban sürükle-bırak, AJAX task oluşturma, toplu işlem, toast |

## Yeniden kullan, yenisini yazma
- **Yetki:**
  - `user.has_portal_perm(PermissionType.X)`, `user.is_manager` (ROLE_MANAGEMENT), `user.is_director` (tüm yetkiler)
  - view dekoratörü `@portal_perm_required(PermissionType.X)`: login + 403
  - template'te `{% if perm.role %}`
- **Task görünürlüğü:**
  - `visible_tasks(user)`: TASK_MANAGEMENT yetkisi varsa tüm task'lar, yoksa ana/yedek sorumlusu olduğu veya oluşturduğu task'lar
  - `can_edit_task(user, task)`, `can_change_status(user, task)` (düzenleyen, ana veya yedek sorumlu)
- **JSON/AJAX:** `wants_json(request)` (`X-Requested-With: XMLHttpRequest`), `task_json(task)`. Kanban `POST /tasks/<id>/status/` ve AJAX `task_create` bunu kullanır.
- **Yönlendirme:** `safe_next(request, fallback)` (open redirect korumalı).
- **Toplu işlem:** `task_bulk` (`op=status:X | severity:X | assign | unassign`), her değişiklik `update_task` üzerinden.
- **Ekip:** `team_with_stats(manager)` (open/progress/done sayıları), `user.team_members`.
- **Sıralama:** `SEVERITY_RANK` (Kritik önce).
- **Durum ve önem sabitleri:** `Task.STATUS_*`, `Task.SEVERITY_*`, `Task.PENDING_STATUSES`; Türkçe etiketler `get_*_display()` ile alınır.

## Desenler
- **Yeni sayfa:** view → `core/urls.py` → `templates/core/<ad>.html` (`{% extends "app.html" %}`, `heading`/`content` blokları) → gerekirse `app.html` sidebar linki (`perm.*` koşuluyla) → `PageRenderTests`'e URL ve beklenen durum kodu. Ayrıntı için `/new-page` skill'i.
- **Yazma işlemleri:** `@require_POST`, `messages.success(...)`, ardından `redirect(...)` (PRG deseni). AJAX istekte aynı view JSON döner.
- **Nesne erişimi:** `get_object_or_404(<scoped queryset>, pk=pk)`. Örnek: `get_object_or_404(visible_tasks(request.user), pk=pk)`. Scope edilmemiş `Model.objects.get(pk=...)` kullanılmaz.
- **Task değişiklikleri:** Her zaman `services` üzerinden. Yeni bir alan geçmişe yazılacaksa `update_task` içine bir dal ve `TaskHistory` action tipi eklenir.
- **Bildirim:** Doğrudan `send_mail` / `Notification.objects.create` yerine `core/notifications.py` fonksiyonları kullanılır.

## Testler
- `manage.py test core` her PR öncesi yeşil olmalı.
- Yeni sayfa ve yetki kuralı için `PageRenderTests` güncellenir: yetkili kullanıcı 200, yetkisiz kullanıcı 403.
