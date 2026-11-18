# portal-backend (Spring Boot 4 + DuckDB)

Domain verisinin sahibi. Django LDAP login yapar, `POST /internal/users/sync` çağırır ve
HS256 JWT üretip `Authorization: Bearer <jwt>` ile `/api/**` uçlarını çağırır.

## Çalıştırma

```bash
./mvnw spring-boot:run        # veya: mvn spring-boot:run
```

- Port: `8080`. Veritabanı: `./data/portal.duckdb` (otomatik oluşur, git'e girmez).
- `schema.sql` ve `data.sql` her açılışta çalışır (idempotent). Temiz seed için uygulamayı durdurup `data/` klasörünü silin.
- Swagger: http://localhost:8080/swagger-ui.html

## Ortam değişkenleri

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `PORTAL_JWT_SECRET` | `dev-only-change-me-dev-only-change-me-32b` | Django ile ortak HS256 anahtarı (en az 32 byte) |
| `PORTAL_SERVICE_KEY` | `dev-service-key` | `/internal/**` için `X-Service-Key` header değeri |

## JWT

- Algoritma: HS256. Claim'ler: `sub` = `app_user.id` (string), `username`, `iat`, `exp`.
- Yetkiler token'dan **okunmaz**; her istekte DuckDB'den (`user_permission`) yüklenir.

## Test token'ı (sadece dev)

```bash
TOKEN=$(curl -s -H 'X-Service-Key: dev-service-key' \
  'http://localhost:8080/internal/dev/token?username=yonetici' | sed 's/.*"token":"\([^"]*\)".*/\1/')
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/me
```

Demo kullanıcıları: `direktor` (tüm yetkiler), `yonetici` (tüm yetkiler, ekip yöneticisi), `mert`, `alper`, `berkay`, `aykun`.

## Paketler

- `auth`: SecurityConfig, JWT, `CurrentUserService.get()` / `require(code)`, `/internal/users/sync`, `/api/me`
- `common`: `PermissionCodes`, `NotFoundException`, `ForbiddenException`, hata formatı `{"error":{"code","message"}}`
- `task`: `TaskVisibility` (görünürlük kuralı — tüm task sorgularında kullanın)
- `user`, `activity`, `report`: ekip tarafından doldurulacak

Kurallar: sadece `JdbcTemplate`/`NamedParameterJdbcTemplate`, sadece parametreli SQL, JPA yok.
