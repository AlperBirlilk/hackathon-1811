# Plan — Java + DuckDB Backend'e Tam Geçiş ve Agentic Yapı

## Context
Prototipte backend, UI ve veri tek bir Django uygulamasında. Hedef mimari:
- **`hackatlon-be/`:** Spring Boot (Java 25) + DuckDB. **Domain verisinin tek sahibi.** REST API, yetki kontrolü, task geçmişi, bildirim, SLA ve raporlar burada.
- **`hackatlon-django/`:** Frontend / BFF. LDAP login, JWT üretimi, template'ler. Domain verisine ORM ile değil, yalnızca Java API üzerinden erişir.
- **`mcp/`:** Java API'yi aynı JWT ile çağırır.

Bu ayrım hem MCP'nin aynı API'yi kullanmasını sağlıyor, hem de agentic yapıda "backend görevi" ile "frontend görevi"ni net biçimde bölüyor. Kullanıcı terminali repo kökünde açıp tek komutla full-stack görev verebilmeli.

**Süre: yaklaşık 1 saat. Risk yüksek.** Bu yüzden:
- Geçişe başlamadan önce `main` üzerindeki çalışan Django sürümü `demo-django-v1` olarak tag'lenir.
- **T+40'ta go/no-go:** demo akışı Java üzerinden çalışmıyorsa sunum tag'deki sürümden yapılır; mimari "geçiş sürüyor" diye anlatılır.

## Hedef mimari
```
Tarayıcı ──session──> Django :8000  (LDAP login, JWT üretir, template render)
                          │  Authorization: Bearer <JWT>
                          ▼
MCP server ──JWT──>  Java :8080  /api/**  (yetki, iş kuralları)
                          │  JdbcTemplate
                          ▼
                     DuckDB  hackatlon-be/data/portal.duckdb
```

### Kimlik ve yetki
1. Django `/login/`: LDAP (ya da yerel demo hesabı) doğrulanır.
2. Django, `POST /internal/users/sync` çağrısıyla kullanıcıyı Java'ya bildirir. Bu çağrı `X-Service-Key` başlığıyla korunur ve kullanıcının id'sini ve yetkilerini döner.
3. Django HS256 bir JWT üretir: `sub`=user id, `username`, `perms`, `exp`=8 saat. Ortak secret `PORTAL_JWT_SECRET` env değişkeninden okunur. JWT session'da saklanır, tarayıcıya JS ile verilmez.
4. Java her istekte JWT'yi doğrular (Spring Security resource server, HMAC). **Yetkiler JWT'deki claim'lerden değil, DuckDB'deki `user_permission` tablosundan okunur**; böylece yetki geri alma anında geçerli olur.
5. "Veri Paylaşımı" sayfası, MCP ve dış istemciler için uzun ömürlü bir JWT gösterir.

