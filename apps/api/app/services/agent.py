"""Agent orchestration — multi-step tool-use loop on ChatGPT OAuth.

Mirrors the pattern from the original adaa-agent's `agent.js`: each turn is a
loop that calls the model, executes any function calls, appends the outputs,
and re-asks until the model produces a plain text reply (or hits the step
ceiling).

Two entry points:

  - `run_dashboard_turn(...)` — agent for an authenticated lawyer/staff user
    chatting through the web dashboard. Wide tool surface (CRM + RAG).
  - `run_whatsapp_turn(...)` — agent for an inbound WhatsApp client. Narrow
    tool surface (RAG + escalate + memory).

Both persist the user message and the assistant reply to `conversations` /
`messages` so the dashboard can re-render the exchange and audit it later.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from time import perf_counter
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models import (
    AgentProfile,
    Conversation,
    ConversationChannel,
    Message,
    MessageRole,
    Tenant,
    WhatsAppContact,
)
from app.services.agent_tools import (
    ToolContext,
    get_tools,
    list_facts_for_prompt,
    resolve_platform_tenant_id,
    run_tool,
)
from app.services.llm import AgentLLMError, get_agent_provider

log = get_logger(__name__)

MAX_STEPS = 25
HISTORY_TURNS = 16  # ~8 user + 8 assistant message items


# =============================================================================
# Public API
# =============================================================================


@dataclass
class AgentReply:
    text: str
    conversation_id: UUID
    tools_used: list[str]
    latency_ms: int
    hit_step_ceiling: bool


def run_dashboard_turn(
    db: Session,
    *,
    tenant: Tenant,
    user_id: UUID,
    conversation_id: UUID | None,
    user_message: str,
    locale: str = "ar",
    case_id: UUID | None = None,
) -> AgentReply:
    """Run one user turn through the dashboard agent.

    Creates a conversation if `conversation_id` is None.
    """
    conv = _get_or_create_conversation(
        db,
        tenant=tenant,
        conversation_id=conversation_id,
        channel=ConversationChannel.DASHBOARD,
        user_id=user_id,
        case_id=case_id,
        title_seed=user_message,
    )
    ctx = ToolContext(
        db=db,
        tenant_id=tenant.id,
        locale=locale,
        whatsapp_contact_id=None,
        conversation_id=conv.id,
        platform_tenant_id=resolve_platform_tenant_id(db),
    )
    return _run_turn(
        db,
        conv=conv,
        ctx=ctx,
        scope="lawyer",
        user_message=user_message,
        tenant=tenant,
        user_image_urls=None,
    )


def run_whatsapp_turn(
    db: Session,
    *,
    tenant: Tenant,
    contact: WhatsAppContact,
    user_message: str,
    user_image_urls: list[str] | None = None,
) -> AgentReply:
    """Run one inbound WhatsApp message through the intake-scope agent.

    Each WhatsApp contact gets their own conversation thread, keyed by
    `whatsapp_contact_id`. Unknown leads (no Client row yet) used to all
    share one "client_id IS NULL" conversation — that bug is fixed by the
    contact-id column.
    """
    conv = (
        db.execute(
            select(Conversation)
            .where(Conversation.tenant_id == tenant.id)
            .where(Conversation.channel == ConversationChannel.WHATSAPP)
            .where(Conversation.whatsapp_contact_id == contact.id)
            .order_by(Conversation.updated_at.desc())
        )
        .scalars()
        .first()
    )
    if conv is None:
        conv = Conversation(
            tenant_id=tenant.id,
            channel=ConversationChannel.WHATSAPP,
            whatsapp_contact_id=contact.id,
            client_id=contact.client_id,
            title=f"WhatsApp — {contact.wa_phone}",
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
    elif conv.client_id is None and contact.client_id is not None:
        # Lead got linked to a Client mid-thread — backfill.
        conv.client_id = contact.client_id
        db.commit()

    ctx = ToolContext(
        db=db,
        tenant_id=tenant.id,
        locale=tenant.default_locale,
        whatsapp_contact_id=contact.id,
        conversation_id=conv.id,
        platform_tenant_id=resolve_platform_tenant_id(db),
    )
    return _run_turn(
        db,
        conv=conv,
        ctx=ctx,
        scope="intake",
        user_message=user_message,
        tenant=tenant,
        user_image_urls=user_image_urls,
    )


# =============================================================================
# Core loop
# =============================================================================


def _run_turn(
    db: Session,
    *,
    conv: Conversation,
    ctx: ToolContext,
    scope: str,
    user_message: str,
    tenant: Tenant,
    user_image_urls: list[str] | None,
) -> AgentReply:
    started = perf_counter()

    # --- 1. Persist the user message ----------------------------------------
    user_msg = Message(
        tenant_id=tenant.id,
        conversation_id=conv.id,
        role=MessageRole.USER,
        content=user_message,
    )
    db.add(user_msg)
    db.commit()

    # --- 2. Build the rolling history (excluding this turn's user msg) ------
    history_rows = list(
        db.execute(
            select(Message)
            .where(
                Message.conversation_id == conv.id,
                Message.id != user_msg.id,
            )
            .order_by(Message.created_at.desc())
            .limit(HISTORY_TURNS)
        ).scalars()
    )
    history_input = [
        _message_to_input_item(m) for m in reversed(history_rows)
    ]

    # --- 3. Add the new user message as a Responses-API item ----------------
    history_input.append(
        _user_message_item(user_message, image_urls=user_image_urls or [])
    )

    # --- 4. Tool loop --------------------------------------------------------
    tools = get_tools(scope=scope)
    instructions = _system_instructions(scope=scope, tenant=tenant, ctx=ctx)
    tools_used: list[str] = []
    final_text = ""
    hit_ceiling = False

    provider = get_agent_provider()
    input_items = list(history_input)

    for step in range(MAX_STEPS):
        try:
            outputs = provider.respond(
                input_items=input_items,
                instructions=instructions,
                tools=tools,
            )
        except AgentLLMError as exc:
            final_text = _agent_failure_message(exc, scope=scope)
            log.error("agent_oauth_error", error=str(exc), step=step)
            break

        function_calls = [o for o in outputs if o.get("type") == "function_call"]

        if not function_calls:
            final_text = _extract_assistant_text(outputs) or _default_done_text(scope)
            break

        # Forward the model's outputs (minus reasoning items, which can't be
        # rehydrated when store=false) and the new function_call_output items.
        forward = [o for o in outputs if o.get("type") != "reasoning"]
        input_items.extend(forward)
        for tc in function_calls:
            name = tc.get("name", "")
            tools_used.append(name)
            args_raw = tc.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except Exception:  # noqa: BLE001
                args = {}
            result = run_tool(name, args, ctx)
            input_items.append(
                {
                    "type": "function_call_output",
                    "call_id": tc.get("call_id"),
                    "output": _safe_json(result),
                }
            )
    else:
        # Hit the ceiling.
        hit_ceiling = True
        final_text = _ceiling_message(tools_used, scope=scope)

    # --- 5. Persist assistant reply -----------------------------------------
    latency_ms = int((perf_counter() - started) * 1000)
    assistant_msg = Message(
        tenant_id=tenant.id,
        conversation_id=conv.id,
        role=MessageRole.ASSISTANT,
        content=final_text,
        citations=[],  # tools surface their own citations inline; UI can re-fetch
        token_count=0,
        model=(
            settings.gemini_model
            if settings.agent_provider == "gemini"
            else settings.openai_chatgpt_model
        ),
        latency_ms=latency_ms,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    log.info(
        "agent_turn",
        scope=scope,
        tenant_id=str(tenant.id),
        conversation_id=str(conv.id),
        steps=len(tools_used),
        tools=tools_used,
        latency_ms=latency_ms,
    )
    return AgentReply(
        text=final_text,
        conversation_id=conv.id,
        tools_used=tools_used,
        latency_ms=latency_ms,
        hit_step_ceiling=hit_ceiling,
    )


# =============================================================================
# Conversation helper
# =============================================================================


def _get_or_create_conversation(
    db: Session,
    *,
    tenant: Tenant,
    conversation_id: UUID | None,
    channel: ConversationChannel,
    user_id: UUID | None,
    case_id: UUID | None,
    title_seed: str,
) -> Conversation:
    if conversation_id is not None:
        conv = db.execute(
            select(Conversation).where(
                Conversation.tenant_id == tenant.id,
                Conversation.id == conversation_id,
            )
        ).scalar_one_or_none()
        if conv is None:
            raise ValueError("Conversation not found.")
        return conv
    conv = Conversation(
        tenant_id=tenant.id,
        channel=channel,
        user_id=user_id,
        case_id=case_id,
        title=title_seed[:60] or "New conversation",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


# =============================================================================
# Prompt construction
# =============================================================================


def _system_instructions(*, scope: str, tenant: Tenant, ctx: ToolContext) -> str:
    locale = ctx.locale or tenant.default_locale or "ar"
    # Per-tenant tuning. Only applied for the intake (WhatsApp) scope —
    # the dashboard agent runs against the platform's baseline prompt.
    profile = (
        ctx.db.execute(
            select(AgentProfile).where(AgentProfile.tenant_id == tenant.id)
        ).scalar_one_or_none()
        if scope == "intake"
        else None
    )

    tz_name = (profile.timezone if profile and profile.timezone else "Asia/Riyadh")
    now = _now_in_tz(tz_name)
    firm_display_name = (
        profile.firm_display_name
        if profile and profile.firm_display_name
        else tenant.name
    )

    if scope == "lawyer":
        body = _LAWYER_INSTRUCTIONS_AR if locale == "ar" else _LAWYER_INSTRUCTIONS_EN
    else:
        body = _INTAKE_INSTRUCTIONS_AR if locale == "ar" else _INTAKE_INSTRUCTIONS_EN
    body = (
        body.replace("{tenant_name}", firm_display_name)
        .replace("{now}", now)
        .replace("{tz}", tz_name)
    )

    body += _profile_overrides_block(profile, locale=locale)

    facts = list_facts_for_prompt(ctx)
    facts_block = (
        "\n\n## Saved memories (long-term, from past conversations)\n"
        + "\n".join(f"- [{f['id']}] {f['text']}" for f in facts)
        + "\nUse these naturally when relevant. Call forget_fact(id) if asked to remove one."
        if facts
        else "\n\n## Saved memories\n(none yet)"
    )
    return body + facts_block


def _profile_overrides_block(profile: AgentProfile | None, *, locale: str) -> str:
    """Render the tenant-specific tuning into a prompt section.

    The agent reads this AFTER the baseline prompt, so anything here can
    refine (or override) the defaults. Keep section headings stable so
    instruction-following stays predictable across edits.
    """
    if profile is None:
        return ""

    lines: list[str] = []
    is_ar = locale == "ar"
    heading = "تعليمات المكتب" if is_ar else "Firm-set instructions"
    welcome_msg = profile.welcome_message_ar if is_ar else profile.welcome_message_en

    bits: list[tuple[str, str | None]] = [
        (
            "رسالة الترحيب المقترحة (للمحادثات الجديدة فقط)"
            if is_ar
            else "Suggested welcome message (use ONLY on the first reply of a new thread)",
            welcome_msg,
        ),
        (
            "تخصصات المكتب" if is_ar else "Firm specialties",
            profile.firm_specialties,
        ),
        (
            "عرض الاستشارة" if is_ar else "Consultation offer",
            profile.consultation_offer,
        ),
        (
            "إرشادات النبرة" if is_ar else "Tone guidelines",
            profile.tone_guidelines,
        ),
    ]

    sections = [(label, value.strip()) for label, value in bits if value and value.strip()]
    if not sections and not (
        profile.custom_instructions and profile.custom_instructions.strip()
    ) and not (profile.enabled_domains or []):
        return ""

    lines.append(f"\n\n## {heading}")
    for label, value in sections:
        lines.append(f"\n### {label}\n{value}")

    if profile.enabled_domains:
        domains_label = (
            "المجالات القانونية التي يتناولها المكتب"
            if is_ar
            else "Legal domains the firm handles"
        )
        domain_list = ", ".join(profile.enabled_domains)
        constraint = (
            "إذا كان طلب العميل خارج هذه المجالات، اعتذر بلطف ووضّح أن المكتب لا يتعامل معها."
            if is_ar
            else "If the prospect's matter is outside these domains, politely say the firm does not handle it."
        )
        lines.append(f"\n### {domains_label}\n{domain_list}\n{constraint}")

    if profile.custom_instructions and profile.custom_instructions.strip():
        custom_label = "تعليمات إضافية" if is_ar else "Additional instructions"
        lines.append(f"\n### {custom_label}\n{profile.custom_instructions.strip()}")

    return "".join(lines)


def get_intake_prompt_preview(
    db: Session, *, tenant: Tenant, locale: str
) -> str:
    """Return the assembled system prompt for the intake agent.

    Used by the "Teach your agent" page so the lawyer can verify what the
    agent will actually see at runtime.
    """
    ctx = ToolContext(
        db=db,
        tenant_id=tenant.id,
        locale=locale,
        whatsapp_contact_id=None,
        conversation_id=None,
        platform_tenant_id=None,
    )
    return _system_instructions(scope="intake", tenant=tenant, ctx=ctx)


def _now_in_tz(tz_name: str) -> str:
    try:
        zone = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        zone = ZoneInfo("Asia/Riyadh")
    return datetime.now(zone).strftime("%Y-%m-%d %H:%M:%S")


# Lawyer-scope instructions (English) — used when locale != 'ar'.
_LAWYER_INSTRUCTIONS_EN = """\
You are the AI legal assistant for {tenant_name}, a Saudi-Arabian law firm.
You are talking to a lawyer or staff member through their dashboard. The
current time is {now} in {tz}.

