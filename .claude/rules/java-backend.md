---
paths:
  - "hackatlon-be/**"
---

# Java backend kuralları

- **SQL:** Yalnızca `JdbcTemplate` / `NamedParameterJdbcTemplate` ile parametreli sorgu (`?` veya `:name`). Kullanıcı girdisi SQL string'ine birleştirilmez. Dinamik sıralama/filtre kolonları sabit bir izin listesinden seçilir. JPA yok.
- **Kimlik:** Her Controller endpoint'i kimlik doğrulama ister. `/api/**` JWT ile, `/internal/**` yalnızca `X-Service-Key` ile. `permitAll` yalnızca sağlık kontrolü ve `/v3/api-docs` için.
- **Scope:** Yetki ve görünürlük kontrolü **Service katmanında**, `CurrentUser` üzerinden yapılır; Controller'da veya yalnızca sorgu parametresinde değil. ID ile erişimde görünmeyen kayıt için 404.
- **Geçmiş:** Task'ın her yazma işleminde `task_history` kaydı aynı `@Transactional` metod içinde yazılır. Atama bildirimi de aynı transaction'da.
- **DTO:** İstek ve yanıtlar Java `record`. Tüm kolonların ham `Map`'i ya da `queryForList` sonucu doğrudan dönülmez.
- **Sızıntı:** Yanıtlarda parola, hash, secret, token veya `ldap_dn` gibi alanlar bulunmaz.
- **Hata:** Exception'lar `@RestControllerAdvice` ile `{"error": {"code", "message"}}` formatına çevrilir; stack trace ve SQL mesajı istemciye dönmez. `message` Türkçe.
- **Şema:** `schema.sql` yalnızca eklemeli değişir (`CREATE TABLE IF NOT EXISTS`, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`); mevcut ifadeler yıkıcı biçimde düzenlenmez. `data.sql` idempotent (`INSERT OR IGNORE`).
- **Test:** Yeni endpoint = MockMvc testi (200 / 401 / 403-404).
- Sözleşme dışında endpoint veya alan eklenmez; önce `docs/api-contract.md` güncellenir.
