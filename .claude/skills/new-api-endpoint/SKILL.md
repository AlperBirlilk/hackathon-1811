---
name: new-api-endpoint
description: hackatlon-django'ya salt okunur, token korumalı bir REST API endpoint'i (DRF) ekler. Veri paylaşımı, MCP server veya dış sistem entegrasyonu için veri açılması gerektiğinde kullan.
---

# Salt okunur REST API endpoint'i

API, ekrandaki görünürlük kurallarının aynısını uygular ve DATA_ACCESS yetkisi ister.

1. **İlk kurulum** (yalnızca bir kez; `core/api.py` zaten varsa atla):
   - `requirements.txt` dosyasına `djangorestframework` ekle, kur.
   - `settings.py`: `INSTALLED_APPS += ['rest_framework', 'rest_framework.authtoken']`.
   - `REST_FRAMEWORK` ayarları:
     - `DEFAULT_AUTHENTICATION_CLASSES`: Token + Session
     - `DEFAULT_PERMISSION_CLASSES`: `IsAuthenticated`
     - Sayfalama: `PageNumberPagination`, `PAGE_SIZE: 50`
   - `migrate` (authtoken tablosu; migration koordinasyonu gerekmez, 3. parti migration).
   - `core/api.py` içinde ortak yetki sınıfı:
     ```python
     class HasDataAccess(BasePermission):
         def has_permission(self, request, view):
             return request.user.is_authenticated and request.user.has_portal_perm(PermissionType.DATA_ACCESS)
     ```
   - `config/urls.py`: `path('api/', include(router.urls))` (router `core/api.py` içinde).
2. **Serializer:** Alanları açıkça listele. `fields='__all__'` kullanılmaz; `password`, `ldap_dn`, `is_superuser` gibi alanlar asla dönmez. İlişkiler için `display_name` / `username` gibi basit alanlar kullanılır.
3. **ViewSet:** `ReadOnlyModelViewSet`, `permission_classes = [IsAuthenticated, HasDataAccess]`.
   - `get_queryset()` scope edilmiş olmalı: task için `visible_tasks(self.request.user)`, ekip için `team_members`.
   - `select_related` / `prefetch_related` kullanılır.
   - Filtreler query param ile (`status`, `severity`), `task_list` view'ındaki mantıkla aynı.
4. **Token:** Veri Paylaşımı sayfası (`data_sharing` view'ı ve template) kullanıcının token'ını (`Token.objects.get_or_create(user=...)`) ve endpoint listesini gösterir. Token yenileme POST ve CSRF ile yapılır.
5. **Test:** `APIClient` ile token'lı istek 200; DATA_ACCESS yetkisi olmayan kullanıcıya 403; başka kullanıcının görünmeyen task'ı listede yok.
6. **Doğrula:**
   ```bash
   curl -s -H "Authorization: Token <token>" http://127.0.0.1:8000/api/tasks/ | head
   ```
   Endpoint'i `mcp/CLAUDE.md` içindeki tool listesiyle eşleştir.
