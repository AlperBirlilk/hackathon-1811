# Plan — Claude Agentic Kurulumu (prototip: `hackatlon-django`)

## Context
Hackathon: 4 kişi, kalan süre ~1.5-2 saat, herkes Claude Code kullanıyor. Alper'in prototipi `main`'e merge edildi (`5e29d9e`). Bu plan iki şey yapıyor:
1. Ortak bir Claude yapısı kuruyor (CLAUDE.md, rule'lar, agent'lar, skill'ler, izinler). Böylece 4 paralel Claude oturumu prototipin mevcut desenlerine uyar ve birbirini ezmez.
2. Prototipte eksik kalan minimum gereksinimleri öncelik sırasıyla kişilere dağıtıyor.

Kural: **Çalışan hiçbir şey yeniden yazılmaz.** Demo yakın; prototipin mimarisi korunur, üzerine ekleme yapılır.

## Prototipin gerçek yapısı (planın dayanağı)
- **Uygulama:** `hackatlon-django/` — Django 5.2 monolit, server-rendered template'ler, SQLite + ORM. Tek app: `core`.
- **Python:** 3.10+ gerekli (macOS'taki sistem Python 3.9 çalışmaz). Kurulum `uv venv -p 3.12 .venv && uv pip install -r requirements.txt`.
- **Komutlar:** `migrate` → `seed` (`--reset` ile task ve etkinlikleri sıfırlar) → `runserver`; testler `manage.py test core` (14 test, şu an yeşil). Demo şifresi `Cyber2026!`.
- **Yetki modeli:** Sabit rol yok, 5 yetki tipi var: `PermissionType` + `UserPermission` (TASK_MANAGEMENT, ACTIVITY_MANAGEMENT, ROLE_MANAGEMENT, REPORT_ANALYSIS, DATA_ACCESS). Kontroller:
  - `user.has_portal_perm(code)` ve `user.is_manager` (ROLE_MANAGEMENT yetkisi)
  - view tarafında `@portal_perm_required(code)` dekoratörü
  - template'lerde `perm.*` context'i (`core/context_processors.py`)
- **Ekip hiyerarşisi:** `User.manager` alanı (self-FK); ekip istatistikleri `team_with_stats(manager)` ile.
- **Task kuralları:**
  - Tüm task değişiklikleri `core/services.py` içindeki `create_task` / `update_task` fonksiyonlarından geçer; `TaskHistory` kaydı otomatik yazılır.
  - Görünürlük `visible_tasks(user)`, düzenleme yetkisi `can_edit_task(user, task)` ile belirlenir (ikisi de `core/views.py` içinde).
- **Auth:** `core/ldap_backend.py` (ldap3, yalnızca kimlik doğrulama) + yerel demo hesapları (`LOCAL_AUTH_ENABLED`).
- **Arayüz:** `templates/` (base, app, `core/*`, `_field.html`, `_theme_toggle.html`), `static/css/portal.css`, `static/js/portal.js`; açık/koyu tema var.
- **Diğer:** `hackatlon-be/` boş bir Spring Boot iskeleti (`target/` klasörü commit edilmiş); `main.py` PyCharm'ın örnek dosyası.

## Kesinleşen kararlar
- Mimari aynen kalır: Django monolit + template + SQLite/ORM. React yok. DuckDB'ye ileride geçişi zorlaştırmamak için raw SQL yazılmaz.
- **Roller, mevcut yetki tiplerine eşlenir.** Yeni bir rol modeli eklenmez:
  - Çalışan = yetkisiz kullanıcı
  - Yönetici = ROLE_MANAGEMENT + TASK_MANAGEMENT
  - Direktör = tüm yetkiler, ya da yetki modelinde açıkça seçilmiş bir "üst yönetici" kullanıcısı. Seed'e `direktor` adında bir kullanıcı eklenir.
- **REST API:** `djangorestframework` eklenir. Endpoint'ler salt okunur, Token auth ile çalışır, DATA_ACCESS yetkisi ister ve `visible_tasks` ile aynı görünürlük kurallarına uyar. "Veri Paylaşımı" sayfası kullanıcının token'ını ve endpoint listesini gösterir.
- **MCP:** `mcp/` altında salt okunur bir MCP server; yalnızca REST API'yi token ile çağırır.

## Migration koordinasyonu (kritik)
Tek bir `core` app'i olduğu için 4 kişi ayrı ayrı `makemigrations` çalıştırırsa çakışma kaçınılmaz olur. Çözüm:
- **Bütün model değişiklikleri T+0-15 içinde tek seferde, tek kişi tarafından** yapılır (`0003_mvp_fields.py`) ve hemen `main`'e push edilir. Herkes çalışmaya bu commit'in üzerinden başlar.
- Bu adımdan sonra model değişikliği gerekirse önce ekibe haber verilir, sonra `git pull` → `makemigrations` → hemen push.

Toplu model değişikliği (`0003`):
- `Task`: `due_date` (DateTimeField, null olabilir), `backup_assignee` (FK User, null olabilir).
  - `assignees` = ana sorumlular, `backup_assignee` = yedek sorumlu.
  - `is_overdue` property olarak eklenir; SLA'ya göre otomatik son tarih `services.create_task` içinde atanır (Kritik 24 saat, Yüksek 3 gün, Orta 7 gün, Düşük 14 gün).
- `User`: `is_on_leave` (Bool) — yedek sorumluya devir için.
- `Activity`: `activity_type` (Eğitim / Konferans / Diğer), `participation_type` (Bireysel / Kurumsal), `contact_person` (FK User, null olabilir).
- `Notification`: `user`, `task` (FK, null olabilir), `message`, `is_read`, `create_date`.

## Eksik özellikler — öncelik ve sahip
| Öncelik | Özellik | Dokunulacak yerler | Sahip |
|---|---|---|---|
| P0 | Toplu model değişikliği (`0003`) + seed güncellemesi (direktör, due date, yedek sorumlu) | `models.py`, `seed.py`, `admin.py` | Mert |
| P1 | Bildirim: atama sonrası `Notification` oluşturma (services içinde), navbar'da sayaç, okundu işaretleme | `services.py`, `base`/`app.html`, yeni view | Mert |
| P1 | Son tarih, geciken iş ve SLA: form alanı, liste ve dashboard'da "Geciken" kartı | `forms.py`, `task_*.html`, `dashboard` | Mert |
| P1 | Excel/PDF export (REPORT_ANALYSIS yetkisi, `task_list` filtreleriyle aynı) | yeni `core/reports.py` + view; `openpyxl`, `reportlab` | Berkay |
| P1 | REST API + Veri Paylaşımı sayfası | yeni `core/api.py` (DRF), `data_sharing.html` | Aykun |
| P2 | Yedek sorumlu ve devir: task formu ve detayında yedek sorumlu; izinli kullanıcının işleri yedeğin dashboard'unda | `views.py`, template'ler | Alper |
| P2 | Etkinlik alanları (tür, katılım, iletişim kişisi) form ve listede | `forms.py`, `activity_*.html` | Alper |
| P2 | Direktör görünümü: tüm ekipler ve raporlar | `views.py` (`team`, `dashboard`) | Alper |
| P3 | MCP server (`list_tasks`, `overdue_tasks`, `team_summary`) | `mcp/` | Aykun |

## Oluşturulacak Claude dosyaları

### 1. CLAUDE.md
- **Kök `CLAUDE.md`:** repo haritası (`hackatlon-django/` = uygulama, `mcp/`), Python 3.10+ ve uv notu, çalıştırma ve test komutları, demo hesapları, dil kuralı (arayüz Türkçe, kod/commit İngilizce), migration koordinasyon kuralı, branch kuralı (`feat/<kişi>-<konu>`, küçük ve sık PR'lar `main`'e).
- **`hackatlon-django/CLAUDE.md`:**
  - Mimari özeti; mevcut yardımcıların listesi: `services.create_task`/`update_task`, `visible_tasks`, `can_edit_task`, `portal_perm_required`, `team_with_stats`, `has_portal_perm`, context processor'daki `perm`.
  - "Yeni yardımcı yazmadan önce bunları kullan" talimatı.
  - Yeni sayfa deseni: view (`views.py`) → url (`core/urls.py`) → template (`app.html`'i extend eder, `_field.html` kullanır) → menü linki (`perm.*` ile).
  - Yeni sayfalar `PageRenderTests` içine eklenir.
- **`mcp/CLAUDE.md`:** Python MCP SDK; yalnızca REST API çağırır, DB'ye doğrudan erişmez.

### 2. `.claude/rules/` (path-scoped)
- **`django.md`** (`paths: hackatlon-django/**/*.py`):
  - Task'ı her zaman `services` üzerinden değiştir; doğrudan `task.save()` kullanma.
  - Sorgular `visible_tasks` ile scope edilir; nesneler `get_object_or_404(<scoped qs>, pk=...)` ile alınır.
  - Yazma yapan view'lar `@require_POST` ile korunur.
  - `select_related` / `prefetch_related` kullan.
  - Raw SQL yok.
  - Model değişikliği yalnızca koordinasyon kuralına göre yapılır.
- **`templates.md`** (`paths: hackatlon-django/templates/**, hackatlon-django/static/**`):
  - Mevcut `portal.css` sınıflarını ve tema değişkenlerini kullan; inline stil yok.
  - Her POST formunda `{% csrf_token %}`; metinler Türkçe.
  - Görsel tasarım için `frontend-design` skill'i kullanılır, mevcut tasarım dili korunur.
- **`security.md`** (her yerde geçerli):
  - Her view'da yetki kontrolü (`portal_perm_required` ya da scoped queryset).
  - Export, API ve MCP aynı görünürlük kurallarına uyar.
  - `next` parametresi `url_has_allowed_host_and_scheme` ile doğrulanır.
  - Secret ve `.env` commit edilmez.
  - LDAP backend'indeki korumalar (boş parola, username regex, escape) kaldırılmaz.

### 3. `.claude/agents/`
| Agent | Görev | Araçlar |
|---|---|---|
| `django-dev` | View, form, service, model, migration; yukarıdaki desenlere uyar | tümü |
| `template-dev` | Template ve CSS; `frontend-design` skill'ini kullanır, `portal.css` diline uyar | tümü |
| `security-reviewer` | IDOR (scope edilmemiş `objects.get/all`), eksik `portal_perm_required`, CSRF / `require_POST`, open redirect, export/API/MCP yetki sızıntısı, yetki yükseltme, LDAP korumalarının bozulması | salt okunur |
| `code-reviewer` | Desenlere uyum (services, `visible_tasks`), N+1, migration çakışması, testlerin güncel olması | salt okunur |
| `qa-demo` | Demo senaryosunu yönetici, çalışan ve direktör hesaplarıyla curl üzerinden (session + CSRF) uçtan uca doğrular | Bash, Read |

### 4. `.claude/skills/`
- **`new-page`:** view + url + template + menü + `PageRenderTests` maddesi (yetkili kullanıcı 200, yetkisiz 403).
- **`task-change`:** Task'a yeni bir davranış ekleme: `services` içinde değişiklik → `TaskHistory` action tipi → gerekirse `Notification` → test.
- **`new-api-endpoint`:** DRF ViewSet (salt okunur, scoped queryset, DATA_ACCESS yetkisi) → router → curl ile token testi.
- **`demo-check`:** `seed --reset` → `test core` → `makemigrations --check` → `runserver` → demo akışı → `security-reviewer`.

### 5. `.claude/settings.json` (mevcut `enabledPlugins` korunur)
- allow:
  - `.venv/bin/python manage.py *`, `python manage.py *`
  - `uv *`, `curl -s *127.0.0.1*`
  - `git status|diff|log|add|commit|checkout|pull|fetch|switch`
- deny: `Read(**/.env*)`, `rm -rf *`, `git push --force*`
- Kök `.claude/settings.json` (yeni kurulan) ile `hackatlon-django/.claude/settings.json` aynı plugin'i içeriyor. Kök dosya esas alınır; alt dizindeki dosya tutulabilir.

### 6. Repo temizliği (küçük, demo için risksiz)
- Kök `.gitignore` dosyasına Python ve venv kuralları eklenir (`.venv/`, `__pycache__/`, `db.sqlite3`); Java için olanlar kalır.
- `hackatlon-be/target/` git'ten çıkarılır (`git rm -r --cached`).
- `main.py` (PyCharm örneği) silinir.
- **Ekiple teyit edilecek:** `hackatlon-be/` (Spring Boot) kullanılmıyorsa tamamen kaldırılır.
- `requirements.txt` dosyasına `djangorestframework`, `openpyxl`, `reportlab` eklenir (her biri ilgili özelliğin sahibi tarafından, ama tek satır çakışmalarına dikkat).
- README'ye macOS/uv kurulum satırı eklenir.

## Zaman çizelgesi
- **T+0-15:** Mert, Claude kurulumu + `0003` migration + seed güncellemesini `main`'e push eder. Diğerleri bu sırada kendi P1 işlerinin planını çıkarır ve template/view taslağı hazırlar (model dosyasına dokunmadan).
- **T+15-75:** Tabloya göre paralel geliştirme; her özellik bitince PR açılır.
- **T+75-95:** Entegrasyon; PR'larda `security-reviewer` ve `code-reviewer` çalıştırılır.
- **T+95-110:** `/demo-check` ve demo provası. MCP (P3) bu noktada yetişmemişse "Veri Paylaşımı" sayfasındaki REST API ile gösterilir.

## Doğrulama
- `claude` içinde `/agents` 5 agent'ı, `/skills` 4 skill'i listelemeli.
- `cd hackatlon-django && .venv/bin/python manage.py test core` yeşil olmalı; `makemigrations --check` temiz olmalı.
- `seed --reset` sonrası demo akışı:
  1. Yönetici kritik bir iş açar; ana ve yedek sorumlu atar, son tarih SLA'ya göre otomatik gelir.
  2. Çalışan bildirimi görür, işi başlatır ve tamamlar.
  3. Dashboard'da sayılar ve geçmiş güncellenir; geciken iş kartı görünür.
  4. Etkinlik (tür, katılım, iletişim kişisi) ve yetkinlik eklenir.
  5. Direktör filtreli Excel/PDF raporunu alır; `curl -H "Authorization: Token …" /api/tasks/` yalnızca yetkili veriyi döner, yetkisiz kullanıcıya 403.
