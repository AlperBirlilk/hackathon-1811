---
name: task-change
description: Task'a yeni bir alan veya davranış ekler (son tarih, SLA, yedek sorumlu, bildirim, devir gibi). Geçmiş kaydını ve yetki kurallarını koruyarak services katmanından yapar. Task modeli, task formu veya task iş kuralı değişikliklerinde kullan.
---

# Task davranışı değiştirme

Task yazma işlemleri `core/services.py` dışında yapılmaz. Bu skill o katmanı genişletir.

1. **Model gerekiyor mu?** Gerekiyorsa önce **migration koordinasyonu** (root `CLAUDE.md`): ekibe haber ver → `git pull origin main` → `models.py` değişikliği → `makemigrations core` → migration'ı hemen commit ve push et. Admin'e (`core/admin.py`) alanı ekle.
2. **Service:**
   - `create_task(...)`: yeni parametreyi keyword-only olarak ekle (`*, ..., due_date=None`); varsayılanı mevcut çağrıları bozmasın (`seed.py`, `views.task_create`).
   - `update_task(task, *, user, **changes)`: yeni alan için mevcut dallarla aynı desende bir `if '<alan>' in changes and ... != ...` dalı yaz; `logs` listesine `(TaskHistory.<TİP>, 'Türkçe açıklama')` ekle.
   - Yeni history tipi gerekiyorsa `TaskHistory.ACTION_CHOICES` listesine ekle. Bu da bir migration demektir; 1. adımla birlikte yap.
   - Bildirim gerekiyorsa (atama vb.) aynı `transaction.atomic` bloğu içinde oluştur. İşlemi yapan kişiye kendi işlemi için bildirim gönderme.
3. **Form ve view:** `core/forms.py` → `TaskForm` alanı; `views.task_create` ve `views.task_detail` içinde `initial` sözlüğü ve `services` çağrısı.
4. **Template:** `task_form.html`, `task_detail.html`, `task_list.html`; gerekiyorsa `dashboard.html`.
5. **Seed:** `seed.py` → `TASKS` verisine yeni alanı ekle (demo için anlamlı değerlerle); idempotent kalsın.
6. **Doğrula:** `manage.py test core`, `makemigrations --check --dry-run`, `seed --reset`; ardından task detayındaki geçmişte yeni kaydın Türkçe göründüğünü kontrol et.
