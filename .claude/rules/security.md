# Güvenlik kuralları (tüm repo)

Bu bir siber güvenlik ürünü; jüri güvenlik açıklarına özellikle bakacak.

## Genel
- **Yetki:** Her endpoint (HTML, export, REST API, MCP) sunucu tarafında yetki kontrol eder ve veriyi aynı kurallarla scope eder. Export ve API, ekranda görülemeyen veriyi döndürmez.
- **IDOR:** ID ile nesne erişimi her zaman scope edilmiş sorgu üzerinden yapılır; görünmeyen kayıt 404.
- **Yetki yükseltme:** Bir kullanıcı sahip olmadığı yetkiyi başkasına veremez. Yeni rol veya yetki akışları da bu kurala uyar.
- **CSRF / metot:** Django'da durum değiştiren işlemler POST ve CSRF korumalıdır. Java API Bearer token ile çalışır (cookie yok), bu yüzden CSRF dışında kalır.
- **Open redirect:** `next` ve benzeri parametreler `url_has_allowed_host_and_scheme` ile doğrulanır.
- **Dosya çıktıları:** Excel/PDF dosya adları sabit ya da temizlenmiş olmalı. Hücre değerlerinde formül enjeksiyonuna karşı `=`, `+`, `-`, `@` ile başlayan değerlerin başına `'` eklenir.

## JWT ve servisler arası
- **JWT session'da kalır:** Django JWT'yi server-side session'da tutar; template'e, JS'e, URL'e veya log'a koymaz. İstisna: Veri Paylaşımı sayfasındaki uzun ömürlü token yalnızca sahibine gösterilir.
- **Algoritma sabit:** Java JWT'yi yalnızca HS256 ile doğrular (`alg` başlığına güvenilmez, `none` reddedilir); `exp` zorunlu.
- **Secret'lar env'den:** `PORTAL_JWT_SECRET`, `PORTAL_SERVICE_KEY`, Django `SECRET_KEY`, LDAP bilgileri ve API token'ları koda, `application.properties`'e veya teste gömülmez. `.env`, `application-local*`, token, `db.sqlite3`, `*.duckdb` ve sertifikalar commit edilmez. Log'lara parola veya token yazılmaz.
- **Yetki kaynağı DB:** Java yetkileri JWT claim'lerinden değil, her istekte DuckDB `user_permission` tablosundan okur (`CurrentUserService`). JWT'deki `perms` yalnızca Django arayüzü içindir.
- **`/internal/**`:** Dışarıya açılmaz, yalnızca `X-Service-Key` ile çağrılır; anahtar sabit zamanlı karşılaştırılır. Dev token endpoint'i yalnızca geliştirme içindir.
- **Tek kontrol noktası:** Export (Excel/PDF) ve MCP, HTML ekranlarıyla aynı Java Service metodlarından geçer; ayrı, gevşek bir sorgu yolu açılmaz.
- **SQL:** DuckDB sorguları parametreli; kullanıcı girdisi string birleştirmeyle SQL'e girmez.

## LDAP
- `core/ldap_backend.py` içindeki korumalar kaldırılmaz: boş parola engeli, `USERNAME_RE`, `escape_rdn` / `escape_filter_chars`, yerel hesapların LDAP ile eşleştirilmemesi.
