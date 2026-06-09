"""CLI entry points (Typer).

Run with:  python -m app.cli <command>

Commands:
  seed                     — seed plans, platform tenant, super admin, base templates
  create-superadmin EMAIL  — promote/create a super admin user
  reindex-document UUID    — re-run ingestion for a document
  ingest-laws DIR          — bulk-import a folder of Saudi-law PDFs into the platform corpus
"""
from __future__ import annotations

import getpass
import mimetypes
import uuid as _uuid
from datetime import date
from io import BytesIO
from pathlib import Path
from uuid import UUID

import typer
from sqlalchemy import select

from app.core.logging import configure_logging, get_logger
from app.core.security import Role, hash_password
from app.db.session import SessionLocal
from app.models import (
    Document,
    DocumentSource,
    DocumentStatus,
    LegalDomain,
    Plan,
    PlanTier,
    Template,
    TemplateKind,
    Tenant,
    User,
)
from app.services.document_processor import parse
from app.services.legal_chunker import chunk_legal_pages, detect_language
from app.services.rag import index_document_chunks
from app.services.storage import (
    ensure_bucket,
    storage_key_for,
    upload_fileobj,
)
from app.workers.tasks import ingest_document_task

app = typer.Typer(no_args_is_help=True)
log = get_logger(__name__)


PLAN_SEED = [
    {
        "tier": PlanTier.BASIC,
        "name_en": "Basic",
        "name_ar": "الأساسية",
        "price_monthly_sar": 299,
        "price_monthly_usd": 79,
        "monthly_messages_limit": 1000,
        "monthly_documents_limit": 50,
        "monthly_contracts_limit": 10,
        "seats_limit": 2,
    },
    {
        "tier": PlanTier.PRO,
        "name_en": "Pro",
        "name_ar": "الاحترافية",
        "price_monthly_sar": 999,
        "price_monthly_usd": 269,
        "monthly_messages_limit": 5000,
        "monthly_documents_limit": 250,
        "monthly_contracts_limit": 50,
        "seats_limit": 10,
    },
    {
        "tier": PlanTier.ENTERPRISE,
        "name_en": "Enterprise",
        "name_ar": "المؤسسات",
        "price_monthly_sar": 3499,
        "price_monthly_usd": 929,
        "monthly_messages_limit": 25000,
        "monthly_documents_limit": 2000,
        "monthly_contracts_limit": 500,
        "seats_limit": 50,
    },
]


