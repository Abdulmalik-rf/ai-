"""Email sender + templates.

Two backends:
  - "console" (default in dev): logs the email to stdout. Useful for local
    dev where SMTP isn't set up — you can copy the verification link from
    the log.
  - "smtp": ordinary smtplib client. Uses EMAIL_SMTP_* env vars.

Templates live inline (small, bilingual, easy to edit). Each returns a
(subject, text, html) triple.
"""
from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from textwrap import dedent

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class RenderedEmail:
    subject: str
    text: str
    html: str


# =============================================================================
# Backends
# =============================================================================


def _send_console(to: str, subject: str, text: str, html: str) -> None:
    log.info(
        "email_console",
        to=to,
        subject=subject,
        body_preview=text[:300],
    )
    # Also write to stdout so devs can copy verification links from the log.
    print("\n" + "=" * 70)
    print(f"[email] to={to}\n[email] subject={subject}")
    print("-" * 70)
    print(text)
    print("=" * 70 + "\n", flush=True)


def _send_smtp(to: str, subject: str, text: str, html: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.email_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    if settings.email_smtp_use_ssl:
        client = smtplib.SMTP_SSL(
            settings.email_smtp_host, settings.email_smtp_port, timeout=10
        )
    else:
        client = smtplib.SMTP(
            settings.email_smtp_host, settings.email_smtp_port, timeout=10
        )
        if settings.email_smtp_use_tls:
            client.starttls()
    try:
        if settings.email_smtp_user:
            client.login(settings.email_smtp_user, settings.email_smtp_password)
        client.send_message(msg)
    finally:
        client.quit()


def send_email(
    *, to: str, subject: str, text: str, html: str | None = None
) -> None:
    if not to:
        return
    backend = settings.email_backend
    body_html = html or text.replace("\n", "<br>")
    try:
        if backend == "smtp":
            _send_smtp(to, subject, text, body_html)
        else:
            _send_console(to, subject, text, body_html)
    except Exception:  # noqa: BLE001
        # Sending an email must never break the request. We log and move on —
        # the user can hit "resend" if needed.
        log.exception("email_send_failed", to=to, backend=backend)


# =============================================================================
# Templates
# =============================================================================
#
# Bilingual: each template builds an Arabic + English block back-to-back so
# the user sees their language without us asking. Saves having to thread
# `locale` through every caller.


def _link(base: str, path: str) -> str:
    return f"{base.rstrip('/')}{path}"


def _wrap_html(*, title: str, ar_block: str, en_block: str, cta_url: str | None, cta_label: str | None) -> str:
    """Bilingual HTML email wrapper. Inline CSS only (Gmail strips <style>)."""
    button_html = ""
    if cta_url and cta_label:
        button_html = (
            f'<table role="presentation" cellspacing="0" cellpadding="0" '
            f'style="margin:20px auto;"><tr><td style="background:#0f172a;'
            f'border-radius:8px;"><a href="{cta_url}" style="display:inline-block;'
            f'padding:12px 28px;color:#ffffff;text-decoration:none;font-weight:600;'
            f'font-family:Arial,Helvetica,sans-serif;">{cta_label}</a></td></tr></table>'
        )
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<title>{title}</title></head>'
        '<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;color:#111827;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        '<tr><td align="center" style="padding:32px 12px;">'
        '<table role="presentation" width="560" cellpadding="0" cellspacing="0" '
        'style="background:#ffffff;border-radius:12px;padding:40px 36px;text-align:left;">'
        '<tr><td style="font-size:18px;font-weight:700;color:#0f172a;padding-bottom:24px;">Legal AI OS</td></tr>'
        f'<tr><td style="font-size:15px;line-height:1.6;color:#1f2937;">{en_block}</td></tr>'
        f'<tr><td>{button_html}</td></tr>'
        '<tr><td style="border-top:1px solid #e5e7eb;padding-top:24px;'
        f'direction:rtl;text-align:right;font-size:15px;line-height:1.7;color:#1f2937;">{ar_block}</td></tr>'
        '<tr><td style="padding-top:32px;font-size:12px;color:#6b7280;">'
        '— Legal AI OS · Riyadh, Kingdom of Saudi Arabia'
        '</td></tr></table></td></tr></table></body></html>'
    )


