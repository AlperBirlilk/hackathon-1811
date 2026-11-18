# Güvenlik kuralları (tüm repo)

Bu bir siber güvenlik ürünü; jüri güvenlik açıklarına özellikle bakacak.

- **Yetki:** Her endpoint (HTML, export, REST API, MCP) sunucu tarafında yetki kontrol eder ve veriyi aynı kurallarla scope eder (`visible_tasks`, `manager=request.user` vb.). Export ve API, ekranda görülemeyen veriyi döndürmez.
- **IDOR:** ID ile nesne erişimi her zaman scope edilmiş queryset üzerinden yapılır.
- **Yetki yükseltme:** Bir kullanıcı sahip olmadığı yetkiyi başkasına veremez (bkz. `member_permissions`). Yeni rol veya yetki akışları da bu kurala uyar.
- **CSRF / metot:** Durum değiştiren işlemler POST ve CSRF korumalıdır. DRF API'si salt okunur olduğu sürece Token auth ile CSRF dışında kalabilir.
- **Open redirect:** `next` ve benzeri parametreler `url_has_allowed_host_and_scheme` ile doğrulanır.
- **LDAP:** `core/ldap_backend.py` içindeki korumalar kaldırılmaz: boş parola engeli, `USERNAME_RE`, `escape_rdn` / `escape_filter_chars`, yerel hesapların LDAP ile eşleştirilmemesi.
- **Secret:** `SECRET_KEY`, LDAP bilgileri ve API token'ları env'den okunur. `.env`, token, `db.sqlite3` ve sertifikalar commit edilmez. Log'lara parola veya token yazılmaz.
- **Dosya çıktıları:** Excel/PDF dosya adları sabit ya da temizlenmiş olmalı. Hücre değerlerinde formül enjeksiyonuna karşı `=`, `+`, `-`, `@` ile başlayan değerlerin başına `'` eklenir.