GLOBAL_TEMPLATES = [
    {
        "title_en": "Non-Disclosure Agreement (Saudi)",
        "title_ar": "اتفاقية عدم إفصاح (السعودية)",
        "kind": TemplateKind.NDA,
        "body_en": (
            "NON-DISCLOSURE AGREEMENT\n\n"
            "This Non-Disclosure Agreement (the \"Agreement\") is made on {{date}} between "
            "{{party_a}} (\"Disclosing Party\") and {{party_b}} (\"Receiving Party\").\n\n"
            "1. Confidential Information. ...\n"
            "2. Obligations. ...\n"
            "3. Term. {{term_months}} months.\n"
            "4. Governing Law. The laws of the Kingdom of Saudi Arabia."
        ),
        "body_ar": (
            "اتفاقية عدم إفصاح\n\n"
            "أبرمت هذه الاتفاقية في {{date}} بين {{party_a}} (\"الطرف المُفصِح\") و"
            "{{party_b}} (\"الطرف المُستلم\").\n\n"
            "١. المعلومات السرية. ...\n"
            "٢. الالتزامات. ...\n"
            "٣. المدة: {{term_months}} شهراً.\n"
            "٤. القانون الحاكم: أنظمة المملكة العربية السعودية."
        ),
        "variables": [
            {"name": "date", "label_en": "Date", "label_ar": "التاريخ", "type": "date"},
            {"name": "party_a", "label_en": "Party A", "label_ar": "الطرف الأول", "type": "text"},
            {"name": "party_b", "label_en": "Party B", "label_ar": "الطرف الثاني", "type": "text"},
            {"name": "term_months", "label_en": "Term (months)", "label_ar": "المدة (شهور)", "type": "text"},
        ],
        "is_global": True,
    },
    {
        "title_en": "Power of Attorney (KSA)",
        "title_ar": "وكالة شرعية",
        "kind": TemplateKind.POWER_OF_ATTORNEY,
        "body_en": (
            "POWER OF ATTORNEY\n\nI, {{principal_name}}, ID {{principal_id}}, hereby authorize "
            "{{agent_name}}, ID {{agent_id}}, to act on my behalf in {{matters}}."
        ),
        "body_ar": (
            "وكالة شرعية\n\nأنا الموقع أدناه {{principal_name}} وهويتي {{principal_id}}، "
            "أوكل {{agent_name}} هويته {{agent_id}} للقيام نيابةً عني في {{matters}}."
        ),
        "variables": [
            {"name": "principal_name", "label_en": "Principal", "label_ar": "الموكِّل", "type": "text"},
            {"name": "principal_id", "label_en": "Principal ID", "label_ar": "هوية الموكِّل", "type": "text"},
            {"name": "agent_name", "label_en": "Agent", "label_ar": "الوكيل", "type": "text"},
            {"name": "agent_id", "label_en": "Agent ID", "label_ar": "هوية الوكيل", "type": "text"},
            {"name": "matters", "label_en": "Matters", "label_ar": "موضوع الوكالة", "type": "text"},
        ],
        "is_global": True,
    },
    {
        "title_en": "Employment Contract (KSA Labor Law)",
        "title_ar": "عقد عمل (نظام العمل السعودي)",
        "kind": TemplateKind.EMPLOYMENT,
        "body_en": (
            "EMPLOYMENT CONTRACT\n\nEmployer: {{employer}}\nEmployee: {{employee}}\nPosition: {{position}}\n"
            "Monthly salary: {{salary_sar}} SAR\nProbation: {{probation_months}} months\n"
            "Working hours: per Article 98 of the KSA Labor Law."
        ),
        "body_ar": (
            "عقد عمل\n\nصاحب العمل: {{employer}}\nالموظف: {{employee}}\nالمسمى الوظيفي: {{position}}\n"
            "الراتب الشهري: {{salary_sar}} ريال سعودي\nفترة التجربة: {{probation_months}} شهراً\n"
            "ساعات العمل: وفقاً للمادة ٩٨ من نظام العمل."
        ),
        "variables": [
            {"name": "employer", "label_en": "Employer", "label_ar": "صاحب العمل", "type": "text"},
            {"name": "employee", "label_en": "Employee", "label_ar": "الموظف", "type": "text"},
            {"name": "position", "label_en": "Position", "label_ar": "المسمى الوظيفي", "type": "text"},
            {"name": "salary_sar", "label_en": "Salary (SAR)", "label_ar": "الراتب (ريال)", "type": "text"},
            {"name": "probation_months", "label_en": "Probation (months)", "label_ar": "فترة التجربة (شهور)", "type": "text"},
        ],
        "is_global": True,
    },
    {
        "title_en": "Demand Letter",
        "title_ar": "خطاب مطالبة",
        "kind": TemplateKind.DEMAND_LETTER,
        "body_en": (
            "DEMAND LETTER\n\nDate: {{date}}\nTo: {{recipient}}\nFrom: {{sender}}\n\n"
            "We hereby demand payment of SAR {{amount}} owed to our client under {{contract_ref}}, "
            "no later than {{due_date}}."
        ),
        "body_ar": (
            "خطاب مطالبة\n\nالتاريخ: {{date}}\nإلى: {{recipient}}\nمن: {{sender}}\n\n"
            "نطالبكم بسداد مبلغ {{amount}} ريال مستحق لموكلنا بموجب {{contract_ref}} في موعد أقصاه {{due_date}}."
        ),
        "variables": [
            {"name": "date", "label_en": "Date", "label_ar": "التاريخ", "type": "date"},
            {"name": "recipient", "label_en": "Recipient", "label_ar": "المرسل إليه", "type": "text"},
            {"name": "sender", "label_en": "Sender", "label_ar": "المرسل", "type": "text"},
            {"name": "amount", "label_en": "Amount", "label_ar": "المبلغ", "type": "text"},
            {"name": "contract_ref", "label_en": "Contract Reference", "label_ar": "مرجع العقد", "type": "text"},
            {"name": "due_date", "label_en": "Due Date", "label_ar": "تاريخ الاستحقاق", "type": "date"},
        ],
        "is_global": True,
    },
]


