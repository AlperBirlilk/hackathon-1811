---
name: demo-check
description: Demo veya merge öncesi tam kontrol. Java ve Django testleri, iki sunucunun ayağa kalkması, uçtan uca demo senaryosu (qa-demo) ve güvenlik incelemesini (security-reviewer) çalıştırıp tek bir hazırlık raporu verir. "Demo hazır mı", "main'e merge etmeden önce kontrol et" gibi isteklerde kullan.
---

# Demo hazırlık kontrolü

Sırayla:

1. **Ortam:**
   - `git status` temiz mi, `origin/main`'in gerisinde mi? (`git fetch && git status -sb`)
   - `PORTAL_JWT_SECRET`, `PORTAL_SERVICE_KEY`, `PORTAL_API_URL` tanımlı mı? (Değerleri yazdırma.)
   - Django `.venv` yoksa `uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt`.
2. **Statik kontroller ve testler:**
   - `cd hackatlon-be && ./mvnw test`: yeşil olmalı.
   - `cd hackatlon-django && .venv/bin/python manage.py check && .venv/bin/python manage.py test core`: yeşil olmalı.
   - `git diff origin/main -- hackatlon-be/src/main/resources/schema.sql`: yalnızca eklemeli değişiklik mi?
   - Django'da domain migration'ı eklenmemiş olmalı.
3. **Sunucular:** Java (`./mvnw spring-boot:run`, `:8080`, `/v3/api-docs` 200), ardından Django (`runserver`, `:8000`). `qa-demo` bunu kendisi de yapabilir.
4. **Uçtan uca:** `qa-demo` agent'ını çalıştır (Django tarayıcı akışı + dev token ile API + negatif yetki testleri).
5. **Güvenlik:** `security-reviewer` agent'ını `git diff <son demo-check commit'i veya origin/main>...HEAD` kapsamıyla çalıştır. 4. ve 5. adım bağımsız; ikisini **paralel** başlat.
6. **Rapor:**
   - Kontrol / sonuç tablosu.
   - FAIL olan demo adımları ve Kritik/Yüksek güvenlik bulguları en üstte.
   - Sonda tek satırlık hüküm: "Demo hazır", "Bloklayan sorunlar: ..." ya da Java akışı çalışmıyorsa "Fallback: `demo-django-v1` tag'inden sunum".

Bu skill kod değiştirmez. Düzeltmeleri kullanıcı onayıyla ayrıca yap.
