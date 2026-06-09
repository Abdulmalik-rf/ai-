// HTTP client for the FastAPI side. Two callbacks:
//   - notifyInbound: bridge → /webhooks/whatsapp-baileys (per inbound message)
//   - notifySessionUpdate: bridge → /webhooks/whatsapp-baileys/session (per state change)
//
// Both auth with X-Bridge-Secret. On network errors we log and move on —
// the next event will retry. We don't want a flaky API to wedge sockets.

import { config } from './config.js'

const headers = () => ({
  'Content-Type': 'application/json',
  'X-Bridge-Secret': config.bridgeSecret,
})

export async function notifyInbound(payload) {
  const url = `${config.apiBaseUrl}/webhooks/whatsapp-baileys`
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const body = await res.text().catch(() => '')
      console.error(`[api] inbound ${res.status}: ${body.slice(0, 200)}`)
      return null
    }
    return await res.json().catch(() => ({}))
  } catch (err) {
    console.error('[api] inbound failed:', err?.message ?? err)
    return null
  }
}

export async function notifySessionUpdate(payload) {
  const url = `${config.apiBaseUrl}/webhooks/whatsapp-baileys/session`
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify(payload),
    })
    if (!res.ok) {
      const body = await res.text().catch(() => '')
      console.error(`[api] session-update ${res.status}: ${body.slice(0, 200)}`)
    }
  } catch (err) {
    console.error('[api] session-update failed:', err?.message ?? err)
  }
}