@app.command()
def seed() -> None:
    """Seed plans, platform tenant, and base templates. Idempotent."""
    configure_logging()
    db = SessionLocal()
    try:
        # 1. Plans
        for p in PLAN_SEED:
            existing = db.execute(select(Plan).where(Plan.tier == p["tier"])).scalar_one_or_none()
            if existing is None:
                db.add(Plan(**p))
        db.commit()

        # 2. Platform tenant (owns global Saudi-law datasets + global templates)
        platform = db.execute(select(Tenant).where(Tenant.slug == "platform")).scalar_one_or_none()
        if platform is None:
            platform = Tenant(
                name="Legal AI OS Platform",
                slug="platform",
                subdomain="platform",
                country="SA",
                default_locale="ar",
                is_active=True,
            )
            db.add(platform)
            db.commit()
            db.refresh(platform)

        # 3. Global templates
        for t in GLOBAL_TEMPLATES:
            exists = db.execute(
                select(Template).where(
                    Template.title_en == t["title_en"], Template.is_global.is_(True)
                )
            ).scalar_one_or_none()
            if exists is None:
                db.add(Template(tenant_id=platform.id, **t))
        db.commit()

        typer.echo("Seed complete.")
    finally:
        db.close()


@app.command(name="create-superadmin")
def create_superadmin(email: str) -> None:
    """Create or promote a super admin user."""
    configure_logging()
    pwd = getpass.getpass("Password: ")
    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(
                email=email,
                full_name="Super Admin",
                hashed_password=hash_password(pwd),
                role=Role.SUPER_ADMIN,
                tenant_id=None,
                is_active=True,
                is_email_verified=True,
            )
            db.add(user)
        else:
            user.role = Role.SUPER_ADMIN
            user.hashed_password = hash_password(pwd)
        db.commit()
        typer.echo(f"Super admin ready: {email}")
    finally:
        db.close()


