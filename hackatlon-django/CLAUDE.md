# hackatlon-django — Django uygulaması

Komutlar bu dizinden çalıştırılır: `.venv/bin/python manage.py <cmd>`.

## Yapı
| Dosya | Sorumluluk |
|---|---|
| `config/settings.py` | Ayarlar; env değişkenleri: `DJANGO_*`, `LDAP_*`, `LOCAL_AUTH_ENABLED` |
| `core/models.py` | `User` (AbstractUser + `manager` self-FK, `auth_source`), `PermissionType`, `UserPermission`, `UserSkill`, `Task` (`assignees` M2M), `TaskHistory`, `Activity` (`attendees` M2M) |
| `core/services.py` | **Task yazma işlemlerinin tek kapısı:** `create_task(...)`, `update_task(task, user=..., **changes)`; `TaskHistory` kaydını otomatik yazar |
| `core/views.py` | Function-based view'lar ve yardımcılar (aşağıda) |
| `core/forms.py` | `TaskForm` (plain Form), `ActivityForm`, `ProfileForm`, `SkillForm` |
| `core/urls.py` | Tüm URL'ler; isimli route'lar (`task_list`, `team` vb.) |
| `core/ldap_backend.py` | LDAP kimlik doğrulama (ldap3). Yetkiler LDAP'tan değil, DB'den gelir |
| `core/context_processors.py` | Template'lere `perm.task/activity/role/report/data` bayraklarını verir |
| `core/management/commands/` | `seed` (demo verisi), `grant_perm` |
| `core/tests.py` | LDAP testleri + `PageRenderTests` (seed verisiyle sayfa ve rol kontrolü) |
| `templates/` | `base.html` → `app.html` (sidebar + topbar) → `core/*.html`; `_field.html` form alanı partial'ı |
| `static/css/portal.css`, `static/js/portal.js` | Tasarım sistemi, açık/koyu tema |

## Yeniden kullan, yenisini yazma
- **Yetki:**
  - `user.has_portal_perm(PermissionType.X)`, `user.is_manager` (ROLE_MANAGEMENT yetkisi)
  - view dekoratörü `@portal_perm_required(PermissionType.X)`: login + 403
  - template'te `{% if perm.role %}`
- **Task görünürlüğü:**
  - `visible_tasks(user)`: TASK_MANAGEMENT yetkisi varsa tüm task'lar, yoksa atanan veya oluşturduğu task'lar
  - `can_edit_task(user, task)`
- **Ekip:** `team_with_stats(manager)` (open/progress/done sayıları), `user.team_members`.
- **Sıralama:** `SEVERITY_RANK` (Kritik önce).
- **Durum ve önem sabitleri:** `Task.STATUS_*`, `Task.SEVERITY_*`, `Task.PENDING_STATUSES`; Türkçe etiketler `get_*_display()` ile alınır.

## Desenler
- **Yeni sayfa:** view → `core/urls.py` → `templates/core/<ad>.html` (`{% extends "app.html" %}`, `heading`/`content` blokları) → gerekirse `app.html` sidebar linki (`perm.*` koşuluyla) → `PageRenderTests`'e URL ve beklenen durum kodu. Ayrıntı için `/new-page` skill'i.
- **Yazma işlemleri:** `@require_POST`, `messages.success(...)`, ardından `redirect(...)` (PRG deseni).
- **Nesne erişimi:** `get_object_or_404(<scoped queryset>, pk=pk)`. Örnek: `get_object_or_404(visible_tasks(request.user), pk=pk)`. Scope edilmemiş `Model.objects.get(pk=...)` kullanılmaz.
- **Task değişiklikleri:** Her zaman `services` üzerinden. Yeni bir alan geçmişe yazılacaksa `update_task` içine bir dal ve `TaskHistory` action tipi eklenir.

## Testler
- `manage.py test core` her PR öncesi yeşil olmalı.
- Yeni sayfa ve yetki kuralı için `PageRenderTests` güncellenir: yetkili kullanıcı 200, yetkisiz kullanıcı 403.
