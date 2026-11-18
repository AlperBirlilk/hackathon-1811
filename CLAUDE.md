# CyberOps Portal — Hackathon Monorepo

Siber güvenlik ekipleri için task, etkinlik, yetkinlik ve yetki yönetimi portalı. 4 kişilik ekip, paralel Claude Code oturumlarıyla çalışıyor. Bu dosya **orkestratör**: kökten verilen görevler burada tarif edilen akışla agent'lara dağıtılır.

## Mimari
```
Tarayıcı ──session──> Django :8000  (LDAP login, JWT üretir, template render)
                          │  Authorization: Bearer <JWT>
MCP server ──JWT──>  Java :8080  /api/**  (yetki, iş kuralları)
                          │  JdbcTemplate
                     DuckDB  hackatlon-be/data/portal.duckdb
```
Ayrıntı ve gerekçe: `docs/migration_plan.md`.

## Repo haritası
| Yol | İçerik |
|---|---|
| `hackatlon-be/` | **Backend.** Spring Boot 4.1 / Java 25 + DuckDB. Domain verisinin tek sahibi: REST API, yetki, task geçmişi, bildirim, rapor. Detay: `hackatlon-be/CLAUDE.md` |
| `hackatlon-django/` | **Frontend / BFF.** LDAP login, JWT üretimi, server-rendered template'ler. Domain verisine yalnızca `core/api_client.py` ile erişir. Detay: `hackatlon-django/CLAUDE.md` |
| `mcp/` | Salt okunur MCP server; Java API'yi JWT ile çağırır. Detay: `mcp/CLAUDE.md` |
| `docs/api-contract.md` | **Endpoint sözleşmesinin tek doğruluk kaynağı** (istek/yanıt JSON'ı, yetki, hata formatı) |
| `docs/` | Gereksinimler, takım kararları, ERD'ler, `migration_plan.md`, `claude_setup_plan.md` |
| `.claude/` | Ortak agent, skill, rule ve izinler (repoda tutulur) |

## Çalıştırma
Ortak env (iki sunucuda da aynı değerler; commit edilmez):
```bash
export PORTAL_JWT_SECRET='<en az 32 byte rastgele>'   # HS256 ortak secret
export PORTAL_SERVICE_KEY='<rastgele>'                # /internal/** için X-Service-Key
export PORTAL_API_URL=http://127.0.0.1:8080           # Django ve MCP'nin Java adresi
```
1. **Önce Java** (Java 25):
   ```bash
   cd hackatlon-be
   ./mvnw spring-boot:run      # http://127.0.0.1:8080, schema.sql + data.sql otomatik
   ./mvnw test
   ```
2. **Sonra Django** (Python 3.10+; macOS sistem Python 3.9 çalışmaz):
   ```bash
   cd hackatlon-django
   uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt
   .venv/bin/python manage.py migrate         # yalnızca auth/session tabloları
   .venv/bin/python manage.py runserver        # http://127.0.0.1:8000
   .venv/bin/python manage.py test core
   ```
3. **Dev token** (API'yi doğrudan denemek için):
   ```bash
   TOKEN=$(curl -s -H "X-Service-Key: ${PORTAL_SERVICE_KEY:-dev-service-key}" "http://127.0.0.1:8080/internal/dev/token?username=yonetici" | sed 's/.*"token":"\([^"]*\)".*/\1/')
   curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/me
   ```

Demo hesapları (parola `Cyber2026!`): `yonetici` (tüm yetkiler), `alper` (Task Mgmt), `berkay` (Report), `aykun` (Activity), `mert` (Data Access), `admin` (superuser).

**Fallback:** `demo-django-v1` tag'i eski, tamamı Django olan çalışan sürümdür. Java akışı demoda çalışmazsa sunum bu tag'den yapılır (`git switch --detach demo-django-v1`).

## Görev akışı (orkestratör)
### Full-stack görev ("şu özelliği ekle")
`/fullstack-feature` skill'ini izle:
1. **Sözleşme:** `docs/api-contract.md` içinde ilgili bölümü yaz veya güncelle (endpoint, istek/yanıt JSON'ı, yetki, hata kodları).
2. **Paralel geliştirme:** `backend-dev` ve `frontend-dev` agent'larını **tek mesajda, paralel** başlat. İkisine de sözleşme bölümünü ortak spec olarak ver.
   - `backend-dev`: Controller/Service/Repository + `schema.sql` + MockMvc testi.
   - `frontend-dev`: `api_client` fonksiyonu + view + template (sözleşmeye göre; backend'i beklemez).
3. **Uçtan uca:** İki sunucuyu başlat; dev token ile API'ye ve session + CSRF ile Django'ya curl at.
4. **İnceleme:** `security-reviewer` + `code-reviewer` agent'larını paralel çalıştır; Kritik/Yüksek bulguları düzelt.

### Tek katmanlı görev
Yalnızca ilgili agent: Java işi → `backend-dev`; template/görünüm/view işi → `frontend-dev`; MCP → `/add-mcp-tool`. Sözleşme değişmiyorsa diğer tarafa dokunulmaz.

## Ekip kuralları
- **Çalışan kodu yeniden yazma.** Demo yakın; mevcut desenlerin üzerine ekleme yap.
- **Dil:** Arayüz metinleri Türkçe; kod, değişken adları ve commit mesajları İngilizce.
- **Branch:** Kendi branch'inde çalış (`mert`, `alper`, `berkay`, `aykun` veya `feat/<kişi>-<konu>`), küçük ve sık PR'larla `main`'e gönder. Başlamadan önce `git pull origin main`.
- **Sözleşme:** `docs/api-contract.md` değişikliği, iki tarafın koduyla **aynı PR'da** yapılır.
- **`schema.sql` koordinasyonu (kritik):** Değiştirmeden önce ekibe haber ver. Yalnızca eklemeli değişiklik: yeni tablo (`CREATE TABLE IF NOT EXISTS`) veya `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`. Mevcut ifadeler yıkıcı biçimde düzenlenmez (kolon silme/yeniden adlandırma, tip değiştirme yok). `data.sql` idempotent kalır.
- **Django migration'ları** artık yalnızca auth/session içindir; domain modeli eklenmez.
- **Kapsam:** Sahip olduğun özelliğe odaklan (`docs/migration_plan.md` iş bölümü). Başkasının dosyasında büyük değişiklik gerekiyorsa önce sor.
- **Bağımlılık:** `pom.xml` / `requirements.txt` değişikliği küçük tutulur ve hemen push edilir.

## Claude yapısı
- **Agent'lar** (`.claude/agents/`):
  - `backend-dev`: Java / Spring / DuckDB
  - `frontend-dev`: Django view + `api_client` + template + tasarım
  - `security-reviewer`, `code-reviewer`: salt okunur, iki stack, PR öncesi
  - `qa-demo`: iki sunucuyla uçtan uca demo doğrulaması
- **Skill'ler:**
  - `/fullstack-feature`: ana akış (sözleşme → backend ∥ frontend → e2e → inceleme)
  - `/new-backend-endpoint`: Java endpoint'i
  - `/new-page`: yeni Django ekranı
  - `/task-change`: task davranışı (Java `TaskService` + Django form)
  - `/add-mcp-tool`: MCP tool'u
  - `/demo-check`: demo öncesi tam kontrol
- **Kurallar** (`.claude/rules/`): `java-backend.md`, `django.md`, `templates.md`, `security.md`; ilgili dosyalara dokunulduğunda otomatik yüklenir.
- **Kişisel ayarlar** `.claude/settings.local.json` ve `CLAUDE.local.md` dosyalarına yazılır; ikisi de gitignore'da.