@app.command(name="check-chatgpt-token")
def check_chatgpt_token() -> None:
    """Verify the OPENAI_CHATGPT_TOKEN is valid + still talks to Codex.

    Decodes the JWT (no signature check), prints expiry and account info,
    then fires a one-shot ping. Useful as a cron after refreshing the token.
    """
    import base64
    import json
    from datetime import datetime, timezone

    from app.core.config import settings as _settings
    from app.services.llm import ChatGPTOAuthError, ChatGPTOAuthProvider

    token = (_settings.openai_chatgpt_token or "").strip()
    if not token:
        typer.echo("OPENAI_CHATGPT_TOKEN is not set in .env.", err=True)
        raise typer.Exit(code=1)

    try:
        seg = token.split(".")[1]
        seg += "=" * (-len(seg) % 4)
        payload = json.loads(base64.urlsafe_b64decode(seg))
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Token is not a valid JWT: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    iat = datetime.fromtimestamp(payload.get("iat", 0), timezone.utc)
    exp = datetime.fromtimestamp(payload.get("exp", 0), timezone.utc)
    now = datetime.now(timezone.utc)
    auth = payload.get("https://api.openai.com/auth", {})
    profile = payload.get("https://api.openai.com/profile", {})

    typer.echo(f"Email:       {profile.get('email', '?')}")
    typer.echo(f"Plan:        {auth.get('chatgpt_plan_type', '?')}")
    typer.echo(f"Account ID:  {auth.get('chatgpt_account_id', '?')}")
    typer.echo(f"Issued:      {iat.isoformat()}")
    typer.echo(f"Expires:     {exp.isoformat()}")
    delta = exp - now
    if delta.total_seconds() <= 0:
        typer.echo("Status:      EXPIRED — refresh from chatgpt.com/api/auth/session", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Time left:   {delta}")

    typer.echo("\nPinging Codex backend (gpt-5.2)…")
    try:
        provider = ChatGPTOAuthProvider()
        resp = provider.chat(
            [
                {"role": "system", "content": "Reply with a single word."},
                {"role": "user", "content": "Reply with exactly: OK"},
            ]
        )
    except ChatGPTOAuthError as exc:
        typer.echo(f"Codex error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Codex reply: {resp.content!r}")
    typer.echo("Status:      OK ✓")


@app.command(name="reindex-document")
def reindex_document(document_id: str) -> None:
    """Re-run ingestion for a document."""
    db = SessionLocal()
    try:
        doc = db.get(Document, UUID(document_id))
        if doc is None:
            typer.echo("Not found.", err=True)
            raise typer.Exit(code=1)
        ingest_document_task.delay(str(doc.tenant_id), str(doc.id))
        typer.echo(f"Reindex queued for {document_id}")
    finally:
        db.close()


@app.command(name="ingest-laws")
def ingest_laws(
    directory: str = typer.Argument(..., help="Folder containing Saudi-law PDFs."),
    domain: str = typer.Option(
        ...,
        "--domain",
        "-d",
        help=(
            "Legal domain for every file in this batch. One of: "
            + ", ".join(d.value for d in LegalDomain)
        ),
    ),
    authority: str | None = typer.Option(
        None, "--authority", "-a", help="Issuing body (e.g. 'Ministry of Labor')."
    ),
    decree_number: str | None = typer.Option(
        None, "--decree", help="Royal decree / decision number (e.g. 'M/51')."
    ),
    enacted_at: str | None = typer.Option(
        None,
        "--enacted-at",
        help="Date of enactment (YYYY-MM-DD). Applies to every file in the batch.",
    ),
    version: str | None = typer.Option(
        None, "--version", help="Version label, e.g. '2023 amendment'."
    ),
    language: str = typer.Option(
        "auto",
        "--language",
        "-l",
        help="ar | en | auto. 'auto' detects per file from the text.",
    ),
    tenant_slug: str = typer.Option(
        "platform",
        "--tenant",
        help="Owning tenant slug. Default 'platform' = global corpus shared across all firms.",
    ),
    title_strategy: str = typer.Option(
        "filename",
        "--title-strategy",
        help="'filename' = use the filename without extension; 'first-line' = first non-empty line.",
    ),
    sync: bool = typer.Option(
        True,
        "--sync/--no-sync",
        help=(
            "Run ingestion in-process (--sync, default) or queue Celery jobs "
            "(--no-sync). Sync surfaces errors immediately; queueing is faster."
        ),
    ),
    pattern: str = typer.Option(
        "*.pdf",
        "--pattern",
        help="Glob pattern of files to ingest (e.g. '*.pdf', '*.docx', '*.{pdf,docx}').",
    ),
) -> None:
    """Bulk-import a folder of Saudi-law PDFs.

    Each file becomes a Document under the chosen tenant, with the supplied
    domain + authority + decree metadata stamped on every chunk. Run once
    per legal domain to keep your CLI invocation simple — the chunker
    auto-detects articles regardless.

    Example:
        python -m app.cli ingest-laws ./laws/labor \\
            --domain labor --authority "Ministry of Human Resources" \\
            --decree "M/51" --enacted-at 2005-09-27
    """
    configure_logging()
    try:
        domain_enum = LegalDomain(domain)
    except ValueError as exc:
        typer.echo(f"Invalid domain '{domain}'.", err=True)
        raise typer.Exit(code=2) from exc

    if language not in ("ar", "en", "auto"):
        typer.echo("--language must be one of: ar, en, auto.", err=True)
        raise typer.Exit(code=2)

    enacted_date = None
    if enacted_at:
        try:
            enacted_date = date.fromisoformat(enacted_at)
        except ValueError as exc:
            typer.echo("--enacted-at must be YYYY-MM-DD.", err=True)
            raise typer.Exit(code=2) from exc

    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        typer.echo(f"Not a directory: {root}", err=True)
        raise typer.Exit(code=2)

    files = sorted(p for p in root.glob(pattern) if p.is_file())
    if not files:
        typer.echo(f"No files matched {pattern} under {root}.", err=True)
        raise typer.Exit(code=1)

    db = SessionLocal()
    try:
        tenant = db.execute(
            select(Tenant).where(Tenant.slug == tenant_slug)
        ).scalar_one_or_none()
        if tenant is None:
            typer.echo(
                f"Tenant '{tenant_slug}' not found. Run `python -m app.cli seed` first "
                "to create the platform tenant.",
                err=True,
            )
            raise typer.Exit(code=1)

        try:
            ensure_bucket()
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Could not ensure bucket: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        successes = 0
        failures: list[tuple[str, str]] = []
        for path in files:
            try:
                _ingest_one_law_file(
                    db,
                    tenant=tenant,
                    path=path,
                    domain=domain_enum,
                    authority=authority,
                    decree_number=decree_number,
                    enacted_at=enacted_date,
                    version=version,
                    language=language,
                    title_strategy=title_strategy,
                    sync=sync,
                )
                successes += 1
                typer.echo(f"✓ {path.name}")
            except Exception as exc:  # noqa: BLE001
                failures.append((path.name, str(exc)))
                typer.echo(f"✗ {path.name}: {exc}", err=True)

        typer.echo(
            f"\nIngested {successes}/{len(files)} files into tenant '{tenant_slug}' "
            f"as domain={domain_enum.value}."
        )
        if failures:
            typer.echo(f"Failures: {len(failures)}")
            for name, err in failures:
                typer.echo(f"  - {name}: {err}")
            raise typer.Exit(code=1)
    finally:
        db.close()


def _ingest_one_law_file(
    db,
    *,
    tenant: Tenant,
    path: Path,
    domain: LegalDomain,
    authority: str | None,
    decree_number: str | None,
    enacted_at: date | None,
    version: str | None,
    language: str,
    title_strategy: str,
    sync: bool,
) -> None:
    """Upload + register + index a single law file."""
    raw = path.read_bytes()
    mime, _ = mimetypes.guess_type(path.name)
    if not mime:
        if path.suffix.lower() == ".pdf":
            mime = "application/pdf"
        elif path.suffix.lower() == ".docx":
            mime = (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
        else:
            mime = "application/octet-stream"

    pages = parse(raw, mime)
    if not pages:
        raise RuntimeError("parser returned 0 pages")

    if language == "auto":
        lang = detect_language(pages)
    else:
        lang = language

    title = _derive_title(path=path, pages=pages, strategy=title_strategy)

    doc_id = _uuid.uuid4()
    storage_key = storage_key_for(tenant.id, doc_id, path.name)
    upload_fileobj(storage_key, BytesIO(raw), mime)

    doc = Document(
        id=doc_id,
        tenant_id=tenant.id,
        title=title,
        source=DocumentSource.GLOBAL_DATASET
        if tenant.slug == "platform"
        else DocumentSource.UPLOAD,
        status=DocumentStatus.PROCESSING,
        storage_key=storage_key,
        mime_type=mime,
        byte_size=len(raw),
        page_count=len(pages),
        language=lang,
        legal_domain=domain,
        authority=authority,
        decree_number=decree_number,
        enacted_at=enacted_at,
        version=version,
        source_url=None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    if not sync:
        ingest_document_task.delay(str(tenant.id), str(doc.id))
        return

    chunks = chunk_legal_pages(pages, language=lang)
    n = index_document_chunks(
        db,
        tenant_id=tenant.id,
        document_id=doc.id,
        chunks=chunks,
        legal_domain=domain,
    )
    doc.status = DocumentStatus.INDEXED
    db.commit()
    log.info("ingest_laws_done", document_id=str(doc.id), chunks=n, file=path.name)


def _derive_title(
    *, path: Path, pages: list[tuple[int, str]], strategy: str
) -> str:
    if strategy == "first-line":
        for _, text in pages[:3]:
            for line in (text or "").splitlines():
                line = line.strip()
                if line and len(line) > 4:
                    return line[:300]
    return path.stem.replace("_", " ").strip()[:300]


if __name__ == "__main__":
    app()