def render_verification_email(*, to: str, token: str) -> RenderedEmail:
    url = _link(settings.app_base_url, f"/verify-email?token={token}")
    subject = "Verify your email — Legal AI OS / فعّل بريدك الإلكتروني"
    en = (
        f"Welcome to Legal AI OS.<br><br>Confirm your email address to "
        f"finish setting up your account. The link expires in "
        f"<b>{settings.email_verification_ttl_hours} hours</b>."
    )
    ar = (
        f"مرحبًا بك في Legal AI OS.<br><br>"
        f"لإكمال إعداد حسابك، فعّل بريدك الإلكتروني. ينتهي الرابط خلال "
        f"<b>{settings.email_verification_ttl_hours} ساعة</b>."
    )
    text = dedent(
        f"""
        Welcome to Legal AI OS — confirm your email:
        {url}

        ---

        مرحبًا بك في Legal AI OS — فعّل بريدك:
        {url}
        """
    ).strip()
    html = _wrap_html(
        title=subject,
        en_block=en,
        ar_block=ar,
        cta_url=url,
        cta_label="Verify email · تفعيل البريد",
    )
    return RenderedEmail(subject=subject, text=text, html=html)


def render_password_reset_email(*, to: str, token: str) -> RenderedEmail:
    url = _link(settings.app_base_url, f"/reset-password?token={token}")
    subject = "Reset your password — Legal AI OS / إعادة تعيين كلمة المرور"
    en = (
        f"You asked to reset your password. The link below is valid for "
        f"<b>{settings.password_reset_ttl_minutes} minutes</b>. If this "
        "wasn't you, ignore the email."
    )
    ar = (
        f"طلبت إعادة تعيين كلمة المرور. الرابط أدناه صالح لمدة "
        f"<b>{settings.password_reset_ttl_minutes} دقيقة</b>. إذا لم تطلب "
        "هذا، تجاهل الرسالة."
    )
    text = dedent(
        f"""
        Reset your password:
        {url}

        ---

        إعادة تعيين كلمة المرور:
        {url}
        """
    ).strip()
    html = _wrap_html(
        title=subject,
        en_block=en,
        ar_block=ar,
        cta_url=url,
        cta_label="Reset password · إعادة التعيين",
    )
    return RenderedEmail(subject=subject, text=text, html=html)


def render_invite_email(
    *, to: str, token: str, firm_name: str, role: str, inviter_name: str | None
) -> RenderedEmail:
    url = _link(settings.app_base_url, f"/accept-invite?token={token}")
    inviter = inviter_name or "your firm admin"
    subject = f"You're invited to {firm_name} on Legal AI OS"
    en = (
        f"<b>{inviter}</b> invited you to join <b>{firm_name}</b> on Legal AI OS "
        f"as <b>{role}</b>. The invitation expires in "
        f"<b>{settings.invite_ttl_days} days</b>."
    )
    ar = (
        f"دعاك <b>{inviter}</b> للانضمام إلى <b>{firm_name}</b> على Legal AI OS "
        f"بدور <b>{role}</b>. تنتهي الدعوة خلال "
        f"<b>{settings.invite_ttl_days} أيام</b>."
    )
    text = dedent(
        f"""
        {inviter} invited you to {firm_name} as {role}.
        Accept here: {url}

        ---

        دعاك {inviter} للانضمام إلى {firm_name} بدور {role}.
        قبول الدعوة: {url}
        """
    ).strip()
    html = _wrap_html(
        title=subject,
        en_block=en,
        ar_block=ar,
        cta_url=url,
        cta_label="Accept invitation · قبول الدعوة",
    )
    return RenderedEmail(subject=subject, text=text, html=html)
