"""CyberOps portalı için salt okunur MCP server.

Java backend REST API'sini (docs/api-contract.md) `Authorization: Bearer <JWT>` ile çağırır.
DB'ye doğrudan erişmez; yalnızca GET endpoint'lerini sarar. stdio transport.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

API_URL = os.environ.get("PORTAL_API_URL", "http://127.0.0.1:8080").rstrip("/")

TOKEN_HELP = (
    "PORTAL_API_TOKEN tanımlı değil. Portalda 'Veri Paylaşımı' sayfasından token'ı kopyalayıp "
    "ortam değişkeni olarak verin. Geliştirmede: curl -s -H 'X-Service-Key: dev-service-key' "
    "'http://127.0.0.1:8080/internal/dev/token?username=yonetici' komutunun döndürdüğü 'token' alanı."
)

mcp = FastMCP("cyberops-portal")


class PortalError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _token() -> str:
    tok = os.environ.get("PORTAL_API_TOKEN", "").strip()
    if not tok or tok.startswith("${"):
        raise PortalError(TOKEN_HELP)
    return tok


def _error_message(r: httpx.Response) -> str | None:
    try:
        err = r.json().get("error") or {}
        if isinstance(err, dict) and err.get("message"):
            code = err.get("code")
            return f"{err['message']}" + (f" ({code})" if code else "")
    except Exception:
        pass
    return None


def api_get(path: str, **params: Any) -> Any:
    """Java API'ye GET isteği atar; hataları anlaşılır Türkçe mesaja çevirir."""
    clean = {k: v for k, v in params.items() if v not in (None, "")}
    try:
        r = httpx.get(
            f"{API_URL}{path}",
            params=clean,
            headers={"Authorization": f"Bearer {_token()}", "Accept": "application/json"},
            timeout=10,
        )
    except httpx.ConnectError:
        raise PortalError(f"Backend çalışmıyor ({API_URL}). PORTAL_API_URL'i ve Java sunucusunu kontrol edin.")
    except httpx.TimeoutException:
        raise PortalError(f"Backend yanıt vermedi (zaman aşımı, {API_URL}).")
    except httpx.HTTPError as e:
        raise PortalError(f"Backend'e bağlanılamadı ({API_URL}): {e.__class__.__name__}")

    if r.status_code == 401:
        raise PortalError("Token geçersiz veya süresi dolmuş. " + TOKEN_HELP.split(". ", 1)[1])
    if r.status_code == 403:
        raise PortalError(_error_message(r) or "Bu işlem için yetkiniz yok.", 403)
    if r.status_code == 404:
        raise PortalError(_error_message(r) or "Kayıt bulunamadı veya görüntüleme yetkiniz yok.")
    if r.status_code >= 400:
        raise PortalError(_error_message(r) or f"API hatası (HTTP {r.status_code}).")
    if not r.content:
        return None
    return r.json()


# ---------- sadeleştirme yardımcıları ----------

def _user(u: dict | None) -> str | None:
    if not u:
        return None
    name = u.get("displayName") or u.get("username")
    return f"{name} (#{u.get('id')})" if u.get("id") is not None else name


def _task(t: dict) -> dict:
    out = {
        "id": t.get("id"),
        "code": t.get("code"),
        "title": t.get("title"),
        "status": t.get("status"),
        "severity": t.get("severity"),
        "assignees": [_user(a) for a in t.get("assignees") or []],
        "backupAssignee": _user(t.get("backupAssignee")),
        "dueDate": t.get("dueDate"),
        "isOverdue": t.get("isOverdue"),
    }
    if t.get("handover"):
        out["handover"] = True
    return out


def _activity(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "name": a.get("name"),
        "date": a.get("date"),
        "location": a.get("location"),
        "type": a.get("type"),
        "participationType": a.get("participationType"),
        "contactPerson": _user(a.get("contactPerson")),
        "attendees": [_user(u) for u in a.get("attendees") or []],
        "joined": a.get("joined"),
    }


def _team_member(m: dict) -> dict:
    return {
        "user": _user(m.get("user")),
        "title": m.get("title"),
        "isOnLeave": m.get("isOnLeave"),
        "open": m.get("openCount"),
        "inProgress": m.get("progressCount"),
        "done": m.get("doneCount"),
        "overdue": m.get("overdueCount"),
    }


def _history(h: dict) -> dict:
    out = {
        "date": h.get("actionDate"),
        "by": _user(h.get("actionBy")),
        "action": h.get("actionType"),
        "description": h.get("actionDescription"),
    }
    if h.get("task"):
        out["task"] = h["task"].get("code")
    return out


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1)


# ---------- tool'lar ----------

