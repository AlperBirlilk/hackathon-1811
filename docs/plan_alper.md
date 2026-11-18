# Plan — Alper (Django monolit tamamlama)

Hazırlanma: Adım 0 keşfi, `alper` branch'i `d38388f` ("fix") üzerinde. `origin/alper` ile aynı, çalışma alanı temiz.
Kaynaklar: `demo-django-v1` tag'i (`.claude` + dokümanlar), `origin/mert` (`mcp/server.py`, `docs/api-contract.md`).
**Onay gelmeden bu dosya dışında hiçbir şey değişmedi.**

---

## 1. Mevcut özelliklerim (Mert'in planı bunları bilmiyor)

| Alan | Durum | Not |
|---|---|---|
| LDAP login (`core/ldap_backend.py`) | ✅ | Upsert, `auth_source`, yerel hesap koruması, boş parola engeli, brute-force kilidi (hash'li cache key) |
| Yetkiler DB'den, `grant_perm` komutu | ✅ | |
| Light/dark tema, sade tasarım (`portal.css`, `portal.js`) | ✅ | Tema butonu sağ üstte |
| **Kanban dashboard** (Yapılacak / Devam ediyor / Tamamlandı) | ✅ | Sürükle-bırak ve ‹ › okları, `POST /tasks/<id>/status/` JSON, sayaçlar canlı güncellenir. "İşlerim" = atanan **veya oluşturan** |
| Aynı sayfada task oluşturma (AJAX), renkli önem seçici | ✅ | `task_create` JSON döner, "Son eklediklerim" listesi |
| **Toplu işlem** (`POST /tasks/bulk/`) | ✅ | Durum, önem, kişi ekle/çıkar; geçmişe yazılır, yetkisizler atlanır |
| Dağılım panelleri (önem / durum) | ✅ | `_distribution_panel.html`, tıklanınca filtreli liste |
| **E-posta bildirimi** (`core/notifications.py`) | ✅ | Task ataması ve etkinlik daveti; `mailTemplate.msg` şablonu, "Hackatlon Bilgilendirme" başlığı; gönderen `TEAM-SMA@smtp.turkcell.com.tr`; domain filtresi, test modu, `MAIL_NOTIFY_SELF=1` (kendine atayana da gider), `send_test_mail` komutu |
| SQLite WAL + timeout | ✅ | DB Browser açıkken kilitlenme olmaz |
| Testler | ✅ | 35 test (LDAP, sayfa render, kanban/AJAX, toplu işlem, mail) |

**Plandaki maddelerle karşılaştırma:**

| Plan maddesi | Durum | Karar |
|---|---|---|
| Bildirim | **Kısmen var**: e-posta var, uygulama içi `Notification` modeli yok | `Notification` modeli eklenir. `core/notifications.py` **tek giriş noktası** olur: hem DB bildirimi hem e-posta. Modül adı korunur |
| Dashboard istatistikleri / "İşlerim" | **Farklı tasarım**: kanban | Benimki korunur. Gecikmiş kartı ve "Devralınan işler" kanbana eklenir. API'deki `pendingTasks`/`doneTasks` kanban verisinden türetilir |
| Durum değişikliği yetkisi | Var (`can_change_status`: düzenleyen veya ana sorumlu) | Yedek sorumlu eklenir |
| `visible_tasks` | Var (atanan veya oluşturan) | Yedek sorumlu eklenir |
| Toplu işlem, AJAX create, JSON status | Planda yok, bende var | Korunur. Yeni alanlar (son tarih, yedek) bu akışlara da eklenir |
| Veri Paylaşımı sayfası | Sadece yer tutucu | Token üretme ve endpoint listesi eklenir |
| Etkinlik e-postası | Var | Yeni alanlar (tür, katılım, iletişim kişisi) maile de eklenir |

---

## 2. `.claude` ve doküman birleştirme önerisi (Adım 1)

Çakışma kontrolü: kökte `.claude/`, `CLAUDE.md`, `mcp/`, `docs/` **yok**. Yerelde sadece `hackatlon-django/.claude/settings.json` var (frontend-design eklentisi).

- `demo-django-v1` → `.claude/`, `CLAUDE.md`, `hackatlon-django/CLAUDE.md`, `docs/*`, `mcp/CLAUDE.md`: doğrudan alınır.
- `hackatlon-django/.claude/settings.json`: Tag bunu siliyor, kök `.claude/settings.json` aynı eklentiyi zaten içeriyor. **Öneri: silinsin** (yinelenen ayar).
- `hackatlon-django/img.png` → tag'de `docs/prototype-erd.png`; `main.py` (PyCharm örneği) siliniyor. **Öneri: tag'deki gibi.** Bunun için `git checkout demo-django-v1 -- hackatlon-django/core/models.py` yapılmaz; sadece docstring satırı elle güncellenir.
- Kök `.gitignore` (şu an Java şablonu) → tag'deki Python/Claude sürümü alınır, Java satırları korunur (`hackatlon-be` repoda).
- `origin/mert` → `mcp/server.py`, `mcp/pyproject.toml`, `mcp/uv.lock`, `mcp/README.md`, `.mcp.json.example`, `docs/api-contract.md` alınır.
  - `.mcp.json.example`: `PORTAL_API_URL` → `http://127.0.0.1:8000`.
  - `mcp/README.md` ve `mcp/CLAUDE.md`: adres `:8000`, token adımı "Veri Paylaşımı → Anahtar üret", `Authorization: Bearer`.
- `hackatlon-django/CLAUDE.md` (tag sürümü) benim eklemelerimle güncellenir: `notifications.py` (mail + bildirim), kanban/AJAX JSON deseni (`wants_json`), `task_bulk`, `safe_next`, Windows komutları (`myenv\Scripts\python.exe`).
- `.claude/settings.json` izinlerine Windows karşılıkları eklenir (`Bash(myenv/Scripts/python.exe manage.py:*)`).

Commit: `chore: import shared Claude setup and MCP server`

---

## 3. Tek migration: `0003` (Adım 2)

`core/models.py`:
- **Task**
  - `due_date = DateTimeField(null=True, blank=True)`
  - `backup_assignee = FK(User, null=True, blank=True, on_delete=SET_NULL, related_name='backup_tasks')`
  - `is_overdue` property: `due_date < now` ve durum DONE değil
  - `TaskHistory.ACTION_CHOICES` + `('due_date_change', 'Son Tarih Değişikliği')`, `('backup_change', 'Yedek Sorumlu Değişikliği')`
- **User**: `is_on_leave = BooleanField(default=False)`
- **Activity**
  - `activity_type`: TRAINING / CONFERENCE / OTHER (varsayılan OTHER)
  - `participation_type`: INDIVIDUAL / CORPORATE (varsayılan INDIVIDUAL)
  - `contact_person = FK(User, null=True, blank=True, SET_NULL, related_name='contact_activities')`
- **Notification** (yeni, `db_table='notification'`): `user` FK, `task` FK null, `message`, `is_read` (varsayılan False), `create_date` (auto_now_add); sıralama `-create_date`; index `(user, is_read)`.
- **Aynı migration içinde `RunPython`:** Son tarihi olmayan mevcut task'lara `create_date + SLA` atanır. Böylece gerçek DB'deki task'larınız (testTask, mailTest…) da tutarlı olur. Geri alınabilir (`noop` reverse).

Ayrıca aynı commit'te:
- `requirements.txt` + `djangorestframework`, `openpyxl`, `reportlab` (myenv'e kurulur)
- `INSTALLED_APPS` + `rest_framework`, `rest_framework.authtoken`
- `seed.py`:
  - `direktor` (tüm yetkiler); `yonetici.manager = direktor`
  - SLA'ya göre son tarihler, 2 açık task geçmiş tarihli (gecikmiş)
  - 3 task'a yedek sorumlu
  - Etkinliklere tür, katılım şekli, iletişim kişisi
  - Idempotent kalır (`update_or_create`)

`makemigrations --check` temiz → commit `feat(models): due date, backup assignee, leave, activity types, notifications` → **push**.

---

## 4. Yapılacaklar ve öncelik

Öncelik: **3c → 3a → 3b**.

### 3c. REST API + MCP (öncelik 1)
- Paket `core/api/`: `auth.py`, `permissions.py`, `serializers.py`, `views.py`, `urls.py`, `exceptions.py`.
- **Kimlik doğrulama:**
  - `BearerTokenAuthentication(TokenAuthentication)`: `keyword = 'Bearer'`.
  - Token yaşı `API_TOKEN_TTL_HOURS` (varsayılan 24) aşarsa 401.
  - `SessionAuthentication` da eklenir.
- **Yetki:**
  - `IsAuthenticated` + `HasDataAccess`; `/api/me` hariç.
  - `/api/team` ayrıca ROLE_MANAGEMENT ister.
  - Sadece GET (salt okunur).
- **Endpoint'ler** (sözleşmeyle aynı, camelCase):
  - `me`, `users`
  - `tasks` (`status`, `severity`, `q`, `assigneeId`, `overdue`): `visible_tasks` ile scope edilir, sıralama `SEVERITY_RANK` → `-modified_date`
  - `tasks/{id}`: + `description`, `createdBy`, `createDate`, `modifiedBy`, `canEdit`, `canChangeStatus`, `history[]`; görünmeyen → 404
  - `dashboard`: + `recentHistory`
  - `team`
  - `activities?scope=`
- `handover`: ana sorumlulardan biri izinli ve kullanıcı yedekse `true`.
- **Hata:** `{"error":{"code","message"}}` (custom handler; 401/403/404/400/500 eşlemesi).
- **Veri Paylaşımı sayfası:**
  - `POST /data-sharing/token/` + CSRF: token üretir veya yeniler; eski token geçersiz olur.
  - **Token yalnızca üretildiği anda bir kez gösterilir**, sonra maskelenir (`abcd…`).
  - Sayfada endpoint listesi, `.mcp.json` örneği ve "Token'ı sil" butonu.
- **MCP:**
  - `mcp/server.py` **değiştirilmez**. `PORTAL_API_URL=http://127.0.0.1:8000` ile çalışır.
  - Test: `whoami`, `overdue_tasks`, `team_summary` stdio istemcisiyle çağrılır.
- **Testler** (`core/test_api.py`):
  - Token yok → 401; DATA_ACCESS yok → 403
  - IDOR → 404; `/api/team` yetkisiz → 403
  - Görünürlük scope'u; JSON alan adları

### 3a. Task özellikleri (öncelik 2)
- `services.create_task(..., due_date=None, backup_assignee=None)`: SLA (Kritik 1g, Yüksek 3g, Orta 7g, Düşük 14g).
- `services.update_task`: `due_date` ve `backup_assignee` dalları geçmişe yazılır.
  - Örnek: `Son tarih: 20.11.2026 → 22.11.2026`, `Yedek sorumlu: — → Alper`.
- **Bildirim** (`notifications.notify_task_assigned`): Yeni ana ve yedek sorumlulara DB `Notification` kaydı (`"<Ad Soyad> size TSK-0012 işini atadı"`) + e-posta. Toplu atamada da çalışır.
- **`visible_tasks`, `can_change_status`:** + `backup_assignee`.
- **Form ve template'ler:**
  - `TaskForm`: `due_date` (datetime-local, boş = SLA) ve `backup_assignee` (tek seçim).
  - Önem seçicinin yanında "boş bırakılırsa SLA'ya göre" ipucu.
  - Liste ve detayda son tarih ile "Gecikmiş" rozeti; detayda yedek sorumlu.
  - Kanban kartında son tarih ve gecikmiş rozeti.
  - `task_list` filtresi: "Gecikmiş". Toplu işleme "Yedek sorumlu ata" eklenmez (kapsam dışı).
- **Dashboard:**
  - Özet şeridine "Gecikmiş" (5. kutu).
  - "Devralınan işler" paneli (yedeği olduğum ve ana sorumlusu izinli olan).
- **Profil:** `ProfileForm` + `is_on_leave` ("İzinliyim"); Ekibim'de ve profilde "İzinli" rozeti.
- **Direktör** (bkz. soru 1): Ekibim'de herkesi görür, herkesin profilini ve yetkilerini düzenleyebilir (yetki yükseltme koruması aynen geçerli); "Ekipten çıkar" sadece kendi ekibi için.
- **Testler:** `core/test_tasks.py`.

### 3b. Bildirim sayfası, rapor, etkinlik (öncelik 3)
- **Bildirimler:**
  - Context processor `unread_notifications`; sidebar'da sayaç rozeti.
  - `/notifications/` sayfası (son 50).
  - `POST /notifications/<id>/read/`, `POST /notifications/read-all/` (`safe_next` ile); bildirime tıklayınca task detayına gider.
- **Raporlar** (`@portal_perm_required(REPORT_ANALYSIS)`):
  - `core/reports.py` + `/reports/tasks.xlsx`, `/reports/tasks.pdf`.
  - `task_list` ile aynı filtreler + `overdue`, `visible_tasks` scope'u.
  - Kolonlar: Kod, Başlık, Durum, Önem, Sorumlular, Yedek, Son Tarih, Gecikmiş.
  - Formül enjeksiyonu: `= + - @` (ve `\t`, `\r`) ile başlayan değerlerin başına `'` eklenir.
  - Dosya adı sabit: `gorev-raporu-YYYYMMDD.xlsx`.
  - PDF fontu: `C:\Windows\Fonts\arial.ttf` → DejaVu → macOS Arial Unicode (sırayla denenir, bulunamazsa Helvetica + uyarı).
  - `task_list`'te "Excel" / "PDF" butonları (mevcut filtre query'siyle).
- **Etkinlik:**
  - `ActivityForm` + tür, katılım şekli, iletişim kişisi.
  - Listede tür ve katılım rozeti, iletişim kişisi.
  - Mail içeriğine eklenir.
- **Testler:** `core/test_reports.py`
  - Yetkisiz → 403
  - Formül enjeksiyonu
  - Scope (görünmeyen task raporda yok)
  - PDF/XLSX içerik tipi

---

## 5. Paralel subagent dağılımı (Adım 3)

Agent'lar (`django-dev`, `template-dev`, …) Claude yeniden başlatılınca görünür; görünmezse `general-purpose` kullanılır. Hepsi aynı çalışma alanında çalışır, **dosya sahipliği ayrık** tutulur:

| Agent | İş | Sahip olduğu dosyalar |
|---|---|---|
| **A** `django-dev` | 3c API + MCP + Veri Paylaşımı | `core/api/**`, `config/urls.py`, `settings.py` (yalnızca `REST_FRAMEWORK` bloğu), `templates/core/data_sharing.html`, `core/test_api.py`, `mcp/README.md`, `.mcp.json.example`; `core/urls.py`'de yalnızca `data-sharing` satırları |
| **B** `django-dev` | 3a task + direktör + profil | `core/services.py`, `core/views.py`, `core/forms.py` (`TaskForm`, `ProfileForm`), `core/notifications.py`, `templates/core/{task_*,dashboard,profile,team}.html`, `static/**`, `core/test_tasks.py` |
| **C** `template-dev` | 3b bildirim sayfası + rapor + etkinlik | `core/reports.py`, `core/report_views.py`, `core/notification_views.py`, `core/context_processors.py`, `templates/app.html`, `templates/core/{notifications,activity_*}.html`, `forms.py` içinde yalnızca `ActivityForm`, `core/test_reports.py`; `core/urls.py`'de yalnızca kendi satırları |
| **Ana oturum** | Adım 1-2, entegrasyon | Model/migration/seed, `requirements.txt`, `INSTALLED_APPS`, `task_list` export butonları, `hackatlon-django/CLAUDE.md`, son test ve demo, review düzeltmeleri |

`core/tests.py` dokunulmadan kalır. Yeni sayfalar `PageRenderTests`'e entegrasyonda eklenir.

---

## 6. Riskler

1. **`seed --reset` gerçek verinizi siler:** Demo akışı `seed --reset` istiyor; DB'deki LDAP kullanıcılarınızın task ve etkinlikleri (testTask, mailTest…) gider. Kullanıcılar ve yetkiler kalır. → Soru 3.
2. **Direktör tanımı çakışması:** "Tüm yetkiler = direktör" kuralına göre `yonetici` de tüm yetkilere sahip olduğu için direktör sayılır ve herkesi görür; hiyerarşi demosu bozulur. `tcalbirlik` de tüm yetkili olduğu için direktör olur. → Soru 1.
3. **Bildirim "kendine" kuralı:** Sözleşme "işlemi yapana bildirim gitmez" diyor, siz e-postada tersini istediniz. → Soru 2.
4. **`uv` kurulu değil (Windows):** `.mcp.json.example` `uv run` kullanıyor. → Soru 4.
5. **`mcp/server.py` metinleri Java'yı anlatıyor:** Hata ve yardım mesajlarında "Java sunucusu", `:8080` ve `/internal/dev/token` geçiyor. Kod `PORTAL_API_URL` ile doğru çalışır, sadece metinler yanıltıcı. Talimat "değiştirme" dediği için **dokunulmaz**; doğru kullanım README'ye yazılır.
6. **DRF `authtoken` token'ı DB'de düz metin tutar:** Önlemler 24 saatlik TTL, tek seferlik gösterim, yenileyince eskisinin geçersiz olması ve pasif kullanıcının reddedilmesi. Hash'li token kapsam dışı (süre).
7. **Kural ihlali:** `templates/emails/notification.txt` `{% autoescape off %}` kullanıyor; şablon kuralı bunu yasaklıyor. → Düz metin gövdesi Python'da üretilir, `.txt` şablonu kaldırılır (davranış aynı).
8. **Paralel agent çakışması:** `core/urls.py` ve `forms.py` iki agent tarafından düzenleniyor (ayrık satırlar). Edit aracıyla küçük çakışma riski var; entegrasyonda `manage.py check` + testlerle doğrulanır.
9. **Takım arkadaşlarıyla migration çakışması:** `0003` üretilmeden önce `git pull origin main` yapılır; başkası `0003` ürettiyse yeniden numaralanır.
10. **Komut yolları:** Plan `.venv/bin/python` (macOS) diyor; burada `myenv\Scripts\python.exe` (Python 3.10, yeterli) kullanılır.
11. **Mail gönderimi demo sırasında:** Seed task'ları `@cyberops.local` adreslerine atanır, domain filtresi bunları zaten atlar. Gerçek LDAP kullanıcılarına atama yapılırsa gerçek mail gider (beklenen davranış).

---

## 7. Kararlar (Alper'in yanıtları)

1. **Direktör = tüm yetkiler.** Seed'de `yonetici`'den DATA_ACCESS çıkarılır; `direktor` ve `tcalbirlik` direktör olur.
2. **Kendine atama:** Uygulama içi bildirim gitmez, e-posta `MAIL_NOTIFY_SELF=1` ile gider.
3. **Seed:** Önce `db.sqlite3` yedeklenir (`db.backup-<tarih>.sqlite3`, gitignore'da), sonra `seed --reset`.
4. **MCP:** `pip install uv`; `.mcp.json.example` aynen kalır (sadece URL `:8000`).

<details><summary>Sorulan sorular ve seçenekler</summary>

1. **Direktör nasıl belirlensin?**
   - (a) Tüm yetkiler = direktör (sözleşmeye uyar), `yonetici`'den DATA_ACCESS çıkarılır **(önerilen)**
   - (b) Yönetici zincirinin tepesi (yöneticisi olmayan + ROLE_MANAGEMENT)
   - (c) Ayrı `is_director` alanı (migration'a eklenir)
2. **Kendine atamada bildirim:**
   - (a) Uygulama içi bildirim gitmez (sözleşme), e-posta mevcut `MAIL_NOTIFY_SELF=1` ile gider **(önerilen)**
   - (b) İkisi de gitmez
   - (c) İkisi de gider
3. **`seed --reset` ve gerçek veri:**
   - (a) Önce `db.sqlite3` yedeği (`db.backup-<tarih>.sqlite3`, gitignore'da), sonra reset **(önerilen)**
   - (b) Reset yok, seed sadece eksikleri ekler
   - (c) Yedeksiz reset
4. **MCP çalıştırma:**
   - (a) `pip install uv` (kullanıcı ortamına), `.mcp.json.example` aynen kalır **(önerilen)**
   - (b) `mcp/.venv` + `python server.py`, örnek config'e Windows alternatifi eklenir

</details>

Varsayılan kararlar (itiraz yoksa böyle):
- Token TTL 24 saat, tek seferlik gösterim
- `hackatlon-django/.claude/settings.json` silinir
- `img.png` → `docs/`, `main.py` silinir
- `notification.txt` → Python'da düz metin
- Mevcut task'lara SLA backfill
- Work branch `alper` → `main`'e PR
