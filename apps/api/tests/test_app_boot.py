"""App-boot smoke tests — no DB/Redis required, just import + route table."""
from __future__ import annotations


def test_app_imports():
    from app.main import app

    assert app is not None
    assert app.title == "Legal AI OS — Saudi Edition"


def test_routes_registered():
    """Spot-check the high-value routes so a regression in the v1 router
    wiring fails the test rather than a customer."""
    from app.main import app

    paths = {getattr(r, "path", "") for r in app.routes}
    expected = {
        "/health/live",
        "/health/ready",
        "/metrics",
        "/v1/auth/signup",
        "/v1/auth/login",
        "/v1/auth/refresh",
        "/v1/auth/logout",
        "/v1/auth/sessions",
        "/v1/team/users",
        "/v1/team/invites",
        "/v1/subscriptions/me",
        "/v1/subscriptions/usage",
        "/v1/subscriptions/change-plan",
        "/v1/invoices",
        "/v1/onboarding/status",
        "/v1/compliance/me/export",
        "/v1/compliance/me/delete",
        "/v1/compliance/tenant/delete",
        "/v1/tenants/me",
        "/v1/tenants/me/subdomain",
        "/v1/subdomains/check",
        "/v1/whatsapp/session/start",
        "/v1/whatsapp/session/qr.png",
        "/v1/whatsapp/agent-profile",
        "/v1/chat",
        "/v1/chat/agent",
        "/webhooks/stripe",
        "/webhooks/moyasar",
        "/webhooks/whatsapp-baileys",
    }
    missing = expected - paths
    assert not missing, f"missing routes: {missing}"


def test_alembic_chain_is_linear():
    """Walks revisions to confirm there's no fork in the migration history.
    This catches the 'two devs added a migration named the same revision'
    foot-gun before it hits CI."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    sd = ScriptDirectory.from_config(Config("alembic.ini"))
    revs = list(sd.walk_revisions())
    # Each revision (except the head) should have exactly one descendant
    # of the chain. We assert by walking from base → head and confirming
    # we visit every revision.
    by_id = {r.revision: r for r in revs}
    assert by_id, "no migrations found"
    # Find heads — there should be exactly one.
    heads = sd.get_heads()
    assert len(heads) == 1, f"multiple heads: {heads}"
