# mcp — Salt okunur MCP server (P3)

Amaç: Portal verisini (yetki sınırları içinde) başka uygulamalarda ve Claude'da görüntülemek. Minimum gereksinimlerdeki "Veri Paylaşımı: API veya MCP" maddesini karşılar.

## Kurallar
- **Bağımlılık:** Önce `hackatlon-django` içindeki REST API (`/api/...`, DRF, Token auth, DATA_ACCESS yetkisi) hazır olmalı.
- **DB'ye doğrudan erişim yok.** Server yalnızca REST API'yi `Authorization: Token <token>` ile çağırır; böylece yetki kuralları tek yerde kalır.
- Token ve API adresi env'den okunur: `PORTAL_API_URL`, `PORTAL_API_TOKEN`. Token commit edilmez.
- **Salt okunur.** Yazma tool'u eklenmez.
- **Teknoloji:** Python MCP SDK (`mcp` paketi, FastMCP) + `httpx`; stdio transport.

## Hedef tool'lar
- `list_tasks(status?, severity?, assignee?)`
- `overdue_tasks()`
- `team_summary()`: ekip üyesi başına açık / devam eden / biten sayıları
- `upcoming_activities(days=14)`

## Demo
Claude Code'da `.mcp.json` ile bağlanıp "Takımımın geciken kritik işleri neler?" sorusu sorulur.
