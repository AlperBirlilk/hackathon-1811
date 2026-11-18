---
name: add-mcp-tool
description: mcp/ altındaki MCP server'a, bir Java API endpoint'ini saran salt okunur bir tool ekler (Python MCP SDK / FastMCP + httpx, env PORTAL_API_URL / PORTAL_API_TOKEN). Portal verisinin Claude'da veya başka uygulamada sorgulanması gerektiğinde kullan.
---

# Salt okunur MCP tool'u

Argüman: tool'un amacı (ör. "geciken kritik task'lar").

1. **Endpoint:** `docs/api-contract.md` içinde karşılık gelen **GET** endpoint'ini bul. Yoksa önce `/new-backend-endpoint` ile Java'ya eklenir; MCP doğrudan DuckDB'ye bağlanmaz. Yazma endpoint'i sarılmaz.
2. **İlk kurulum** (`mcp/server.py` yoksa):
   - `mcp/requirements.txt`: `mcp`, `httpx`.
   - `server.py`:
     ```python
     import os, httpx
     from mcp.server.fastmcp import FastMCP

     API = os.environ.get("PORTAL_API_URL", "http://127.0.0.1:8080")
     TOKEN = os.environ["PORTAL_API_TOKEN"]
     mcp = FastMCP("cyberops-portal")

     def get(path: str, **params):
         r = httpx.get(f"{API}{path}", params={k: v for k, v in params.items() if v is not None},
                       headers={"Authorization": f"Bearer {TOKEN}"}, timeout=10)
         if r.status_code == 401:
             raise RuntimeError("Token geçersiz veya süresi dolmuş")
         if r.status_code >= 400:
             raise RuntimeError(r.json().get("error", {}).get("message", f"API hatası {r.status_code}"))
         return r.json()

     if __name__ == "__main__":
         mcp.run()  # stdio
     ```
3. **Tool:** `@mcp.tool()` ile fonksiyon; açık bir docstring (Claude tool'u buna göre seçer), tipli ve isteğe bağlı parametreler. `get(...)` ile endpoint'i çağır, yanıtı sade bir listeye/özete indir (gereksiz alanları at). Token'ı çıktıya veya log'a yazma.
4. **Yetki:** Scope Java'da uygulanır; tool kendi filtresiyle görünürlüğü genişletmez veya ek veri çekmez.
5. **Bağla ve dene:** Repo kökünde `.mcp.json`:
   ```json
   {"mcpServers": {"cyberops": {"command": "python", "args": ["mcp/server.py"],
     "env": {"PORTAL_API_URL": "http://127.0.0.1:8080", "PORTAL_API_TOKEN": "${PORTAL_API_TOKEN}"}}}}
   ```
   Java açıkken dev token ile (`/internal/dev/token`) dene; yetkisi az bir kullanıcının token'ıyla görünmeyen verinin dönmediğini kontrol et.
6. `mcp/CLAUDE.md` → "Hedef tool'lar" listesini güncelle.
