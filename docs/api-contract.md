# API Sözleşmesi — Java Backend (`hackatlon-be`, :8080)

Tek doğruluk kaynağı. Endpoint, alan veya yetki kuralı değişiyorsa bu dosya **backend ve frontend koduyla aynı PR'da** güncellenir.

## Genel kurallar
- Base URL: `PORTAL_API_URL` (varsayılan `http://127.0.0.1:8080`). JSON alanları **camelCase**. Tarihler ISO-8601 (`2026-11-18T15:30:00+03:00`).
- **Kimlik doğrulama:**
  - `/api/**`: `Authorization: Bearer <JWT>`. JWT HS256 ile `PORTAL_JWT_SECRET` kullanılarak imzalanır. Claim'ler: `sub` = kullanıcı id'si (string), `username`, `exp`.
  - `/internal/**`: `X-Service-Key: <PORTAL_SERVICE_KEY>`. Yalnızca Django çağırır, dışarıya açılmaz.
- **Yetki:** Kullanıcının yetkileri her istekte DuckDB'den okunur (JWT claim'ine güvenilmez). Kodlar: `TASK_MANAGEMENT`, `ACTIVITY_MANAGEMENT`, `ROLE_MANAGEMENT`, `REPORT_ANALYSIS`, `DATA_ACCESS`.
- **Task görünürlüğü:** TASK_MANAGEMENT yetkisi olan kullanıcı tüm task'ları görür. Diğerleri yalnızca ana sorumlusu, yedek sorumlusu ya da oluşturanı oldukları task'ları görür. Görünmeyen bir task'a erişim **404** döner (varlığı sızdırılmaz).
- **Hata formatı:** `{"error": {"code": "NOT_FOUND|FORBIDDEN|VALIDATION|UNAUTHORIZED|INTERNAL", "message": "Türkçe açıklama"}}`. JWT yoksa veya geçersizse 401.
- **Liste yanıtları:** sayfalama yok (demo ölçeği), düz dizi döner.

## Ortak tipler
```jsonc
// UserRef
{ "id": 2, "username": "mert", "displayName": "Mert Demir" }

// Enum'lar (değer → TR etiket; etiketler Django'da gösterilir)
// TaskStatus:   OPEN (Açık) | IN_PROGRESS (Devam Ediyor) | DONE (Tamamlandı)
// TaskSeverity: LOW (Düşük) | MEDIUM (Orta) | HIGH (Yüksek) | CRITICAL (Kritik)
// SLA (dueDate verilmezse createDate'e eklenir): CRITICAL 1g, HIGH 3g, MEDIUM 7g, LOW 14g
// ActivityType: TRAINING (Eğitim) | CONFERENCE (Konferans) | OTHER (Diğer)
// ParticipationType: INDIVIDUAL (Bireysel) | CORPORATE (Kurumsal)
// SkillKind: SKILL (Yetenek) | CERTIFICATE (Sertifika)
// HistoryAction: created | status_change | description_change | assignment_change | severity_change | due_date_change
```

## Internal (Django → Java)

### `POST /internal/users/sync`
LDAP veya yerel login başarılı olduktan sonra Django tarafından çağrılır. Kullanıcı yoksa oluşturur, varsa ad, soyad ve e-postasını günceller (upsert).
```jsonc
// istek
{ "username": "mert", "firstName": "Mert", "lastName": "Demir", "email": "mert@cyberops.local", "authSource": "LOCAL" }
// 200 yanıt  (= Me)
{ "id": 2, "username": "mert", "displayName": "Mert Demir", "title": "SOC Analyst L2",
  "permissions": ["DATA_ACCESS"], "managerId": 1, "isManager": false, "isOnLeave": false }
```
Pasif kullanıcı için 403 döner.

### `GET /internal/dev/token?username=yonetici` (yalnızca geliştirme)
`{ "token": "<jwt>", "user": Me }`. curl testleri ve MCP demosu için.

## Kullanıcı ve ekip

