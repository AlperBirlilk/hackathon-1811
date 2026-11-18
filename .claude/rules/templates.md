---
paths:
  - "hackatlon-django/templates/**"
  - "hackatlon-django/static/**"
---

# Template ve stil kuralları

- Sayfalar `{% extends "app.html" %}` ile başlar ve `heading`, `subheading`, `content` bloklarını doldurur. Login gibi oturum dışı sayfalar `base.html`'i extend eder.
- Form alanları için `{% include "_field.html" %}` partial'ı kullanılır.
- Her POST formunda `{% csrf_token %}` bulunur. Durum değiştiren işlemler GET linkiyle yapılmaz.
- Stil için `static/css/portal.css` içindeki mevcut sınıflar ve CSS değişkenleri kullanılır. Açık ve koyu tema ikisi birden çalışmalı, renkler sabit hex değil tema değişkeni olmalı. Inline `style` sadece küçük layout düzeltmeleri için kullanılır.
- Menü öğeleri `app.html` sidebar'ına eklenir ve `{% if perm.<x> %}` ile koşullanır. Gizlemek yetki değildir; view tarafında da kontrol şarttır.
- Kullanıcıya görünen tüm metinler Türkçe.
- Görsel tasarım için `frontend-design` skill'i kullanılır, ama mevcut portal tasarım dili (sidebar, kartlar, rozetler) korunur; yeni bir tasarım dili açılmaz.
- `|safe` ve `{% autoescape off %}` kullanılmaz.