Django tarafında yalnızca `auth` / `sessions` için minimal SQLite kalır (Django'nun kendi altyapısı). Domain modelleri (`Task`, `Activity` vb.) kullanımdan kalkar; geçiş bitince silinir.

### Backend iç yapısı (`hackatlon-be/`)
- Spring Boot 4.1 (prototip `pom.xml` zaten var).
- Bağımlılıklar:
  - `spring-boot-starter-webmvc`
  - `spring-boot-starter-jdbc`
  - `spring-boot-starter-security` + `oauth2-resource-server` (JWT, HMAC)
  - `org.duckdb:duckdb_jdbc`
  - `springdoc-openapi`: `/v3/api-docs` sözleşmeyi doğrulamak için
  - `poi-ooxml` (Excel) + `openpdf` (PDF)
- JPA yok; DuckDB için Hibernate dialect'i olgun değil. Veri erişimi **JdbcTemplate + parametreli SQL**.
- **Paketler:** `auth/`, `user/`, `task/`, `activity/`, `report/`, `common/`. Her domain paketinde Controller → Service → Repository katmanları; yetki kontrolü Service katmanında, `CurrentUser` üzerinden.
- **Şema:** `src/main/resources/schema.sql` (`CREATE TABLE IF NOT EXISTS`, id'ler için `CREATE SEQUENCE` + `DEFAULT nextval`) ve `data.sql` (idempotent seed, `INSERT OR IGNORE`; Django seed'iyle aynı demo verisi). `spring.sql.init.mode=always`.
- **DuckDB tek süreç:** Dosyayı yalnızca backend süreci açar. Sunucu çalışırken DuckDB CLI ile dosya açılmaz. Hikari havuzu küçük tutulur (`maximum-pool-size=4`).
- **Tablolar:** prototipteki modellerle aynı adlar (`user`, `permission_type`, `user_permission`, `user_skill`, `task`, `task_assignee`, `task_history`, `activity`, `activity_attendee`) + yeni alanlar (`due_date`, `backup_assignee_id`, `is_on_leave`, etkinlik türü/katılım/iletişim kişisi) + `notification`.

### API sözleşmesi
- **Tek doğruluk kaynağı:** `docs/api-contract.md`. Endpoint, istek/yanıt JSON'ı, yetki ve hata formatı (`{"error": {"code", "message"}}`) burada tanımlanır.
- Sözleşme T+0-10'da yazılır ve push edilir. Değişiklikler backend ve frontend tarafıyla **aynı PR'da** yapılır.
- Endpoint'ler:
  - `/api/me`
  - `/api/tasks` (GET/POST, filtreler), `/api/tasks/{id}` (GET/PATCH), `/api/tasks/{id}/status`, `/api/tasks/{id}/history`
  - `/api/dashboard`
  - `/api/activities` (+ `/{id}/join`)
  - `/api/team`, `/api/team/{userId}/permissions`
  - `/api/users/{id}/skills`
  - `/api/notifications` (+ `/{id}/read`)
  - `/api/reports/tasks.xlsx|.pdf`
  - `/internal/users/sync`

## İş bölümü (1 saat)
| Zaman | Mert | Alper | Berkay | Aykun |
|---|---|---|---|---|
| T+0-10 | `demo-django-v1` tag'i; `hackatlon-be` iskeleti (git geçmişinden geri al, `target/` hariç), `pom.xml` bağımlılıkları, `schema.sql` + `data.sql`, `docs/api-contract.md` taslağı → push | Sözleşmeyi oku; JWT tasarımı | Sözleşmeyi oku; Django view envanteri | Sözleşmeyi oku; MCP iskeleti |
| T+10-40 | Java: `task/` (CRUD, durum, geçmiş, bildirim, SLA, yedek sorumlu) + `/api/dashboard` | Java: `auth/` (JWT filtresi, `CurrentUser`, `/internal/users/sync`) + Django: login → sync → JWT, `core/api_client.py` | Django: task, dashboard ve bildirim view'larını ORM'den `api_client`'a geçir | Java: `activity/`, `user/` (ekip, yetki, yetkinlik), `report/` (Excel/PDF) |
| T+40 | **Go/no-go:** Java üzerinden login → task oluşturma → durum değiştirme çalışıyor mu? | | | |
| T+40-55 | Entegrasyon ve hata düzeltme | Django: etkinlik, ekip ve profil view'larını `api_client`'a geçir | `/demo-check` | MCP server (Java API'yi çağırır) |
| T+55-60 | Demo provası | | | |

Kural: Java endpoint'i bitmeden ilgili Django view'ı geçirilmez. Frontend sahibi o sırada `api_client` fonksiyonlarını sözleşmeye göre yazar ve view'ı hazır tutar.

## Agentic yapıdaki değişiklikler

### CLAUDE.md
- **Kök `CLAUDE.md` (orkestratör):**
  - Repo haritası: be / django / mcp / docs.
  - İki sunucuyu başlatma komutları: Java `:8080`, Django `:8000`; ortak env `PORTAL_JWT_SECRET`, `PORTAL_SERVICE_KEY`, `PORTAL_API_URL`.
  - **Full-stack görev akışı:**
    1. Sözleşmeyi güncelle (`docs/api-contract.md`).
    2. `backend-dev` ve `frontend-dev` agent'larını **paralel** başlat. Backend endpoint'i yazar; frontend `api_client` fonksiyonunu ve view/template'i sözleşmeye göre yazar.
    3. İki sunucuyla uçtan uca curl testi.
    4. `security-reviewer` + `code-reviewer`.
  - Tek katmanlı görevde yalnızca ilgili agent çalıştırılır.
- **`hackatlon-be/CLAUDE.md` (yeni):**
  - Paket yapısı ve katmanlar.
  - JdbcTemplate + parametreli SQL; JPA yok.
  - DuckDB tek süreç kuralı.
  - `schema.sql` değişikliği = koordinasyon (migration kuralının karşılığı).
  - Komutlar: `./mvnw spring-boot:run`, `./mvnw test`.
  - Hata formatı, `CurrentUser`, yetki kontrolünün Service katmanında yapılması.
- **`hackatlon-django/CLAUDE.md` (güncellenir):**
  - Django artık frontend / BFF.
  - Yeni domain ORM kodu yazılmaz; veri yalnızca `core/api_client.py` üzerinden alınır (tek HTTP noktası; JWT ekler, hataları Türkçe mesaja çevirir, 401'de login'e yönlendirir).
  - Template ve tasarım kuralları aynen geçerli.
- **`mcp/CLAUDE.md`:** API adresi `:8080`, JWT ile.

### `.claude/rules/`
- **`java-backend.md` (yeni, `paths: hackatlon-be/**`):**
  - SQL'de string birleştirme yok; `?` / named parametreler kullanılır.
  - Her Controller endpoint'i kimlik doğrulama ister (`/internal/**` service key ile).
  - Scope (görünürlük) Service katmanında uygulanır.
  - Task'ın her yazma işleminde `task_history` kaydı aynı transaction içinde yazılır.
  - Yanıt DTO'ları record olarak tanımlanır; entity map'i doğrudan dönülmez.
- **`django.md` (güncellenir):** Domain için ORM yok, `api_client` kullanılır; view'lar API hatalarını `messages` ile gösterir.
- **`templates.md`:** aynen kalır.
- **`security.md` (genişletilir):**
  - JWT session'da kalır, JS'e verilmez.
  - Secret'lar env'den okunur.
  - Java'da yetkiler DB'den okunur.
  - `/internal/**` dışarıya açılmaz.
  - Export ve MCP aynı Service katmanı kontrollerinden geçer.

### `.claude/agents/`
| Agent | Değişiklik |
|---|---|
| `backend-dev` | **Yeni.** Java/Spring/DuckDB. `django-dev` agent'ının yerini alır |
| `frontend-dev` | `template-dev` + Django view işleri birleşir: `api_client`, view, template, `frontend-design` |
| `security-reviewer` | İki stack'i birlikte kontrol eder: JWT doğrulama, algoritma sabitleme, service key, JdbcTemplate injection, Service katmanında scope, Django'da token sızıntısı |
| `code-reviewer` | İki stack + sözleşme uyumu (Java DTO ↔ `api-contract.md` ↔ `api_client`) |
| `qa-demo` | İki sunucuyu başlatır; senaryoyu Django (tarayıcı akışı) ve doğrudan API (JWT) üzerinden doğrular |

### `.claude/skills/`
- **`fullstack-feature` (yeni, ana skill):** sözleşme → backend endpoint → `api_client` → view/template → iki taraf testi. Kökten verilen "şu özelliği ekle" görevleri bu akışı izler.
- **`new-backend-endpoint` (yeni):** Controller/Service/Repository + `schema.sql` + MockMvc testi.
- **`new-page` (güncellenir):** veri `api_client` ile alınır.
- **`task-change`:** Java `TaskService` tarafına taşınır.
- **`new-api-endpoint`:** kaldırılır; yerini `new-backend-endpoint` alır.
- **`add-mcp-tool` (yeni):** Java API'yi saran salt okunur tool.
- **`demo-check` (güncellenir):** `./mvnw test` + Django testleri + iki sunucu + `qa-demo` + `security-reviewer`.

### `.claude/settings.json`
- allow'a eklenecekler: `./mvnw:*`, `mvn:*`, `curl -s http://127.0.0.1:8080:*`.
- deny'a eklenecek: `Read(**/application-local*)`.

## Doğrulama
- `cd hackatlon-be && ./mvnw spring-boot:run` → `curl :8080/v3/api-docs` 200; JWT olmadan `/api/tasks` 401.
- Django `:8000` login → dashboard Java'dan gelen veriyle açılır; task oluştur, durum değiştir, geçmiş görünür.
- Yetkisiz kullanıcı JWT'si ile başka takımın task'ı → 403/404; Excel/PDF yalnızca rapor yetkisiyle.
- Claude'u yeniden başlatınca `/agents` 5 agent'ı, `/skills` 6 skill'i göstermeli. Kökten verilen bir full-stack görevde `backend-dev` ve `frontend-dev` paralel başlamalı.