| Metot | Yol | Yetki | Açıklama |
|---|---|---|---|
| GET | `/api/me` | login | `Me` (yukarıdaki yapı) |
| GET | `/api/users` | login | Aktif kullanıcılar `UserRef[]`; atama ve katılımcı seçimi için |
| GET | `/api/users/{id}` | kendisi, yöneticisi veya ROLE_MANAGEMENT | `Profile` |
| PATCH | `/api/users/me` | login | Kendi profilini günceller: `{firstName,lastName,title,department,location,email,phone,bio,isOnLeave}` |
| GET | `/api/users/{id}/skills` | `/api/users/{id}` ile aynı | `Skill[]` |
| POST | `/api/users/me/skills` | login | `{skillName, kind}` → 201 `Skill` |
| DELETE | `/api/users/me/skills/{skillId}` | yalnızca sahibi | 204 |
| GET | `/api/team` | ROLE_MANAGEMENT | `TeamMember[]`: `manager_id = me`; direktör (tüm yetkiler) herkesi görür |
| GET | `/api/team/candidates` | ROLE_MANAGEMENT | Yöneticisi olmayan aktif kullanıcılar `UserRef[]` |
| POST | `/api/team/members` | ROLE_MANAGEMENT | `{userId}` → ekibe ekler (yalnızca yöneticisi olmayan kullanıcı) |
| DELETE | `/api/team/members/{userId}` | ROLE_MANAGEMENT, üye kendi ekibinde | 204 |
| GET | `/api/team/members/{userId}/permissions` | ROLE_MANAGEMENT, üye kendi ekibinde | `PermissionRow[]` |
| PUT | `/api/team/members/{userId}/permissions` | ROLE_MANAGEMENT, üye kendi ekibinde | `{codes: [...]}`. **Yalnızca çağıranın sahip olduğu yetkiler verilip geri alınabilir** (yetki yükseltme koruması). Yanıt `PermissionRow[]` |

```jsonc
// Profile
{ "id": 2, "username": "mert", "firstName": "Mert", "lastName": "Demir", "displayName": "Mert Demir",
  "email": "...", "title": "...", "department": "...", "phone": "...", "location": "...", "bio": "...",
  "manager": UserRef|null, "isOnLeave": false, "permissions": ["DATA_ACCESS"] }
// Skill
{ "id": 10, "skillName": "OSCP", "kind": "CERTIFICATE", "createDate": "..." }
// TeamMember
{ "user": UserRef, "title": "...", "isOnLeave": false, "permissions": ["..."],
  "openCount": 3, "progressCount": 1, "doneCount": 2, "overdueCount": 1 }
// PermissionRow
{ "code": "TASK_MANAGEMENT", "name": "Task Management", "granted": true, "grantable": true }
```

## Task'lar

| Metot | Yol | Yetki | Açıklama |
|---|---|---|---|
| GET | `/api/tasks?status=&severity=&q=&assigneeId=&overdue=true` | login (görünürlük kuralı) | `TaskSummary[]`: önce önem derecesi (Kritik önce), sonra `modifiedDate` azalan |
| POST | `/api/tasks` | login. TASK_MANAGEMENT yetkisi yoksa yalnızca kendine atayabilir (`assigneeIds = [me]`) | `TaskCreate` → 201 `TaskDetail` |
| GET | `/api/tasks/{id}` | görünürlük | `TaskDetail` (`history` dahil) |
| PATCH | `/api/tasks/{id}` | TASK_MANAGEMENT veya oluşturan | `TaskCreate` alanlarının herhangi biri → `TaskDetail` |
| POST | `/api/tasks/{id}/status` | düzenleyebilen, ana veya yedek sorumlu | `{status}` → `TaskDetail` |
| GET | `/api/tasks/{id}/history` | görünürlük | `HistoryEntry[]` (yeniden eskiye) |

İş kuralları (TaskService):
- **Geçmiş:** Her değişiklik, aynı transaction içinde alan başına bir `task_history` satırı yazar. Açıklama Türkçe olur, ör. `Durum: Açık → Devam Ediyor`.
- **Bildirim:** Yeni atanan her ana ve yedek sorumluya bildirim gönderilir (`"<Ad> size TSK-0012 işini atadı"`). İşlemi yapan kişinin kendisine bildirim gitmez.
- **Son tarih:** `dueDate` verilmezse SLA'ya göre otomatik atanır.
- **Yedek sorumluya devir:** Ana sorumlulardan en az biri izinliyse (`isOnLeave`) `TaskSummary.handover = true` olur ve task yedek sorumlunun "İşlerim" listesinde öne çıkar.

