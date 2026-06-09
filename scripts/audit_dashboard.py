#!/usr/bin/env python
"""
End-to-end audit of every dashboard surface.

Hits both the FastAPI backend (CRUD, AI actions) and the Next.js web layer
(rendered HTML with auth cookies). Each check appends a pass/fail row to
the report which is printed at the end.

Run with:  .venv/Scripts/python.exe scripts/audit_dashboard.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any
from urllib import error, parse, request

API = os.environ.get("API_BASE", "http://localhost:8000")
WEB = os.environ.get("WEB_BASE", "http://localhost:3030")

results: list[tuple[str, str, str]] = []  # (area, name, status)


def record(area: str, name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else f"FAIL — {detail}"
    results.append((area, name, status))
    sym = "+" if ok else "-"
    print(f"  [{sym}] {area:<14} {name:<55} {status}")


def http(
    method: str,
    url: str,
    *,
    token: str | None = None,
    json_body: dict | None = None,
    raw_body: bytes | None = None,
    cookies: dict | None = None,
    content_type: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    headers: dict[str, str] = {"Connection": "close"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    body: bytes | None = None
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif raw_body is not None:
        body = raw_body
        if content_type:
            headers["Content-Type"] = content_type
    # Retry once on transient network errors — urllib on Windows can drop
    # connections under concurrent load (a separate browser tab hitting the
    # same dev server is enough).
    last_err: str = ""
    for attempt in range(3):
        req = request.Request(url, data=body, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=30) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except error.HTTPError as e:
            return e.code, dict(e.headers or {}), e.read()
        except Exception as e:
            last_err = f"NETERR:{type(e).__name__}:{e}"
            time.sleep(0.5 * (attempt + 1))
    return 0, {}, last_err.encode()


# ─── Auth ────────────────────────────────────────────────────────────────────
print("\n=== AUTH ===")
suffix = int(time.time())
email = f"audit-{suffix}@example.com"
password = "AuditPass123!"

code, _, body = http(
    "POST",
    f"{API}/v1/auth/signup",
    json_body={
        "firm_name": "Audit Firm",
        "full_name": "Audit User",
        "email": email,
        "password": password,
        "locale": "en",
    },
)
ok = code == 201 and b"access_token" in body
record("auth", "signup", ok, f"code={code}")
tokens = json.loads(body) if ok else {}
ACCESS = tokens.get("access_token", "")
REFRESH = tokens.get("refresh_token", "")

code, _, body = http(
    "POST",
    f"{API}/v1/auth/login",
    json_body={"email": email, "password": password},
)
record("auth", "login (correct password)", code == 200, f"code={code}")

code, _, _ = http(
    "POST",
    f"{API}/v1/auth/login",
    json_body={"email": email, "password": "WRONG"},
)
record("auth", "login (wrong password = 401)", code == 401, f"code={code}")

code, _, body = http("GET", f"{API}/v1/auth/me", token=ACCESS)
me = json.loads(body) if code == 200 else {}
record(
    "auth",
    "GET /v1/auth/me",
    code == 200 and me.get("email") == email,
    f"code={code}",
)

code, _, body = http(
    "PATCH",
    f"{API}/v1/auth/me",
    token=ACCESS,
    json_body={
        "full_name": "Updated Audit",
        "locale": "ar",
        "phone_number": "+966 50 999 8877",
    },
)
patched = json.loads(body) if code == 200 else {}
record(
    "auth",
    "PATCH /v1/auth/me (name + locale + phone)",
    code == 200
    and patched.get("full_name") == "Updated Audit"
    and patched.get("locale") == "ar"
    and patched.get("phone_number") == "966509998877",
    f"code={code} phone={patched.get('phone_number')}",
)

code, _, body = http("GET", f"{API}/v1/auth/sessions", token=ACCESS)
sessions = json.loads(body) if code == 200 else []
record(
    "auth",
    "GET /v1/auth/sessions",
    code == 200 and isinstance(sessions, list) and len(sessions) >= 1,
    f"code={code} count={len(sessions) if isinstance(sessions, list) else '?'}",
)

code, _, body = http(
    "POST",
    f"{API}/v1/auth/refresh",
    json_body={"refresh_token": REFRESH},
)
rotated = json.loads(body) if code == 200 else {}
record(
    "auth",
    "POST /v1/auth/refresh (token rotation)",
    code == 200 and rotated.get("access_token") and rotated.get("refresh_token"),
    f"code={code}",
)
if rotated:
    ACCESS = rotated.get("access_token", ACCESS)
    REFRESH = rotated.get("refresh_token", REFRESH)

# ─── Tenant self-service ─────────────────────────────────────────────────────
print("\n=== TENANT ===")
code, _, body = http("GET", f"{API}/v1/tenants/me", token=ACCESS)
tenant = json.loads(body) if code == 200 else {}
record(
    "tenant",
    "GET /v1/tenants/me",
    code == 200 and tenant.get("name"),
    f"code={code} name={tenant.get('name')}",
)

code, _, body = http(
    "PATCH",
    f"{API}/v1/tenants/me",
    token=ACCESS,
    json_body={
        "name": "Audit Renamed Firm",
        "billing_email": "billing@audit.example",
        "vat_number": "300000000000003",
        "billing_address": "King Fahd Rd, Riyadh, 12333",
    },
)
record(
    "tenant",
    "PATCH /v1/tenants/me (admin self-service)",
    code == 200,
    f"code={code}",
)

# ─── Clients ─────────────────────────────────────────────────────────────────
print("\n=== CLIENTS ===")
code, _, body = http(
    "POST",
    f"{API}/v1/clients",
    token=ACCESS,
    json_body={
        "name": "Audit Trading Co",
        "kind": "company",
        "email": "contact@audit.example",
        "phone": "+966501112233",
        "city": "Riyadh",
        "cr_number": "1010999888",
        "vat_number": "300000000000004",
        "lead_source": "Audit",
        "notes": "Created by audit script.",
    },
)
client = json.loads(body) if code == 201 else {}
CLIENT_ID = client.get("id", "")
record(
    "clients",
    "POST /v1/clients",
    code == 201 and CLIENT_ID,
    f"code={code}",
)

code, _, body = http("GET", f"{API}/v1/clients/{CLIENT_ID}", token=ACCESS)
record("clients", "GET /v1/clients/{id}", code == 200, f"code={code}")

code, _, body = http(
    "PATCH",
    f"{API}/v1/clients/{CLIENT_ID}",
    token=ACCESS,
    json_body={"name": "Audit Trading Co (Updated)", "status": "active"},
)
updated = json.loads(body) if code == 200 else {}
record(
    "clients",
    "PATCH /v1/clients/{id}",
    code == 200 and updated.get("name", "").endswith("(Updated)"),
    f"code={code}",
)

# Create a second client so list responses have multiple rows
code, _, body = http(
    "POST",
    f"{API}/v1/clients",
    token=ACCESS,
    json_body={"name": "Individual Client", "kind": "person"},
)
record("clients", "POST second client (person)", code == 201, f"code={code}")

code, _, body = http("GET", f"{API}/v1/clients?limit=10", token=ACCESS)
clients_list = json.loads(body) if code == 200 else []
record(
    "clients",
    "GET /v1/clients (list)",
    code == 200 and len(clients_list) >= 2,
    f"code={code} count={len(clients_list) if isinstance(clients_list, list) else '?'}",
)

# ─── Cases ───────────────────────────────────────────────────────────────────
print("\n=== CASES ===")
code, _, body = http(
    "POST",
    f"{API}/v1/cases",
    token=ACCESS,
    json_body={
        "reference": "AUD-001",
        "title": "Audit retainer dispute",
        "domain": "commercial",
        "client_id": CLIENT_ID,
    },
)
case = json.loads(body) if code == 201 else {}
CASE_ID = case.get("id", "")
record(
    "cases",
    "POST /v1/cases (with client_id)",
    code == 201 and CASE_ID,
    f"code={code}",
)

code, _, body = http(
    "PATCH",
    f"{API}/v1/cases/{CASE_ID}",
    token=ACCESS,
    json_body={
        "court_name": "Commercial Court of Riyadh",
        "court_case_number": "AC-2026-001",
        "judge_name": "Sh. Al-Fahad",
        "opposing_party_name": "Counterparty Inc",
        "opposing_counsel": "Al-Saud Law",
        "status": "in_court",
        "priority": "high",
    },
)
patched_case = json.loads(body) if code == 200 else {}
record(
    "cases",
    "PATCH /v1/cases/{id} (full field set)",
    code == 200
    and patched_case.get("court_name") == "Commercial Court of Riyadh"
    and patched_case.get("status") == "in_court",
    f"code={code}",
)

code, _, body = http(
    "GET",
    f"{API}/v1/cases?client_id={CLIENT_ID}&limit=10",
    token=ACCESS,
)
filtered = json.loads(body) if code == 200 else []
record(
    "cases",
    "GET /v1/cases?client_id= (server-side filter)",
    code == 200 and len(filtered) == 1 and filtered[0].get("id") == CASE_ID,
    f"code={code} count={len(filtered) if isinstance(filtered, list) else '?'}",
)

# Try AI analysis — may fail if OpenAI key isn't set; treat 5xx as soft fail
code, _, body = http(
    "POST",
    f"{API}/v1/cases/{CASE_ID}/analyze",
    token=ACCESS,
    json_body={"locale": "en"},
)
record(
    "cases",
    "POST /v1/cases/{id}/analyze (AI action)",
    code in (200, 502, 503),  # AI may be down — endpoint reachable is what we want
    f"code={code}",
)

# ─── Tasks ───────────────────────────────────────────────────────────────────
print("\n=== TASKS ===")
code, _, body = http(
    "POST",
    f"{API}/v1/tasks",
    token=ACCESS,
    json_body={
        "title": "Audit task — draft response",
        "priority": "high",
        "case_id": CASE_ID,
    },
)
task = json.loads(body) if code == 201 else {}
TASK_ID = task.get("id", "")
record(
    "tasks",
    "POST /v1/tasks",
    code == 201 and TASK_ID,
    f"code={code}",
)

code, _, body = http(
    "PATCH",
    f"{API}/v1/tasks/{TASK_ID}",
    token=ACCESS,
    json_body={"status": "completed"},
)
record("tasks", "PATCH /v1/tasks/{id} (complete)", code == 200, f"code={code}")

code, _, body = http(
    "GET",
    f"{API}/v1/tasks?case_id={CASE_ID}",
    token=ACCESS,
)
ts = json.loads(body) if code == 200 else []
record(
    "tasks",
    "GET /v1/tasks?case_id=",
    code == 200 and isinstance(ts, list) and any(t["id"] == TASK_ID for t in ts),
    f"code={code} count={len(ts) if isinstance(ts, list) else '?'}",
)

# ─── Hearings ────────────────────────────────────────────────────────────────
print("\n=== HEARINGS ===")
code, _, body = http(
    "POST",
    f"{API}/v1/hearings",
    token=ACCESS,
    json_body={
        "case_id": CASE_ID,
        "scheduled_at": "2026-07-01T10:00:00Z",
        "kind": "hearing",
        "court_name": "Commercial Court of Riyadh",
    },
)
hearing = json.loads(body) if code == 201 else {}
HEARING_ID = hearing.get("id", "")
record("hearings", "POST /v1/hearings", code == 201 and HEARING_ID, f"code={code}")

code, _, body = http("GET", f"{API}/v1/hearings?case_id={CASE_ID}", token=ACCESS)
record(
    "hearings",
    "GET /v1/hearings?case_id=",
    code == 200,
    f"code={code}",
)

# ─── Time entries ────────────────────────────────────────────────────────────
print("\n=== TIME ENTRIES ===")
code, _, body = http(
    "POST",
    f"{API}/v1/time-entries",
    token=ACCESS,
    json_body={
        "case_id": CASE_ID,
        "activity_kind": "research",
        "work_date": "2026-05-22",
        "minutes": 90,
        "description": "Audit time entry",
        "billable": True,
    },
)
record(
    "time-entries", "POST /v1/time-entries", code == 201, f"code={code}"
)

code, _, _ = http("GET", f"{API}/v1/time-entries?case_id={CASE_ID}", token=ACCESS)
record("time-entries", "GET /v1/time-entries", code == 200, f"code={code}")

# ─── Case notes ──────────────────────────────────────────────────────────────
print("\n=== CASE NOTES ===")
code, _, body = http(
    "POST",
    f"{API}/v1/case-notes",
    token=ACCESS,
    json_body={
        "case_id": CASE_ID,
        "body": "Audit note — client is responsive.",
        "is_internal": True,
    },
)
record("case-notes", "POST /v1/case-notes", code == 201, f"code={code}")
code, _, _ = http("GET", f"{API}/v1/case-notes?case_id={CASE_ID}", token=ACCESS)
record("case-notes", "GET /v1/case-notes", code == 200, f"code={code}")

# ─── Activities ──────────────────────────────────────────────────────────────
print("\n=== ACTIVITIES ===")
code, _, body = http(
    "GET", f"{API}/v1/activities?case_id={CASE_ID}", token=ACCESS
)
record("activities", "GET /v1/activities?case_id=", code == 200, f"code={code}")

# ─── Contacts ────────────────────────────────────────────────────────────────
print("\n=== CONTACTS ===")
code, _, body = http(
    "POST",
    f"{API}/v1/contacts",
    token=ACCESS,
    json_body={
        "name": "Audit Contact",
        "kind": "expert",
        "phone": "+966500000000",
    },
)
record("contacts", "POST /v1/contacts", code == 201, f"code={code}")
code, _, _ = http("GET", f"{API}/v1/contacts?limit=10", token=ACCESS)
record("contacts", "GET /v1/contacts", code == 200, f"code={code}")

# ─── Documents (list only — upload is multipart) ────────────────────────────
print("\n=== DOCUMENTS ===")
code, _, _ = http("GET", f"{API}/v1/documents?limit=10", token=ACCESS)
record("documents", "GET /v1/documents", code == 200, f"code={code}")

# ─── Templates ───────────────────────────────────────────────────────────────
print("\n=== TEMPLATES ===")
code, _, body = http("GET", f"{API}/v1/templates", token=ACCESS)
tpls = json.loads(body) if code == 200 else []
record(
    "templates",
    "GET /v1/templates",
    code == 200,
    f"code={code} count={len(tpls) if isinstance(tpls, list) else '?'}",
)

# ─── Plans + subscription ────────────────────────────────────────────────────
print("\n=== BILLING ===")
code, _, body = http("GET", f"{API}/v1/plans")  # public
plans = json.loads(body) if code == 200 else []
record(
    "billing",
    "GET /v1/plans (public)",
    code == 200 and isinstance(plans, list),
    f"code={code} count={len(plans) if isinstance(plans, list) else '?'}",
)
code, _, _ = http("GET", f"{API}/v1/subscriptions/me", token=ACCESS)
record(
    "billing",
    "GET /v1/subscriptions/me",
    code in (200, 404),  # 404 if no sub yet — that's fine
    f"code={code}",
)

# ─── WhatsApp ────────────────────────────────────────────────────────────────
print("\n=== WHATSAPP ===")
code, _, _ = http("GET", f"{API}/v1/whatsapp/session", token=ACCESS)
record(
    "whatsapp",
    "GET /v1/whatsapp/session",
    code == 200,
    f"code={code}",
)
code, _, _ = http("GET", f"{API}/v1/whatsapp/agent-profile", token=ACCESS)
record("whatsapp", "GET /v1/whatsapp/agent-profile", code == 200, f"code={code}")
code, _, _ = http("GET", f"{API}/v1/whatsapp/allowed-senders", token=ACCESS)
record("whatsapp", "GET /v1/whatsapp/allowed-senders", code == 200, f"code={code}")

# ─── Dashboard summary ───────────────────────────────────────────────────────
print("\n=== DASHBOARD ===")
code, _, body = http("GET", f"{API}/v1/dashboard/summary", token=ACCESS)
record("dashboard", "GET /v1/dashboard/summary", code == 200, f"code={code}")

# ─── Team ────────────────────────────────────────────────────────────────────
print("\n=== TEAM ===")
code, _, body = http("GET", f"{API}/v1/team/users", token=ACCESS)
team = json.loads(body) if code == 200 else []
record(
    "team",
    "GET /v1/team/users",
    code == 200 and isinstance(team, list),
    f"code={code} count={len(team) if isinstance(team, list) else '?'}",
)
code, _, _ = http("GET", f"{API}/v1/team/invites", token=ACCESS)
record("team", "GET /v1/team/invites", code == 200, f"code={code}")

# ─── Web pages (cookie-auth) ─────────────────────────────────────────────────
print("\n=== WEB PAGES ===")
cookies = {"lai_access": ACCESS, "lai_refresh": REFRESH}

WEB_PAGES = [
    ("dashboard",        "/en/dashboard",                        ["Mostashari", "Home"]),
    ("dashboard/cases",  "/en/dashboard/cases",                  ["Cases", "AUD-001"]),
    ("case detail",      f"/en/dashboard/cases/{CASE_ID}",       ["Audit retainer dispute", "Edit", "Delete"]),
    ("dashboard/clients",  "/en/dashboard/clients",              ["Audit Trading Co"]),
    ("client detail",      f"/en/dashboard/clients/{CLIENT_ID}", ["Audit Trading Co", "Open cases", "Edit", "Delete"]),
    ("dashboard/documents","/en/dashboard/documents",            ["Documents"]),
    ("dashboard/contracts","/en/dashboard/contracts",            ["No contracts ready", "Upload a contract"]),
    ("dashboard/tasks",    "/en/dashboard/tasks",                ["Tasks"]),
    ("dashboard/hearings", "/en/dashboard/hearings",             ["Hearings"]),
    ("dashboard/contacts", "/en/dashboard/contacts",             ["Audit Contact"]),
    ("dashboard/drafting", "/en/dashboard/drafting",             ["Drafting"]),
    ("dashboard/whatsapp", "/en/dashboard/whatsapp",             ["WhatsApp"]),
    ("dashboard/billing",  "/en/dashboard/billing",              ["Subscription"]),
    ("dashboard/settings", "/en/dashboard/settings",             ["Your profile", "Mobile number", "Active sessions"]),
    ("dashboard/chat",     "/en/dashboard/chat",                 []),
]
for name, path, expect in WEB_PAGES:
    code, _, body = http("GET", f"{WEB}{path}", cookies=cookies)
    html = body.decode("utf-8", errors="ignore") if body else ""
    missing = [s for s in expect if s not in html]
    ok = code == 200 and not missing
    record("web", name, ok, f"code={code} missing={missing if missing else ''}")

# ─── Logout-all (revokes all sessions) ───────────────────────────────────────
print("\n=== LOGOUT-ALL ===")
code, _, _ = http("POST", f"{API}/v1/auth/logout-all", token=ACCESS)
record("auth", "POST /v1/auth/logout-all", code in (200, 204), f"code={code}")

code, _, body = http(
    "POST", f"{API}/v1/auth/refresh", json_body={"refresh_token": REFRESH}
)
record(
    "auth",
    "refresh after logout-all is rejected",
    code == 401,
    f"code={code}",
)

# ─── Summary table ───────────────────────────────────────────────────────────
print("\n" + "=" * 78)
print(" AUDIT REPORT")
print("=" * 78)
passes = sum(1 for *_, s in results if s == "PASS")
fails = len(results) - passes
print(f" Total: {len(results)}    Pass: {passes}    Fail: {fails}")
print("-" * 78)
print(f" {'AREA':<14} {'CHECK':<55} STATUS")
print("-" * 78)
for area, name, status in results:
    print(f" {area:<14} {name:<55} {status}")
print("=" * 78)
sys.exit(0 if fails == 0 else 1)
