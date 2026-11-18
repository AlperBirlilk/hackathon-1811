---
paths:
  - "hackatlon-django/**/*.py"
---

# Django kuralları (frontend / BFF)

- **Domain için ORM yok.** Task, etkinlik, ekip, yetki, yetkinlik ve bildirim verisi yalnızca `core/api_client.py` üzerinden okunur ve yazılır. `Task.objects`, `core/services.py` ve diğer domain modelleri yeni kodda kullanılmaz; kullanımdan kalkıyorlar.
- View içinde `requests` / `httpx` doğrudan çağrılmaz; yeni endpoint için `api_client`'a sözleşmeyle (`docs/api-contract.md`) birebir bir fonksiyon eklenir.
- API hataları view'da yakalanır ve kullanıcıya `messages.error(request, e.message)` ile Türkçe gösterilir. 404 → `Http404`, 403 → `PermissionDenied`, 401 → login'e yönlendirme (`api_client` yapar).
- Yetki isteyen her view `@portal_perm_required(<kod>)` ya da `@login_required` kullanır. Asıl yetki kontrolü Java'dadır, ama Django da sayfayı yetkisize açmaz.
- Durum değiştiren view'lar `@require_POST` ile korunur ve PRG deseni izlenir: `messages` + `redirect`.
- JWT session'da kalır; template context'ine, JS'e veya log'a konmaz.
- Migration'lar yalnızca auth/session içindir; domain modeli eklenmez veya değiştirilmez.
- Yeni sayfa veya yetki kuralı eklendiğinde `core/tests.py` güncellenir; `api_client` mock'lanır.
