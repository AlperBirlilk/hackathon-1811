---
name: task-change
description: Task'a yeni bir alan veya davranış ekler (son tarih, SLA, yedek sorumlu, bildirim, devir gibi). İş kuralı Java TaskService'te (eklemeli schema kolonu, history action tipi, bildirim), arayüz Django form/template'inde. Task alanı, task formu veya task iş kuralı değişikliklerinde kullan.
---

# Task davranışı değiştirme

Task'ın sahibi Java backend'dir. Task yazma işlemleri yalnızca `hackatlon-be` → `task/TaskService` üzerinden yapılır; Django yalnızca formu ve gösterimi değiştirir. İki tarafa dokunuyorsa `/fullstack-feature` akışıyla (`backend-dev` ∥ `frontend-dev`) yürütülür.

1. **Sözleşme:** `docs/api-contract.md` → task bölümünde yeni alanı `POST /api/tasks`, `PATCH /api/tasks/{id}`, `GET` yanıtları ve (gerekiyorsa) history action tipi listesine ekle.
2. **Şema** (`schema.sql`, yalnızca eklemeli; önce ekibe duyur):
   ```sql
   ALTER TABLE task ADD COLUMN IF NOT EXISTS due_date DATE;
   ```
   Demo değerleri `data.sql`'e idempotent biçimde.
3. **Java:**
   - Record DTO'lar (`TaskDto`, `CreateTaskRequest`, `UpdateTaskRequest`) ve `TaskRepository` SQL'i (parametreli).
   - `TaskService`: yeni alan için değişiklik varsa ayrı bir dal; aynı `@Transactional` içinde `task_history` kaydı (yeni action tipi sabiti + Türkçe açıklama).
   - Atama/devir gibi kişiyi etkileyen değişiklikte aynı transaction'da `notification`; işlemi yapan kişiye kendi işlemi için bildirim gitmez.
   - Görünürlük kuralı değişiyorsa (ör. yedek sorumlu görür) scope sorgusunu tek yerde güncelle; liste, detay, dashboard ve export aynı kuralı kullanır.
   - MockMvc testi: alan yazılıyor, history kaydı oluşuyor, yetkisiz kullanıcı 403/404.
4. **Django:**
   - `core/api_client.py`: create/update payload'una alan.
   - `core/forms.py` → `TaskForm` alanı; `views.task_create` / `views.task_detail` içinde `initial` ve `api_client` çağrısı.
   - Template: `task_form.html`, `task_detail.html`, `task_list.html`; gerekiyorsa `dashboard.html`. Geçmişteki yeni action tipinin Türkçe etiketi.
5. **Doğrula:** `./mvnw test`, `manage.py test core`; iki sunucuyla task oluştur/güncelle, `/api/tasks/{id}/history` ve detay sayfasındaki geçmişte yeni kaydın Türkçe göründüğünü kontrol et.
