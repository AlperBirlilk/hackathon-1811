---
name: new-backend-endpoint
description: hackatlon-be'ye yeni bir REST endpoint'i ekler (Controller/Service/Repository, record DTO, gerekirse eklemeli schema.sql değişikliği, MockMvc testi, dev token ile curl). Java API'ye yeni veri veya işlem açılması gerektiğinde kullan.
---

# Yeni Java endpoint'i

Argüman: `docs/api-contract.md` içindeki endpoint (ör. `GET /api/notifications`). Sözleşmede yoksa önce oraya yazılır.

1. **Paket:** İlgili domain paketi (`task/`, `activity/`, `user/`, `report/`). Aynı paketteki mevcut sınıfları şablon al.
2. **DTO:** İstek/yanıt için `record` (ör. `NotificationDto(long id, String message, boolean read, OffsetDateTime createdAt)`). Alanlar sözleşmeyle birebir; parola/secret alanı yok. İstekte Bean Validation (`@NotBlank`, `@Size`).
3. **Repository:** `JdbcTemplate` / `NamedParameterJdbcTemplate`, parametreli SQL, `RowMapper` ile record'a eşleme. Görünürlük filtresi SQL'de parametre olarak (ör. `WHERE user_id = ?`). Dinamik sıralama kolonu izin listesinden.
4. **Service:**
   - `CurrentUser` parametresiyle; yetki (`hasPerm(...)`) ve scope burada. Yetki yok → 403, görünmüyor → 404 (`common/` exception'ları).
   - Yazma işlemi `@Transactional`; task yazıyorsa `task_history` aynı metodda, atama varsa `notification`.
5. **Controller:** `@RestController`, path sözleşmedeki gibi. `CurrentUser`'ı `CurrentUserService`'ten al, Service'i çağır, DTO dön. İş kuralı ve SQL yok. `/internal/**` ise service key filtresinin kapsamında olduğunu kontrol et.
6. **Şema (gerekiyorsa):** `schema.sql` sonuna eklemeli değişiklik: `CREATE TABLE IF NOT EXISTS ...` veya `ALTER TABLE task ADD COLUMN IF NOT EXISTS due_date DATE;`. Mevcut ifadeleri düzenleme. Demo verisi `data.sql`'e `INSERT OR IGNORE` ile. Ekibe duyur.
7. **Test (MockMvc):** yetkili kullanıcı 200 + JSON alanları; token yok 401; yetkisiz kullanıcı 403 veya başkasının kaydı 404. `./mvnw test` yeşil olmalı.
8. **Curl:**
   ```bash
   TOKEN=$(curl -s -H "X-Service-Key: $PORTAL_SERVICE_KEY" "http://127.0.0.1:8080/internal/dev/token?username=yonetici")
   curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/<path>
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/api/<path>   # 401
   ```
   Yanıtı sözleşmedeki örnekle karşılaştır.
