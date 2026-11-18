---
name: new-page
description: hackatlon-django portalına yeni bir ekran (api_client fonksiyonu + view + URL + template + menü + test) ekler. Veri Java API'den gelir, ORM kullanılmaz. Yeni liste, form, detay, rapor veya bildirim sayfası istendiğinde kullan.
---

# Yeni sayfa ekleme

Argüman: sayfanın amacı ve gereken yetki (ör. "bildirimler sayfası, giriş yapmış herkes").

1. **Plan:** URL adı (`snake_case`), path, yetki kodu (ya da yalnızca login), template adı ve kullanılacak Java endpoint'i (`docs/api-contract.md`). Endpoint yoksa önce sözleşmeye yazılır ve `/new-backend-endpoint` ile eklenir (ya da `/fullstack-feature` akışı). Benzer bir mevcut sayfayı şablon al (liste için `task_list`, form için `activity_create`, ekip için `team`).
2. **`api_client`:** `core/api_client.py` içine sözleşmeyle birebir bir fonksiyon (ör. `list_notifications(request)`, `mark_notification_read(request, pk)`). JWT ekleme, hata çevirme ve 401 yönlendirmesi ortak yardımcıdan gelir; tekrar yazılmaz.
3. **View** (`core/views.py`, ilgili bölüm başlığının altına):
   - Yetki dekoratörü: `@portal_perm_required(<kod>)` ya da `@login_required`.
   - Veri yalnızca `api_client` ile; **ORM yok**. Scope Java'da uygulanır.
   - `api_client.ApiError` yakalanır → `messages.error(request, e.message)`; 404 → `Http404`, 403 → `PermissionDenied`.
   - POST: `@require_POST` (ayrı action view'ı) ya da `request.method == 'POST'` + form validasyonu → `api_client` → `messages.success` → `redirect`.
4. **URL:** `core/urls.py` içinde ilgili grubun yanına `path('...', views.x, name='x')`.
5. **Template:** `templates/core/<ad>.html`:
   ```django
   {% extends "app.html" %}
   {% block heading %}Başlık{% endblock %}
   {% block content %} ... {% endblock %}
   ```
   Anahtarlar API yanıtındaki alan adlarıyla aynı. Form alanları `{% include "_field.html" with field=form.x %}`; POST formunda `{% csrf_token %}`. Kart, tablo ve rozet için `portal.css` içindeki mevcut sınıflar (önce `dashboard.html` / `task_list.html` incelenir).
6. **Menü** (gerekiyorsa): `templates/app.html` sidebar'ına, mevcut linklerle aynı yapıda (`svg.i` ikon + `active` sınıfı) ekle; `{% if perm.<x> %}` ile koşulla.
7. **Test:** `core/tests.py` içinde `api_client` fonksiyonunu mock'la; yetkili kullanıcı 200, yetkisiz 403, API hatasında mesaj gösterimi.
8. **Doğrula:** `.venv/bin/python manage.py test core`; iki sunucu açıksa sayfayı açık ve koyu temada kontrol et.
