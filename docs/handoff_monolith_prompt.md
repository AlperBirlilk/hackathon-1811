Hackathon'un bitmesine az kaldı. Proje **Django monolit** olarak devam ediyor: `hackatlon-django/`, SQLite, ORM, template'ler. Java backend'e geçmiyoruz. Senden üç şey istiyorum:
1. Ortak `.claude` yapısını repoya al.
2. Eksik özellikleri Django içinde tamamla.
3. Django içine paralel bir REST API ve onu kullanan bir MCP server ekle.

Repo kökündesin. Remote: `origin` (GitHub `AlperBirlilk/hackathon-1811`).

**Önemli:** Ben (kullanıcı) prototipe kendi yeni özelliklerimi de ekledim. Aşağıdaki plan, Mert'in branch'inde yapılan işlere göre yazıldı ve benim kodumu bilmiyor. Bu yüzden **önce Adım 0'ı yap, planı güncelle ve onayımı almadan hiçbir dosyayı değiştirme, commit atma.**

## Adım 0 — Mevcut kodu incele, planı güncelle, onay iste (önce bu)
1. Kod değiştirmeden çalışan bir keşif yap:
   - `git status`, `git log --oneline -15`, `git diff origin/main --stat`
   - `hackatlon-django/core/models.py`, `views.py`, `services.py`, `urls.py`, `forms.py`, `templates/core/`, `management/commands/seed.py`, `requirements.txt`, migration listesi
   - Repo kökünde zaten bir `.claude/`, `CLAUDE.md`, `mcp/` veya `docs/` varsa onları da oku.
2. Benim eklediğim özellikleri çıkar ve aşağıdaki plandaki her maddeyle karşılaştır:
   - **Zaten var ve çalışıyor:** Plandan çıkar; yeniden yazma. Plandaki diğer maddeler (API, MCP, rapor) benim modelime ve alan adlarıma uyarlanır.
   - **Kısmen var:** Sadece eksik kısmı plana yaz.
   - **Benim tasarımım plandakinden farklı** (alan adı, model yapısı, URL, yetki mantığı): Varsayılan olarak benimki korunur, plan ona uyarlanır. Önemli bir çelişki varsa bana sor.
   - **Plandaki dosya benim dosyamla çakışıyor** (`.claude/`, `CLAUDE.md`, `mcp/`, `docs/`): Körlemesine `git checkout` ile üzerine yazılmaz. Birleştirme önerisi sunulur.
3. Güncellenmiş planı `docs/plan_<benim-adım>.md` dosyasına yaz. Bu, izin verdiğim tek dosya değişikliği. Planda şunlar olsun:
   - Mevcut özelliklerim (kısa liste)
   - Yapılacaklar ve öncelik sırası
   - Tek migration'da toplanacak model değişiklikleri
   - Paralel subagent dağılımı
   - Riskler
   - Bana sorulacak sorular
