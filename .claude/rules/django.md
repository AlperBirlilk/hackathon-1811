---
paths:
  - "hackatlon-django/**/*.py"
---

# Django kuralları

- Task oluşturma ve güncelleme **yalnızca** `core/services.py` üzerinden yapılır. View içinde `task.save()`, `task.assignees.set()` ya da `Task.objects.create()` kullanılmaz.
- Task sorguları `visible_tasks(user)` ile başlar. Tekil nesne `get_object_or_404(<scoped qs>, pk=pk)` ile alınır.
- Yetki isteyen her view `@portal_perm_required(PermissionType.X)` ya da `@login_required` + açık bir kontrol kullanır. Kontrol template'te değil, sunucu tarafında yapılır.
- Durum değiştiren view'lar `@require_POST` ile korunur ve PRG deseni izlenir: `messages` + `redirect`.
- Liste sorgularında `select_related` / `prefetch_related` kullanılır (N+1 yok).
- Raw SQL (`.raw()`, `cursor.execute`) ve SQLite'a özgü fonksiyonlar yok; ileride DuckDB'ye geçişi zorlaştırmamak için ORM kullanılır.
- Model değişikliği: önce ekibe haber ver → `git pull` → `makemigrations` → migration dosyasını hemen commit ve push et. Mevcut migration dosyaları düzenlenmez.
- `seed.py` idempotent kalır (`get_or_create` / `update_or_create`).
- Yeni sayfa veya yetki kuralı eklendiğinde `core/tests.py` → `PageRenderTests` güncellenir.
