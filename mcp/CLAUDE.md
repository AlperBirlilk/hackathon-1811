# mcp — Salt okunur MCP server

Amaç: Portal verisini (yetki sınırları içinde) başka uygulamalarda ve Claude'da görüntülemek. Minimum gereksinimlerdeki "Veri Paylaşımı: API veya MCP" maddesini karşılar. Yeni tool için `/add-mcp-tool` skill'i.

## Kurallar
- **Kaynak:** Java API (`hackatlon-be`, `http://127.0.0.1:8080/api/...`). Endpoint'ler ve yanıt şekilleri `docs/api-contract.md` içinde.
- **DB'ye doğrudan erişim yok** (DuckDB dosyası tek süreçlidir, ayrıca yetki kuralları Java Service katmanında). Server yalnızca API'yi `Authorization: Bearer <JWT>` ile çağırır.
- Token ve adres env'den okunur: `PORTAL_API_URL` (varsayılan `http://127.0.0.1:8080`), `PORTAL_API_TOKEN` (Veri Paylaşımı sayfasındaki uzun ömürlü JWT; geliştirmede `/internal/dev/token`). Token commit edilmez, log'a yazılmaz.
- **Salt okunur.** Yazma tool'u eklenmez; yalnızca GET endpoint'leri sarılır.
- API hatası (`{"error": {"code", "message"}}`) tool çıktısına anlaşılır metin olarak döner; 401'de "token geçersiz veya süresi dolmuş" denir.
- **Teknoloji:** Python MCP SDK (`mcp` paketi, FastMCP) + `httpx`; stdio transport.

## Hedef tool'lar
- `list_tasks(status?, severity?, assignee?)` → `GET /api/tasks`
- `overdue_tasks()` → `GET /api/tasks?overdue=true` (sözleşmeye göre)
- `team_summary()` → `GET /api/team`: üye başına açık / devam eden / biten
- `upcoming_activities(days=14)` → `GET /api/activities`

## Demo
Claude Code'da `.mcp.json` ile bağlanıp "Takımımın geciken kritik işleri neler?" sorusu sorulur.
