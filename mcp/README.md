# CyberOps Portal — Salt okunur MCP server

Portal verisini (kullanıcının yetki sınırları içinde) Claude Code / Claude Desktop gibi MCP istemcilerinde sorgulamak için. Server yalnızca Django REST API'sinin (`hackatlon-django`, `/api/...`) **GET** endpoint'lerini `Authorization: Bearer <token>` ile çağırır; veritabanına doğrudan erişmez, yazma işlemi yapmaz. Yetki ve görünürlük kuralları Django tarafında (`visible_tasks`, DATA_ACCESS) uygulanır.

Teknoloji: Python ≥3.10, resmi MCP SDK (FastMCP) + `httpx`, stdio transport.

## Token

`PORTAL_API_TOKEN` ortam değişkeni gereklidir:

1. Portala DATA_ACCESS yetkisi olan bir kullanıcıyla girin (demo: `mert` / `Cyber2026!`).
2. **Veri Paylaşımı → Anahtar üret** butonuna basın. Token yalnızca bu anda bir kez gösterilir; kopyalayın.
3. Token 24 saat geçerlidir (`API_TOKEN_TTL_HOURS`). Yeniden üretmek eskisini geçersiz kılar.

`PORTAL_API_URL` olarak `http://127.0.0.1:8000` verin (server.py'deki varsayılan `:8080` eski Java backend'inden kalmadır, env ile ezilir). Token commit edilmez, log'a yazılmaz.

> Not: `server.py` içindeki yardım/hata metinlerinde hâlâ "Java" ve `/internal/dev/token` geçiyor; davranış etkilenmez. Token için yukarıdaki adımları kullanın.

## Çalıştırma

```bash
pip install uv                      # bir kez (Windows dahil)
PORTAL_API_URL=http://127.0.0.1:8000 PORTAL_API_TOKEN=<token> uv run --directory mcp server.py
```
PowerShell:
```powershell
$env:PORTAL_API_URL="http://127.0.0.1:8000"; $env:PORTAL_API_TOKEN="<token>"; uv run --directory mcp server.py
```

## Claude Code'a ekleme

Seçenek 1 — proje config'i: repo kökündeki `.mcp.json.example` dosyasını `.mcp.json` olarak kopyalayın ve `PORTAL_API_TOKEN`'ı ortamda tanımlayın (dosyada `${PORTAL_API_TOKEN}` olarak okunur).

Seçenek 2 — CLI (repo kökünde):
```bash
claude mcp add cyberops-portal \
  -e PORTAL_API_URL=http://127.0.0.1:8000 \
  -e PORTAL_API_TOKEN=$PORTAL_API_TOKEN \
  -- uv run --directory "$(pwd)/mcp" server.py
```
Kontrol: `claude mcp list`.

## Tool'lar

| Tool | Endpoint | Açıklama |
|---|---|---|
| `whoami()` | `GET /api/me` | Token sahibi, yetkileri |
| `list_tasks(status?, severity?, q?, assignee_id?)` | `GET /api/tasks` | Görünür işler, filtreli |
| `overdue_tasks()` | `GET /api/tasks?overdue=true` | Geciken işler |
| `get_task(task_id)` | `GET /api/tasks/{id}` | Detay + değişiklik geçmişi |
| `dashboard_summary()` | `GET /api/dashboard` | İstatistikler, rapor dağılımı, bekleyen işler |
| `team_summary()` | `GET /api/team` | Ekip üyesi başına iş sayıları (ROLE_MANAGEMENT) |
| `upcoming_activities()` | `GET /api/activities?scope=upcoming` | Yaklaşan etkinlikler |
| `list_users()` | `GET /api/users` | Aktif kullanıcılar (id bulmak için) |

Tüm endpoint'ler DATA_ACCESS yetkisi ister (`/api/me` hariç). API hata formatı `{"error": {"code", "message"}}`; mesaj aynen iletilir.

## Demo

Claude Code'da server bağlıyken:

1. **"Takımımın geciken kritik işleri neler?"** → `overdue_tasks` (+ gerekirse `team_summary`) çağrılır, Kritik işler sorumlularıyla listelenir.
2. **"Bu hafta hangi etkinlikler var?"** → `upcoming_activities` çağrılır, bu haftaya düşen eğitim/konferanslar tarih ve yerle özetlenir.

Ek örnek: "TSK-0012'nin geçmişinde neler değişti?" → `list_tasks(q="TSK-0012")` + `get_task`.
