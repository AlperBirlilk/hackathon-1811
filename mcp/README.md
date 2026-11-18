# CyberOps Portal — Salt okunur MCP server

Portal verisini (kullanıcının yetki sınırları içinde) Claude Code / Claude Desktop gibi MCP istemcilerinde sorgulamak için. Server yalnızca Java backend'in (`hackatlon-be`) **GET** endpoint'lerini `Authorization: Bearer <JWT>` ile çağırır; veritabanına doğrudan erişmez, yazma işlemi yapmaz. Yetki ve görünürlük kuralları Java tarafında uygulanır.

Teknoloji: Python ≥3.10, resmi MCP SDK (FastMCP) + `httpx`, stdio transport.

## Token

`PORTAL_API_TOKEN` ortam değişkeni gereklidir:

- **Portal:** "Veri Paylaşımı" sayfasından token'ı kopyalayın (DATA_ACCESS yetkisi gerekir).
- **Geliştirme:** Java açıkken
  ```bash
  export PORTAL_API_TOKEN=$(curl -s -H 'X-Service-Key: dev-service-key' \
    'http://127.0.0.1:8080/internal/dev/token?username=yonetici' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')
  ```

`PORTAL_API_URL` varsayılan olarak `http://127.0.0.1:8080`'dir. Token commit edilmez, log'a yazılmaz.

## Çalıştırma

```bash
uv run --directory mcp server.py
# veya bağımlılıkları geçici kurarak:
uv run --with 'mcp<2' --with httpx mcp/server.py
```

## Claude Code'a ekleme

Seçenek 1 — proje config'i: repo kökündeki `.mcp.json.example` dosyasını `.mcp.json` olarak kopyalayın ve `PORTAL_API_TOKEN`'ı ortamda tanımlayın (dosyada `${PORTAL_API_TOKEN}` olarak okunur).

Seçenek 2 — CLI (repo kökünde):
```bash
claude mcp add cyberops-portal \
  -e PORTAL_API_URL=http://127.0.0.1:8080 \
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

Hatalar anlaşılır Türkçe metin olarak döner: token yoksa nasıl alınacağı, 401'de "token geçersiz veya süresi dolmuş", 403'te yetki mesajı, backend kapalıysa "Backend çalışmıyor (PORTAL_API_URL)". API hata formatı `{"error": {"code", "message"}}` mesajı aynen iletilir.

## Demo

Claude Code'da server bağlıyken:

1. **"Takımımın geciken kritik işleri neler?"** → `overdue_tasks` (+ gerekirse `team_summary`) çağrılır, Kritik işler sorumlularıyla listelenir.
2. **"Bu hafta hangi etkinlikler var?"** → `upcoming_activities` çağrılır, bu haftaya düşen eğitim/konferanslar tarih ve yerle özetlenir.

Ek örnek: "TSK-0012'nin geçmişinde neler değişti?" → `list_tasks(q="TSK-0012")` + `get_task`.