```jsonc
// TaskCreate
{ "title": "Kritik zafiyetin giderilmesi", "description": "...", "severity": "CRITICAL", "status": "OPEN",
  "assigneeIds": [2, 3], "backupAssigneeId": 4, "dueDate": null }
// TaskSummary
{ "id": 12, "code": "TSK-0012", "title": "...", "status": "OPEN", "severity": "CRITICAL",
  "assignees": [UserRef], "backupAssignee": UserRef|null, "dueDate": "...", "isOverdue": false,
  "handover": false, "modifiedDate": "..." }
// TaskDetail = TaskSummary + 
{ "description": "...", "createdBy": UserRef, "createDate": "...", "modifiedBy": UserRef,
  "canEdit": true, "canChangeStatus": true, "history": [HistoryEntry] }
// HistoryEntry
{ "id": 1, "actionType": "status_change", "actionDescription": "Durum: Açık → Devam Ediyor",
  "actionBy": UserRef, "actionDate": "..." }
```

## Dashboard

### `GET /api/dashboard`
Bölümlerin görünürlüğü yetkiye bağlıdır.
```jsonc
{
  "stats": { "pending": 4, "inProgress": 2, "done": 7, "overdue": 1, "critical": 2, "upcomingActivities": 3 },
  "pendingTasks": [TaskSummary],          // benim, açık + devam eden, max 8, Kritik önce
  "doneTasks": [TaskSummary],             // benim, max 8
  "handoverTasks": [TaskSummary],         // yedek sorumlusu olduğum ve ana sorumlusu izinli olan işler
  "myActivities": [ActivitySummary],      // yaklaşan, max 6
  "team": [TeamMember] | null,            // ROLE_MANAGEMENT
  "report": {                             // REPORT_ANALYSIS, yoksa null
    "bySeverity": [{ "key": "CRITICAL", "count": 3, "percent": 30 }],
    "byStatus":   [{ "key": "OPEN", "count": 4, "percent": 40 }]
  } | null,
  "recentHistory": [HistoryEntry & { "task": { "id": 12, "code": "TSK-0012", "title": "..." } }]  // görünür task'lar, max 8
}
```

## Etkinlikler

| Metot | Yol | Yetki | Açıklama |
|---|---|---|---|
| GET | `/api/activities?scope=upcoming\|past\|mine` | login | `ActivitySummary[]` (past: son 10) |
| POST | `/api/activities` | ACTIVITY_MANAGEMENT | `ActivityCreate` → 201 `ActivitySummary` |
| POST | `/api/activities/{id}/join` | login | Katılımı aç/kapat (toggle) → `{ "joined": true }` |

```jsonc
// ActivityCreate
{ "name": "OWASP Konferansı", "description": "...", "date": "...", "location": "...",
  "type": "CONFERENCE", "participationType": "CORPORATE", "contactPersonId": 1, "attendeeIds": [2,3] }
// ActivitySummary
{ "id": 5, "name": "...", "description": "...", "date": "...", "location": "...", "type": "CONFERENCE",
  "participationType": "CORPORATE", "contactPerson": UserRef|null, "createdBy": UserRef,
  "attendees": [UserRef], "joined": true }
```

## Bildirimler

| Metot | Yol | Yetki | Açıklama |
|---|---|---|---|
| GET | `/api/notifications?unread=true` | login (yalnızca kendi bildirimleri) | `Notification[]` (yeniden eskiye, max 20) |
| GET | `/api/notifications/unread-count` | login | `{ "count": 3 }`; navbar sayacı için |
| POST | `/api/notifications/{id}/read` | yalnızca sahibi | 204 |
| POST | `/api/notifications/read-all` | login | 204 |

```jsonc
// Notification
{ "id": 1, "message": "Selin Kaya size TSK-0012 işini atadı", "task": { "id": 12, "code": "TSK-0012" } | null,
  "isRead": false, "createDate": "..." }
```

## Raporlar (REPORT_ANALYSIS)

| Metot | Yol | Açıklama |
|---|---|---|
| GET | `/api/reports/tasks.xlsx?status=&severity=&assigneeId=&overdue=` | Excel. Filtreler `/api/tasks` ile aynı ve görünürlük kuralı geçerli. Hücre değerleri formül enjeksiyonuna karşı temizlenir |
| GET | `/api/reports/tasks.pdf?…` | Aynı filtrelerle basit tablo PDF'i |

`Content-Disposition: attachment; filename="gorev-raporu-YYYYMMDD.xlsx"`. Django bu yanıtı akış (stream) olarak tarayıcıya iletir.

## MCP için (`DATA_ACCESS`)
MCP server, kullanıcının "Veri Paylaşımı" sayfasından aldığı JWT ile yukarıdaki salt okunur endpoint'leri çağırır (`/api/tasks`, `/api/tasks?overdue=true`, `/api/team`, `/api/activities`). Ek bir kural: DATA_ACCESS yetkisi olmayan kullanıcıya Django uzun ömürlü token üretmez.