@mcp.tool()
def whoami() -> str:
    """Token sahibi kullanıcının bilgilerini döndürür (ad, unvan, yetkiler, yönetici mi, izinli mi)."""
    return _dump(api_get("/api/me"))


@mcp.tool()
def list_tasks(
    status: str | None = None,
    severity: str | None = None,
    q: str | None = None,
    assignee_id: int | None = None,
) -> str:
    """Görünür task'ları (işleri) listeler; Kritik önce sıralıdır.

    Filtreler (hepsi isteğe bağlı):
    - status: OPEN (Açık) | IN_PROGRESS (Devam Ediyor) | DONE (Tamamlandı)
    - severity: LOW (Düşük) | MEDIUM (Orta) | HIGH (Yüksek) | CRITICAL (Kritik)
    - q: başlık/kod içinde metin araması
    - assignee_id: sorumlu kullanıcı id'si (list_users ile bulunabilir)
    """
    data = api_get(
        "/api/tasks",
        status=status.upper() if status else None,
        severity=severity.upper() if severity else None,
        q=q,
        assigneeId=assignee_id,
    )
    tasks = [_task(t) for t in data or []]
    return _dump({"count": len(tasks), "tasks": tasks})


@mcp.tool()
def overdue_tasks() -> str:
    """Son tarihi geçmiş (geciken) ve tamamlanmamış görünür task'ları listeler; Kritik önce."""
    tasks = [_task(t) for t in api_get("/api/tasks", overdue="true") or []]
    return _dump({"count": len(tasks), "tasks": tasks})


@mcp.tool()
def get_task(task_id: int) -> str:
    """Tek bir task'ın detayını açıklaması ve değişiklik geçmişiyle (history) birlikte döndürür."""
    t = api_get(f"/api/tasks/{int(task_id)}")
    out = _task(t)
    out.update(
        {
            "description": t.get("description"),
            "createdBy": _user(t.get("createdBy")),
            "createDate": t.get("createDate"),
            "modifiedBy": _user(t.get("modifiedBy")),
            "modifiedDate": t.get("modifiedDate"),
            "history": [_history(h) for h in t.get("history") or []],
        }
    )
    return _dump(out)


@mcp.tool()
def dashboard_summary() -> str:
    """Kullanıcının pano özetini döndürür: istatistikler (bekleyen, devam eden, biten, geciken,
    kritik, yaklaşan etkinlik), bekleyen/devralınan işler, yaklaşan etkinlikler ve yetki varsa
    önem/durum dağılımı raporu ile ekip özeti."""
    d = api_get("/api/dashboard") or {}
    out: dict[str, Any] = {
        "stats": d.get("stats"),
        "report": d.get("report"),
        "pendingTasks": [_task(t) for t in d.get("pendingTasks") or []],
        "handoverTasks": [_task(t) for t in d.get("handoverTasks") or []],
        "myActivities": [_activity(a) for a in d.get("myActivities") or []],
    }
    if d.get("team") is not None:
        out["team"] = [_team_member(m) for m in d["team"]]
    if d.get("recentHistory"):
        out["recentHistory"] = [_history(h) for h in d["recentHistory"]]
    return _dump(out)


@mcp.tool()
def team_summary() -> str:
    """Yöneticinin ekibindeki her üye için açık / devam eden / biten / geciken iş sayılarını ve
    izin durumunu döndürür. ROLE_MANAGEMENT (rol yönetimi) yetkisi gerektirir."""
    try:
        data = api_get("/api/team")
    except PortalError as e:
        if e.status == 403:
            return ("Ekip özetini görüntüleme yetkiniz yok: bu bilgi yalnızca Rol Yönetimi "
                    "(ROLE_MANAGEMENT) yetkisine sahip yöneticilere açıktır.")
        raise
    members = [_team_member(m) for m in data or []]
    return _dump({"count": len(members), "members": members})


@mcp.tool()
def upcoming_activities() -> str:
    """Yaklaşan etkinlikleri (eğitim, konferans vb.) tarih, yer, katılımcılar ve
    kullanıcının katılıp katılmadığı bilgisiyle listeler."""
    acts = [_activity(a) for a in api_get("/api/activities", scope="upcoming") or []]
    return _dump({"count": len(acts), "activities": acts})


@mcp.tool()
def list_users() -> str:
    """Aktif kullanıcıları (id, kullanıcı adı, görünen ad) listeler; list_tasks'taki
    assignee_id filtresi için id bulmakta kullanılır."""
    users = [
        {"id": u.get("id"), "username": u.get("username"), "displayName": u.get("displayName")}
        for u in api_get("/api/users") or []
    ]
    return _dump(users)


if __name__ == "__main__":
    mcp.run()  # stdio