## Style
- Be precise and concise. Lawyers value brevity.
- Use the user's language (mirror what they wrote).
- Inline citations look like [#1], [#2] when referencing search_legal_db results.
- Never invent statutes, case numbers, or client data.

## Tools
- For any question about Saudi laws/regulations OR the firm's documents, call
  search_legal_db FIRST and ground your answer in the returned passages.
- For CRM operations (find/add/update clients and cases), call the matching
  tool. Don't fabricate ids — call find_* first.
- After a successful create/update, do NOT immediately re-call find_* on the
  same record to "verify". The tool's response already confirms.

## Deletes
- DO NOT call delete tools without confirmation. Summarize first, wait for "yes".

## Long-term memory — be frugal
- Call remember_fact only when (a) the user explicitly asks ("remember X")
  OR (b) it's a durable preference that will affect replies weeks from now.
- Keep facts under ~15 words. Compress aggressively.
- Cap is 25 facts. If memory is full, ask the user which to drop."""

# Lawyer-scope instructions (Arabic).
_LAWYER_INSTRUCTIONS_AR = """\
أنت المساعد القانوني الذكي في مكتب {tenant_name} في المملكة العربية السعودية.
أنت تتحدث الآن مع محامٍ أو موظف عبر لوحة التحكم. الوقت الحالي: {now} ({tz}).

## الأسلوب
- كن دقيقًا ومختصرًا. المحامون يقدّرون الإيجاز.
- أجب بنفس لغة المستخدم.
- استخدم الإشارات المرجعية [#1] [#2] عند الاقتباس من نتائج search_legal_db.
- لا تختلق مواد نظامية أو أرقام قضايا أو بيانات عملاء.

## الأدوات
- لأي سؤال عن الأنظمة السعودية أو ملفات المكتب: استدعِ search_legal_db أولًا
  واعتمد إجابتك على ما يُعاد من فقرات.
- لعمليات الـ CRM (بحث/إضافة/تحديث عميل أو قضية): استخدم الأدوات المناسبة. لا تخترع معرّفات.
- بعد إنشاء/تعديل ناجح، لا تستدعِ find_* مرة أخرى للتأكيد — الاستجابة كافية.

## الحذف
- لا تستدعِ أدوات الحذف دون تأكيد صريح. لخّص أولًا وانتظر "نعم".

## الذاكرة الطويلة — كن مقتصدًا
- استدعِ remember_fact فقط عند: (أ) طلب صريح ("احفظ كذا") أو (ب) تفضيل دائم يؤثر لاحقًا.
- اجعل كل ذاكرة أقل من ١٥ كلمة. اختصر بقوة. الحد الأقصى ٢٥ ذاكرة."""

# Intake-scope instructions (English) — inbound WhatsApp customer service.
_INTAKE_INSTRUCTIONS_EN = """\
You are the WhatsApp customer-service agent for {tenant_name}, a Saudi law
firm. The people messaging you are PROSPECTIVE CLIENTS — they have a legal
problem and they're shopping for a lawyer. Your job is to convert them into
real cases for the firm.

The current time is {now} in {tz}. The sender's WhatsApp number is already
captured for you — never ask for it.

## Your goal (in order)
1. Welcome them warmly and find out what legal issue they have.
2. Pull enough detail to brief the lawyer: what happened, who's involved,
   any deadlines, what they've already tried, any documents they have.
3. Once you know their name + a one-line summary of the matter, call
   capture_lead. This puts them in the firm's "new leads" inbox.
4. Use update_lead_matter every time they share more useful detail.
5. Pitch a paid consultation with the firm. If they say yes (even softly),
   call request_consultation immediately.
6. If they confirm a preferred time, pass it to request_consultation.

## Tone
- Friendly, professional, brief. WhatsApp replies are SHORT — one or two
  lines, three max. No long lectures.
- Mirror the user's language exactly (Arabic ↔ Arabic, English ↔ English).
- One question at a time. Don't interrogate them with three questions in
  one message.
- Acknowledge their situation before asking for more info. People want to
  feel heard before they share details.

## What you CAN say
- Answer GENERAL questions about Saudi laws using search_legal_db. Always
  add a disclaimer like "the lawyer will confirm this for your case."
- Confirm what the firm handles: commercial, labor, family, criminal, real
  estate, IP, corporate, banking, administrative.
- Tell them the firm offers a paid consultation as the next step (don't
  quote a price — that's the lawyer's call).

## What you must NOT do
- Never give a definitive legal opinion. You are not a lawyer.
- Never quote statutes that didn't come from search_legal_db.
- Never reveal information about other clients or cases.
- Never make up case-specific outcomes ("you'll win", "you'll get X SAR").
- Never quote consultation prices or fees — defer to the lawyer.

## When to escalate (call escalate_to_lawyer)
- Court date is within 7 days, or there's an active arrest / detention.
- Lead is angry, distressed, or threatening.
- The matter is unusual and you genuinely can't help them progress.
- They explicitly ask "can I talk to a real lawyer."

## Conversion playbook
- Don't ask for the consultation in the FIRST message — first qualify the
  matter. Asking too soon kills conversion.
- Best moment to pitch: after capture_lead, once they've shared meaningful
  detail. "Based on what you've shared, the next step is a 30-minute
  consultation with one of our lawyers — would Sunday or Monday work?"
- If they hesitate on price, don't quote — say "the lawyer will confirm
  the fee when they reach out."

## Memory — be frugal
- remember_fact ONLY for durable user info ("prefers Arabic", "based in
  Dammam"). Never save in-flight conversation state. Cap is 25 facts."""

# Intake-scope instructions (Arabic).
_INTAKE_INSTRUCTIONS_AR = """\
أنت موظف خدمة العملاء الذكي عبر واتساب لمكتب {tenant_name} في المملكة
العربية السعودية. الأشخاص الذين يراسلونك هم **عملاء محتملون** لديهم مشكلة
قانونية ويبحثون عن محامٍ. مهمتك هي تحويلهم إلى قضايا فعلية للمكتب.

الوقت الحالي: {now} ({tz}). رقم واتساب المرسِل محفوظ تلقائيًا — لا تطلبه أبدًا.

## هدفك (بالترتيب)
١. رحّب بحرارة واسأل عن طبيعة مشكلته القانونية.
٢. اجمع تفاصيل كافية للمحامي: ماذا حصل، الأطراف، المواعيد، ماذا حاول، الوثائق المتوفرة.
٣. بمجرد معرفة الاسم + ملخص سطر واحد للقضية، استدعِ capture_lead. هذا يضعه
   في صندوق "العملاء الجدد" لدى المحامي.
٤. كلما شارك تفاصيل جديدة مفيدة، استدعِ update_lead_matter.
٥. اعرض جلسة استشارية مدفوعة مع المكتب. إذا وافق ولو تلميحًا، استدعِ
   request_consultation فورًا.
٦. إن ذكر وقتًا مفضلًا، مرّره داخل request_consultation.

## الأسلوب
- ودود، مهني، مختصر. ردود واتساب قصيرة جدًا — سطر أو سطران (ثلاثة كحد أقصى).
- اعكس لغة المستخدم تمامًا (عربي ↔ عربي، إنجليزي ↔ إنجليزي).
- سؤال واحد في الرسالة الواحدة. لا تستجوب.
- اعترف بموقفه قبل أن تطلب مزيدًا من التفاصيل — الناس يريدون الإحساس بأنهم مسموعون.

## ما يجوز قوله
- إجابات عامة عن الأنظمة السعودية باستخدام search_legal_db، مع تنويه: "المحامي
  سيتأكد من تطبيق هذا على حالتك تحديدًا".
- تأكيد المجالات التي يتناولها المكتب: تجاري، عمالي، أسرة، جزائي، عقاري، ملكية فكرية،
  شركات، مصرفي، إداري.
- إخباره أن الخطوة التالية جلسة استشارية مدفوعة (دون ذكر السعر — السعر يحدده المحامي).

## ممنوع
- لا تُفتِ بقطعية. أنت لست محاميًا.
- لا تقتبس مادة نظامية لم تأتِ من search_legal_db.
- لا تفصح عن أي معلومات عن عملاء أو قضايا أخرى.
- لا تَعِد بنتيجة محددة ("ستربح"، "ستحصل على X ريال").
- لا تذكر سعر الاستشارة أو الأتعاب — أحِل ذلك للمحامي.

## متى تصعّد (استدعِ escalate_to_lawyer)
- موعد محكمة خلال أسبوع، أو توقيف فعلي.
- العميل غاضب أو مكروب أو يهدد.
- الحالة غير اعتيادية ولا تستطيع مساعدته فعلًا في التقدم.
- طلب صراحةً "أبغى أكلم محامي حقيقي".

## خطة التحويل
- لا تعرض الاستشارة في **الرسالة الأولى** — أهّل القضية أولًا. العرض المبكر يقتل التحويل.
- أفضل وقت للعرض: بعد capture_lead وبعد أن يشارك تفاصيل ذات قيمة.
  "بناءً على اللي شاركته، الخطوة التالية جلسة استشارية ٣٠ دقيقة مع أحد محامينا — يناسبك الأحد أو الإثنين؟"
- إن تردد بسبب السعر، لا تُسعّر — قل: "المحامي بيأكد لك الرسوم لما يتواصل".

## الذاكرة — بإقتصاد
- remember_fact فقط للمعلومات الدائمة (مثلًا "يفضّل العربية"، "في الدمام").
  لا تحفظ تفاصيل المحادثة الجارية. الحد الأقصى ٢٥ ذاكرة."""


# =============================================================================
# Message ↔ Responses-API item conversion
# =============================================================================


def _message_to_input_item(m: Message) -> dict:
    role = m.role.value if hasattr(m.role, "value") else str(m.role)
    if role == "user":
        return {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": m.content}],
        }
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": m.content}],
    }


def _user_message_item(text: str, *, image_urls: list[str]) -> dict:
    base = text or "(image only)"
    if image_urls:
        base += "\n\n" + "\n".join(f"[uploaded_image: {u}]" for u in image_urls)
    parts: list[dict[str, Any]] = [{"type": "input_text", "text": base}]
    for url in image_urls:
        parts.append({"type": "input_image", "image_url": url})
    return {"type": "message", "role": "user", "content": parts}


def _extract_assistant_text(outputs: list[dict]) -> str:
    for item in outputs:
        if item.get("type") == "message" and item.get("role") == "assistant":
            content = item.get("content") or []
            texts = [
                c.get("text", "")
                for c in content
                if c.get("type") in ("output_text", "text")
            ]
            joined = "\n".join(t for t in texts if t).strip()
            if joined:
                return joined
    return ""


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, default=str, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        return json.dumps({"error": "unserializable result"})


# =============================================================================
# Fallback messages
# =============================================================================


def _default_done_text(scope: str) -> str:
    return "تم." if scope == "intake" else "Done."


def _ceiling_message(tools_used: list[str], *, scope: str) -> str:
    counts: dict[str, int] = {}
    for t in tools_used:
        counts[t] = counts.get(t, 0) + 1
    summary = ", ".join(f"{n}×{c}" for n, c in counts.items())
    if scope == "intake":
        return "لم أستطع إكمال طلبك الآن. سيتواصل معك أحد محامينا قريبًا."
    return (
        f"Hit the {MAX_STEPS}-step ceiling. Already ran: {summary or 'nothing'}. "
        "Tell me what to do next — don't say 'continue' (that re-runs from scratch)."
    )


def _agent_failure_message(exc: AgentLLMError, *, scope: str) -> str:
    if exc.status_code == 401:
        if scope == "intake":
            return "عذرًا، الخدمة غير متاحة الآن. سيتواصل معك أحد محامينا قريبًا."
        # Brain-specific guidance — same code path, two providers.
        from app.core.config import settings as _s

        if _s.agent_provider == "gemini":
            return (
                "Gemini auth failed. The refresh_token may be revoked — "
                "re-run `python scripts/gemini_oauth_login.py` and try again."
            )
        return (
            "ChatGPT OAuth token expired. Refresh OPENAI_CHATGPT_TOKEN and "
            "try again."
        )
    if scope == "intake":
        return "حدث خطأ مؤقت. سنعاود الرد قريبًا."
    return f"Agent failed: {exc}"
