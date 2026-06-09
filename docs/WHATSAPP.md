# WhatsApp integration

Two phases: **inbound** (clients message the firm) and **outbound** (firm /
assistant message clients).

## Provider

[Twilio WhatsApp](https://www.twilio.com/docs/whatsapp). The same code also
works for Meta's WhatsApp Cloud API with minor adjustments to the send
function — both speak HTTPS+JSON.

## Setup checklist

1. **Twilio account** — note `Account SID` + `Auth Token`.
2. **WhatsApp sender** — either the Twilio sandbox number (dev) or a
   business number connected to a verified WABA (production).
3. Set environment variables:
   ```
   TWILIO_ACCOUNT_SID=AC...
   TWILIO_AUTH_TOKEN=...
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   ```
4. Configure the **inbound webhook** in Twilio's console:
   `https://<your-domain>/webhooks/whatsapp` (POST, form-encoded).

## Inbound flow

```
Twilio → POST /webhooks/whatsapp (form: From, To, Body)
       → handle_inbound:
            - resolve tenant by destination number (`To`)
            - upsert WhatsAppContact for the sender (`From`)
            - find/create a WHATSAPP-channel Conversation
            - persist user Message
            - run RAG (with WhatsApp-specific system prompt)
            - persist assistant Message + citations
            - if reply contains [ESCALATE], record WhatsAppEscalation
            - send the reply outbound via Twilio REST
       → respond with empty TwiML so Twilio does not double-deliver
```

## Outbound

`services/whatsapp.send_message(to_phone, body)` POSTs to
`https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json`
with Basic-auth `{SID}:{TOKEN}`.

## Tenant routing

For MVP, a single Twilio sender belongs to a single tenant — the resolver
just returns the first active tenant. In production:

1. Add a `tenant_channels` table mapping `(provider, sender)` → `tenant_id`.
2. Update `resolve_tenant_for_inbound` to query it.
3. In the admin panel, allow a tenant admin to claim a sender after Twilio
   provisioning.

## Escalation UX

When the assistant responds with `[ESCALATE]` (the prompt asks it to add
this for sensitive or unclear matters), the backend:

1. Strips the sentinel before sending to the client.
2. Records a `WhatsAppEscalation` row tied to the conversation.
3. The dashboard shows a red badge on the conversation list and the lawyer
   can pick it up — replies from the dashboard send via the same
   `send_message` path so the client just sees a continuous chat.

## Compliance notes

- Saudi PDPL: never store payment cards / sensitive auth data over WhatsApp.
- Twilio retains message metadata; treat WhatsApp as untrusted for
  attorney-client privileged content.
- Provide a `STOP` keyword handler if you offer notifications.
