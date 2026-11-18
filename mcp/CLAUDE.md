# mcp — Salt okunur MCP server

Amaç: Portal verisini (yetki sınırları içinde) başka uygulamalarda ve Claude'da görüntülemek. Minimum gereksinimlerdeki "Veri Paylaşımı: API veya MCP" maddesini karşılar.

## Kurallar
- **Bağımlılık:** `hackatlon-django` içindeki REST API (`/api/...`, DRF, Bearer token, DATA_ACCESS yetkisi). Adres: `http://127.0.0.1:8000`.
- **DB'ye doğrudan erişim yok.** Server yalnızca REST API'yi `Authorization: Bearer <token>` ile çağırır; böylece yetki kuralları tek yerde kalır.
- Token ve API adresi env'den okunur: `PORTAL_API_URL=http://127.0.0.1:8000`, `PORTAL_API_TOKEN` (portal → Veri Paylaşımı → Anahtar üret). Token commit edilmez.
- **Salt okunur.** Yazma tool'u eklenmez.
- **Teknoloji:** Python MCP SDK (`mcp` paketi, FastMCP) + `httpx`; stdio transport. Çalıştırma: `uv run --directory mcp server.py`.
- JSON sözleşmesi: `docs/api-contract.md` (camelCase alan adları). Django API bu yapıları birebir döndürür.

## Tool'lar
`whoami`, `list_tasks`, `overdue_tasks`, `get_task`, `dashboard_summary`, `team_summary`, `upcoming_activities`, `list_users` (bkz. `mcp/README.md`).

## Demo
Claude Code'da `.mcp.json` ile bağlanıp "Takımımın geciken kritik işleri neler?" sorusu sorulur.
