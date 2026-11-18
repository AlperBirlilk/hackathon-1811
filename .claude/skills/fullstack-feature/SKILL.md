---
name: fullstack-feature
description: Ana full-stack akış. Kökten verilen "şu özelliği ekle" görevlerinde kullan. Sözleşme (docs/api-contract.md) → backend-dev ile Java endpoint'i ∥ frontend-dev ile api_client + view/template → iki sunucuyla curl uçtan uca test → security-reviewer ∥ code-reviewer.
---

# Full-stack özellik

Argüman: özelliğin tarifi (ör. "task'a yedek sorumlu ekle, bildirim gitsin").

1. **Kapsam:** Hangi katmanlar etkileniyor? Yalnızca biri ise bu skill yerine ilgili agent'ı çalıştır (`backend-dev` / `frontend-dev`). İş bölümü sahibini kontrol et (`docs/migration_plan.md`).
2. **Sözleşme:** `docs/api-contract.md` içinde bölümü yaz veya güncelle:
   - Metot + path, gereken yetki ve görünürlük kuralı.
   - İstek ve yanıt JSON örneği (alan adları, tipler, zorunluluk).
   - Hata kodları (`{"error": {"code", "message"}}`, 400/401/403/404).
   - `schema.sql` değişikliği gerekiyorsa (yalnızca eklemeli) not et ve ekibe duyurulacağını belirt.
3. **Paralel geliştirme:** `backend-dev` ve `frontend-dev` agent'larını **tek mesajda** başlat. İkisinin prompt'una da sözleşme bölümünü aynen koy.
   - `backend-dev`: `/new-backend-endpoint` adımları (Controller/Service/Repository, record DTO, MockMvc testi). Task davranışıysa `/task-change`.
   - `frontend-dev`: `api_client` fonksiyonu, view, URL, template, menü, test (`/new-page` adımları). Backend'i beklemez; testlerde `api_client` mock'lanır.
4. **Uçtan uca:** Java'yı, ardından Django'yu env'lerle başlat (root `CLAUDE.md` → Çalıştırma).
   - API: dev token ile yeni endpoint → beklenen JSON; token yok → 401; yetkisiz kullanıcı → 403/404.
   - Django: session + CSRF login (`qa-demo` agent'ındaki `login` yardımcısı) → sayfa 200, POST → 302 ve mesaj.
   - Sapma varsa ilgili agent'a düzelttir; sözleşme değişirse iki tarafı da güncelle.
5. **İnceleme:** `security-reviewer` ve `code-reviewer` agent'larını paralel çalıştır. Kritik/Yüksek bulguları düzelt, testleri tekrar koş.
6. **Rapor:** Sözleşme değişikliği, iki taraftaki dosyalar, `schema.sql` değişikliği, e2e sonuçları, inceleme hükmü. Sözleşme + iki tarafın kodu aynı PR'da gider.
