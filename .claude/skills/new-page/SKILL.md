---
name: new-page
description: hackatlon-django portalına yeni bir ekran (view + URL + template + menü + test) ekler. Yeni liste, form, detay, rapor veya bildirim sayfası istendiğinde kullan.
---

# Yeni sayfa ekleme

Argüman: sayfanın amacı ve gereken yetki (ör. "bildirimler sayfası, giriş yapmış herkes").

1. **Plan:** URL adı (`snake_case`), path, yetki (`PermissionType.X` ya da yalnızca login), template adı. Benzer bir mevcut sayfayı bul ve onu şablon al (liste için `task_list`, form için `activity_create`, ekip için `team`).
2. **View** (`core/views.py`, ilgili bölüm başlığının altına):
   - Yetki dekoratörü: `@portal_perm_required(PermissionType.X)` ya da `@login_required`.
   - Sorgu scope edilir: `visible_tasks(request.user)` veya `user=request.user`. Liste sorgularında `select_related` / `prefetch_related`.
   - POST işleyen view'da `@require_POST` (ayrı action view'ı için) ya da `request.method == 'POST'` + form validasyonu → `messages.success` → `redirect`.
3. **URL:** `core/urls.py` içinde ilgili grubun yanına `path('...', views.x, name='x')`.
4. **Template:** `templates/core/<ad>.html`:
   ```django
   {% extends "app.html" %}
   {% block heading %}Başlık{% endblock %}
   {% block content %} ... {% endblock %}
   ```
   Form alanları `{% include "_field.html" with field=form.x %}`; POST formunda `{% csrf_token %}`. Kart, tablo ve rozet için `portal.css` içindeki mevcut sınıflar kullanılır (önce `dashboard.html` / `task_list.html` incelenir).
5. **Menü** (gerekiyorsa): `templates/app.html` sidebar'ına, mevcut linklerle aynı yapıda (`svg.i` ikon + `active` sınıfı) ekle; `{% if perm.<x> %}` ile koşulla.
6. **Test:** `core/tests.py` → `PageRenderTests` içinde yetkili kullanıcı için 200, yetkisiz kullanıcı için 403 kontrolü (`test_manager_pages` / `test_member_pages` listelerine ekle).
7. **Doğrula:** `.venv/bin/python manage.py test core`; `runserver` açıksa sayfayı açık ve koyu temada kontrol et.