4. Bana planın kısa bir özetini ve soruları sun (plan mode'daysan ExitPlanMode, değilsen soru sorarak). **Uygulamaya ancak açık onayımdan sonra geç.** Onay gelince aşağıdaki adımları güncellenmiş plana göre uygula.

## Adım 1 — `.claude` yapısını ve dokümanları aktar (2 dk)

Önce, aşağıdaki komutların üzerine yazacağı dosyalarda benim değişikliğim olup olmadığına bak:
```bash
git diff --stat HEAD -- .claude CLAUDE.md hackatlon-django/CLAUDE.md docs mcp
git ls-files .claude CLAUDE.md mcp
```
Benim içeriğim varsa onu koru ve birleştir (Adım 0'da onaylanan şekilde).

```bash
git fetch origin --tags
# Monolit için hazırlanmış Claude yapısı ve dokümanlar (demo-django-v1 tag'i):
git checkout demo-django-v1 -- .claude CLAUDE.md hackatlon-django/CLAUDE.md docs
# MCP server, Mert'in branch'inden (Java API için yazıldı; Django API aynı sözleşmeyle konuşacak):
git checkout origin/mert -- mcp/server.py mcp/pyproject.toml mcp/uv.lock mcp/README.md .mcp.json.example docs/api-contract.md
```

Ardından şunları oku:
- `CLAUDE.md`
- `hackatlon-django/CLAUDE.md`
- `.claude/rules/*.md`
- `docs/api-contract.md`: yalnızca Adım 3'teki endpoint'lerin JSON yapıları için

Notlar:
- `mcp/CLAUDE.md` dosyasını `demo-django-v1` tag'indeki sürümden al (`git checkout demo-django-v1 -- mcp/CLAUDE.md`). İçindeki API adresini `http://127.0.0.1:8000` olarak güncelle.
- `docs/api-contract.md` Java için yazıldı. Burada yalnızca JSON alan adları ve yapılar için referans olarak kullanılacak.
- Agent'lar (`django-dev`, `template-dev`, `security-reviewer`, `code-reviewer`, `qa-demo`) ve skill'ler (`/new-page`, `/task-change`, `/new-api-endpoint`, `/demo-check`) görünmüyorsa kullanıcıdan Claude'u yeniden başlatmasını iste.

Bu dosyaları commit et: `chore: import shared Claude setup and MCP server`.

## Adım 2 — Model değişiklikleri: tek migration, önce bu (5 dk)

Tek bir `core` app'i olduğu için model değişikliklerini **tek seferde** yap, `makemigrations core` çalıştır, commit et ve **hemen push et**. Paralel işler bu commit'in üzerinden başlar.

Değişiklikler:
- **`Task`:**
  - `due_date` (DateTimeField, null olabilir)
  - `backup_assignee` (FK User, null olabilir, `related_name='backup_tasks'`)
  - `TaskHistory.ACTION_CHOICES` listesine `due_date_change`
- **`User`:** `is_on_leave` (BooleanField, varsayılan False)
- **`Activity`:**
  - `activity_type` (TRAINING / CONFERENCE / OTHER → Eğitim / Konferans / Diğer)
  - `participation_type` (INDIVIDUAL / CORPORATE → Bireysel / Kurumsal)
  - `contact_person` (FK User, null olabilir)
- **Yeni `Notification` modeli:** `user`, `task` (FK, null olabilir), `message`, `is_read`, `create_date`.
- **`seed.py`:**
  - `direktor` kullanıcısı: tüm yetkiler, parola `Cyber2026!`. `yonetici` kullanıcısının yöneticisi `direktor` olsun.
  - Task'lara SLA'ya göre son tarih ver; açık task'lardan 1-2 tanesi demo için gecikmiş olsun.
  - Bazı task'lara yedek sorumlu ata.
  - Etkinliklerde tür, katılım şekli ve iletişim kişisini doldur.
  - Seed idempotent kalsın.

## Adım 3 — Paralel geliştirme

Model commit'inden sonra üç işi **paralel subagent'larla** yürüt. Subagent tipleri: `django-dev`, `template-dev`; yoksa `general-purpose`. Hepsi `.claude/rules` kurallarına uyar:
- Task yazma işlemleri `core/services.py` üzerinden yapılır.
- Sorgular `visible_tasks` ile scope edilir.
- Yetki için `portal_perm_required` kullanılır.
- Yazma yapan view'lar `@require_POST` ile korunur.
- Arayüz metinleri Türkçe.

### 3a. Task özellikleri (`/task-change` skill'i)
- `services.create_task`:
  - `due_date` verilmezse SLA'ya göre atanır: Kritik 1 gün, Yüksek 3 gün, Orta 7 gün, Düşük 14 gün.
  - Ana ve yedek sorumlulara `Notification` oluşturulur (işlemi yapan kişi hariç). Mesaj: `"<Ad Soyad> size TSK-0012 işini atadı"`.
- `services.update_task`:
  - `due_date` ve `backup_assignee` değişikliklerini geçmişe yazar (Türkçe açıklama).
  - Yeni atanan kişilere bildirim gönderir.
- `visible_tasks`: Yedek sorumlu da task'ı görür. Durum değişikliğini ana sorumlu ve yedek sorumlu yapabilir.
- `Task` modeline `is_overdue` property'si: `due_date < now` ve durum Tamamlandı değil.
- Formlar ve template'ler:
  - `TaskForm`'a son tarih (`datetime-local`) ve yedek sorumlu alanları.
  - Liste ve detayda son tarih ile "Gecikmiş" rozeti; detayda yedek sorumlu.
  - `task_list` filtrelerine "Gecikmiş".
- Dashboard:
  - "Gecikmiş" istatistik kartı.
  - "Devralınan işler" bölümü: yedek sorumlusu olduğum ve ana sorumlusu izinli olan işler.
  - Profil formuna "İzinli" alanı.

### 3b. Bildirim, rapor, etkinlik (`/new-page` skill'i)
- **Bildirimler:**
  - `app.html` sidebar'ında okunmamış bildirim sayacı (context processor üzerinden).
  - `/notifications/` sayfası.
  - Okundu işaretleme ve tümünü okundu yapma (ikisi de POST).
- **Raporlar** (REPORT_ANALYSIS yetkisi):
  - `/reports/tasks.xlsx` (`openpyxl`) ve `/reports/tasks.pdf` (`reportlab`).
  - `task_list` filtreleriyle aynı filtreler, `visible_tasks` scope'u.
  - Kolonlar: Kod, Başlık, Durum, Önem, Sorumlular, Yedek, Son Tarih, Gecikmiş.
  - Hücre değerleri `=`, `+`, `-`, `@` ile başlıyorsa başına `'` eklenir (formül enjeksiyonu koruması).
  - PDF'te Türkçe karakterler için Unicode TTF font (ör. `/System/Library/Fonts/Supplemental/Arial Unicode.ttf`, yoksa DejaVu).
  - `task_list` sayfasında Excel/PDF butonları.
- **Etkinlik formu ve listesi:** tür, katılım şekli ve iletişim kişisi.
- **Direktör görünümü:** Tüm yetkilere sahip kullanıcı Ekibim'de herkesi görür.

### 3c. REST API + MCP (`/new-api-endpoint` skill'i)
`mcp/server.py` dosyasını **değiştirmeden** çalıştırmak için Django'ya salt okunur bir DRF API ekle.

**Kurulum ve kimlik doğrulama:**
- `djangorestframework` paketini `requirements.txt` dosyasına ekle.
- Auth: `rest_framework.authtoken`. MCP `Authorization: Bearer <token>` gönderdiği için `TokenAuthentication` sınıfını `keyword = 'Bearer'` ile alt sınıfla. `SessionAuthentication` da eklenebilir.
- Yetki: `IsAuthenticated` + DATA_ACCESS (`has_portal_perm`). Yalnızca `/api/me` bütün giriş yapmış kullanıcılara açık kalabilir.

**JSON yapıları:** `docs/api-contract.md` ile birebir aynı, camelCase.
- `UserRef = {id, username, displayName}`
- `TaskSummary = {id, code, title, status, severity, assignees, backupAssignee, dueDate, isOverdue, handover, modifiedDate}`

**Endpoint'ler** (MCP tool'larının kullandıkları):
- `GET /api/me`: `{id, username, displayName, title, permissions, managerId, isManager, isOnLeave}`
- `GET /api/users`: `UserRef[]`
- `GET /api/tasks?status=&severity=&q=&assigneeId=&overdue=true`: `TaskSummary[]`, `visible_tasks` ile scope edilir
- `GET /api/tasks/{id}`: TaskSummary + `description`, `createdBy`, `createDate`, `history[]` (`{actionType, actionDescription, actionBy, actionDate}`); görünmeyen task için 404
- `GET /api/dashboard`: `{stats:{pending,inProgress,done,overdue,critical,upcomingActivities}, pendingTasks, doneTasks, handoverTasks, myActivities, team|null, report|null}`
- `GET /api/team`: ROLE_MANAGEMENT yetkisi ister; `[{user, title, isOnLeave, permissions, openCount, progressCount, doneCount, overdueCount}]`
- `GET /api/activities?scope=upcoming|past|mine`: `[{id, name, description, date, location, type, participationType, contactPerson, createdBy, attendees, joined}]`

**Hata formatı:** `{"error": {"code", "message"}}` (custom DRF exception handler).

**Veri Paylaşımı sayfası** (DATA_ACCESS yetkisi):
- "Anahtar üret" butonu (POST + CSRF) ile kullanıcının token'ını oluştur veya yenile, sadece sahibine göster.
- Sayfada endpoint listesi ve MCP kullanım notu (`mcp/README.md`).

**MCP'yi bağlama ve test:**
- `.mcp.json.example` → `PORTAL_API_URL=http://127.0.0.1:8000`.
- Test:
  ```bash
  uv run --directory mcp server.py
  ```
  veya bir stdio istemcisiyle `whoami`, `overdue_tasks`, `team_summary` tool'larını çağır.
- `mcp/README.md` dosyasındaki adresi `:8000` olarak, token alma adımını da "Veri Paylaşımı → Anahtar üret" olarak güncelle.

## Adım 4 — Kontrol ve teslim
1. `cd hackatlon-django && .venv/bin/python manage.py makemigrations --check && .venv/bin/python manage.py test core`
   - Python 3.10+ gerekli: `uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt`.
   - Yeni sayfalar `PageRenderTests` içine eklenir.
2. `seed --reset` → `runserver` → demo akışı:
   1. `yonetici` kritik bir task açar (ana sorumlu mert, yedek alper); son tarih otomatik gelir.
   2. mert bildirimi görür, durumu Devam Ediyor → Tamamlandı yapar; geçmişte kayıtlar görünür.
   3. Dashboard'daki sayılar güncellenir, gecikmiş kartı görünür.
   4. Etkinlik ve yetkinlik eklenir.
   5. `berkay` (rapor yetkisi) Excel/PDF indirir.
   6. `mert` (Data Access) token üretir, MCP ile "geciken kritik işler" sorgulanır.
3. `security-reviewer` ve `code-reviewer` agent'larını paralel çalıştır, Kritik/Yüksek bulguları düzelt.
4. Küçük ve sık commit'ler at; kendi branch'ine push et, sonra `main`'e PR aç.

Önceliklendirme: Süre biterse sıra **3c (API + MCP) → 3a (son tarih, bildirim) → 3b (rapor)**. Çalışan bir özelliği yeniden yazma; mevcut desenlerin üzerine ekle.
