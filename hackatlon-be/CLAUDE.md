# hackatlon-be — Java backend (Spring Boot 4.1 / Java 25 + DuckDB)

Domain verisinin **tek sahibi**. Komutlar bu dizinden çalıştırılır. Endpoint sözleşmesi: `../docs/api-contract.md`.

## Komutlar
```bash
./mvnw spring-boot:run     # :8080; schema.sql + data.sql her açılışta (spring.sql.init.mode=always)
./mvnw test                # her PR öncesi yeşil olmalı
```
Env: `PORTAL_JWT_SECRET` (HS256), `PORTAL_SERVICE_KEY` (`/internal/**`). Yerel override'lar `application-local*` dosyasında tutulur, commit edilmez.

Dev token:
```bash
TOKEN=$(curl -s -H "X-Service-Key: ${PORTAL_SERVICE_KEY:-dev-service-key}" "http://127.0.0.1:8080/internal/dev/token?username=yonetici" | sed 's/.*"token":"\([^"]*\)".*/\1/')
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/tasks
```

## Yapı (`com.cyberops.portal`)
| Paket | Sorumluluk |
|---|---|
| `auth/` | JWT doğrulama (Spring Security resource server, HMAC), `CurrentUser`, `CurrentUserService`, service key filtresi, `/internal/users/sync`, `/internal/dev/token` |
| `common/` | Hata formatı (`@RestControllerAdvice`), ortak exception'lar, yardımcılar |
| `user/` | `/api/me`, ekip, yetkiler, yetkinlikler |
| `task/` | Task CRUD, durum, geçmiş, bildirim, SLA, yedek sorumlu, `/api/dashboard` |
| `activity/` | Etkinlikler ve katılım |
| `report/` | Excel (`poi-ooxml`) / PDF (`openpdf`) export |

Kaynaklar: `src/main/resources/schema.sql` (`CREATE TABLE IF NOT EXISTS`, id için `CREATE SEQUENCE` + `DEFAULT nextval`), `data.sql` (idempotent seed, `INSERT OR IGNORE`), veri dosyası `data/portal.duckdb`.

## Katmanlar
- **Controller:** HTTP eşleme, istek DTO validasyonu, `CurrentUser` alma. İş kuralı ve SQL yok.
- **Service:** Yetki ve görünürlük (scope) kontrolü, iş kuralları, `@Transactional`. Export ve MCP'nin çağırdığı endpoint'ler de aynı Service metodlarından geçer.
- **Repository:** `JdbcTemplate` / `NamedParameterJdbcTemplate` + parametreli SQL (`?` veya `:name`). **JPA yok**, string birleştirerek SQL yok.
- **DTO:** Java `record`. Yanıtta yalnızca sözleşmedeki alanlar döner; parola/secret alanı yok, tüm kolonların ham map'i dönülmez.

## Yetki
- Her istekte JWT (HS256, `PORTAL_JWT_SECRET`) doğrulanır. `sub`=user id.
- **Yetkiler JWT claim'lerinden değil**, `CurrentUserService` tarafından DuckDB `user_permission` tablosundan her istekte taze okunur. Kontrol: `currentUser.hasPerm("TASK_MANAGEMENT")`.
- `/internal/**` yalnızca `X-Service-Key` (`PORTAL_SERVICE_KEY`) ile; JWT ile erişilmez.
- **Task görünürlüğü:** TASK_MANAGEMENT yetkisi (veya tüm yetkiler) olan kullanıcı tüm task'ları görür; diğerleri yalnızca sorumlusu (`task_assignee`), yedek sorumlusu (`backup_assignee_id`) ya da oluşturanı olduğu task'ları. Bu kural listede, detayda, geçmişte, dashboard'da ve export'ta aynı Service metodundan uygulanır. Görünmeyen task için 404 dönülür.

## İş kuralları
- Task'ın her yazma işleminde (oluşturma, alan güncelleme, durum, atama) `task_history` kaydı **aynı `@Transactional`** içinde yazılır.
- Atama (ana veya yedek sorumlu) yapıldığında atanan kişiye `notification` kaydı aynı transaction'da oluşturulur; işlemi yapan kişiye kendi işlemi için bildirim gitmez.
- Hata formatı her yerde: `{"error": {"code": "NOT_FOUND", "message": "Türkçe açıklama"}}`. 400 validasyon, 401 kimlik yok, 403 yetki yok, 404 bulunamadı/görünmüyor.

## DuckDB tek süreç kuralı
- `.duckdb` dosyasını yalnızca backend süreci açar. **Uygulama çalışırken DuckDB CLI ile dosyayı açma**; inceleme için sunucuyu durdur ya da API'yi kullan.
- Hikari havuzu küçük (`maximum-pool-size=4`).
- `schema.sql` değişikliği eklemeli olur (yeni tablo / `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) ve önce ekibe duyurulur.

## Testler
- Her yeni endpoint için MockMvc testi: yetkili kullanıcı 200, token yok 401, yetkisiz kullanıcı 403/404.
- Yeni bir görünürlük kuralı için başka kullanıcının task'ına erişim testi.
