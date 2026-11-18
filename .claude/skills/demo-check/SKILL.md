---
name: demo-check
description: Demo veya merge öncesi tam kontrol. Temiz seed, testler, migration kontrolü, uçtan uca demo senaryosu ve güvenlik incelemesini sırayla çalıştırıp tek bir hazırlık raporu verir. "Demo hazır mı", "main'e merge etmeden önce kontrol et" gibi isteklerde kullan.
---

# Demo hazırlık kontrolü

`hackatlon-django/` içinde, sırayla:

1. **Ortam:** `.venv` yoksa `uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt`. `git status` temiz mi, `origin/main`'in gerisinde mi? (`git fetch && git status -sb`)
2. **Statik kontroller:**
   - `.venv/bin/python manage.py check`
   - `.venv/bin/python manage.py makemigrations --check --dry-run`: temiz olmalı.
   - `.venv/bin/python manage.py test core`: yeşil olmalı.
3. **Temiz veri:** `.venv/bin/python manage.py migrate && .venv/bin/python manage.py seed --reset`.
4. **Uçtan uca:** `qa-demo` agent'ını çalıştır (sunucuyu kendisi başlatır, rollerle curl senaryosunu koşar).
5. **Güvenlik:** `security-reviewer` agent'ını `git diff <son demo-check commit'i veya origin/main>...HEAD` kapsamıyla çalıştır. 4. ve 5. adım birbirinden bağımsız; ikisini paralel başlat.
6. **Rapor:**
   - Kontrol / sonuç tablosu.
   - FAIL olan demo adımları ve Kritik/Yüksek güvenlik bulguları en üstte.
   - Sonda tek satırlık hüküm: "Demo hazır" ya da "Bloklayan sorunlar: ...".

Bu skill kod değiştirmez. Düzeltmeleri kullanıcı onayıyla ayrıca yap.
