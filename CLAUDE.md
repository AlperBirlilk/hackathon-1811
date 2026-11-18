# CyberOps Portal — Hackathon Monorepo

Siber güvenlik ekipleri için task, etkinlik, yetkinlik ve yetki yönetimi portalı. 4 kişilik ekip, paralel Claude Code oturumlarıyla çalışıyor.

## Repo haritası
| Yol | İçerik |
|---|---|
| `hackatlon-django/` | **Ana uygulama.** Django 5.2 monolit, server-rendered template'ler, SQLite + ORM, tek app `core`. Detay: `hackatlon-django/CLAUDE.md` |
| `mcp/` | Salt okunur MCP server; Django `/api/...` endpoint'lerini Bearer token ile çağırır. Detay: `mcp/CLAUDE.md` |
| `docs/` | Gereksinimler, takım kararları, ERD'ler, **iş listesi ve sahipler: `docs/claude_setup_plan.md`** |
| `.claude/` | Ortak agent, skill, rule ve izinler (repoda tutulur) |

## Çalıştırma (Python 3.10+ zorunlu; macOS sistem Python 3.9 çalışmaz)
```bash
cd hackatlon-django
uv venv -p 3.12 .venv && uv pip install -p .venv/bin/python -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed            # --reset: task/etkinlikleri sıfırlar
.venv/bin/python manage.py runserver        # http://127.0.0.1:8000
.venv/bin/python manage.py test core        # her PR öncesi yeşil olmalı
```
Windows: `.venv/bin/python` yerine `myenv\Scripts\python.exe` (veya kendi venv'iniz). MCP: `pip install uv` sonrası `uv run --directory mcp server.py`.

Demo hesapları (parola `Cyber2026!`): `direktor` (tüm yetkiler, herkesi görür), `yonetici` (Data Access hariç tüm yetkiler, `direktor`'e bağlı), `alper` (Task Mgmt), `berkay` (Report), `aykun` (Activity), `mert` (Data Access), `admin` (superuser).

## Ekip kuralları
- **Çalışan kodu yeniden yazma.** Demo yakın; mevcut desenlerin üzerine ekleme yap.
- **Dil:** Arayüz metinleri Türkçe; kod, değişken adları ve commit mesajları İngilizce.
- **Branch:** Kendi branch'inde çalış (`mert`, `alper`, `berkay`, `aykun` veya `feat/<kişi>-<konu>`), küçük ve sık PR'larla `main`'e gönder. Başlamadan önce `git pull origin main`.
- **Migration koordinasyonu (kritik):** Tek bir `core` app'i var. Model değiştirmeden önce ekibe haber ver, sonra `git pull` → `makemigrations` → hemen commit ve push. İki kişinin aynı anda migration üretmesi çakışma demektir. PR öncesi `makemigrations --check` temiz olmalı.
- **Kapsam:** Sahip olduğun özelliğe odaklan (`docs/claude_setup_plan.md` içindeki tablo). Başkasının dosyasında büyük değişiklik gerekiyorsa önce sor.
- **`requirements.txt`:** Paket eklerken tek satır ekle ve hemen push et; satır çakışmalarına dikkat.

## Claude yapısı
- **Agent'lar** (`.claude/agents/`):
  - `django-dev`: backend
  - `template-dev`: arayüz
  - `security-reviewer`, `code-reviewer`: salt okunur, PR öncesi
  - `qa-demo`: uçtan uca demo doğrulaması
- **Skill'ler:**
  - `/new-page`: yeni ekran
  - `/task-change`: task davranışı
  - `/new-api-endpoint`: REST API
  - `/demo-check`: demo öncesi tam kontrol
- **Kurallar** (`.claude/rules/`): Python, template ve güvenlik kuralları; ilgili dosyalara dokunulduğunda otomatik yüklenir.
- **Kişisel ayarlar** `.claude/settings.local.json` ve `CLAUDE.local.md` dosyalarına yazılır; ikisi de gitignore'da.
