// One Baileys socket per tenant. Wrapped so the bridge HTTP layer can:
//   - kick off pairing (start)
//   - read current QR / status (status)
//   - send messages (sendText)
//   - tear down + delete auth files (stop)
//
// Reconnect strategy: if the connection drops for any reason other than an
// explicit logout, we retry with a 2s delay. logged-out connections require
// a fresh QR — we expose that as `LOGGED_OUT` and let the FastAPI side
// decide whether to re-pair automatically.

import path from 'node:path'
import fs from 'node:fs/promises'
import baileys, {
  DisconnectReason,
  fetchLatestBaileysVersion,
  useMultiFileAuthState,
  downloadContentFromMessage,
} from '@whiskeysockets/baileys'
import pino from 'pino'

import { config } from './config.js'
import { notifyInbound, notifySessionUpdate } from './api-client.js'

const makeWASocket = baileys.default ?? baileys.makeWASocket ?? baileys

const MAX_IMAGE_BYTES = 8 * 1024 * 1024

export const STATUS = Object.freeze({
  DISCONNECTED: 'disconnected',
  PAIRING: 'pairing',
  CONNECTED: 'connected',
  LOGGED_OUT: 'logged_out',
  ERROR: 'error',
})

export class TenantSession {
  constructor(tenantId) {
    this.tenantId = tenantId
    this.authDir = path.join(config.authDir, tenantId)
    this.sock = null
    this.status = STATUS.DISCONNECTED
    this.qr = null
    this.phoneNumber = null
    this.displayName = null
    this.lastDisconnectReason = null
    this._reconnectTimer = null
    this._stopping = false
    // Resolves the next time we transition to PAIRING (qr ready) or
    // CONNECTED. start() awaits this so the dashboard gets a meaningful
    // first response instead of a stale "disconnected".
    this._readyResolvers = []
  }

  // -- Public ---------------------------------------------------------------

  async start({ waitMs = 4000 } = {}) {
    if (this.sock && (this.status === STATUS.CONNECTED || this.status === STATUS.PAIRING)) {
      return this.snapshot()
    }
    this._stopping = false
    await this._connect()
    // Hold the response open briefly so the dashboard sees the QR or
    // connection on the very first request — without this the frontend
    // would have to poll for ~1-2s before seeing anything.
    if (waitMs > 0 && this.status !== STATUS.CONNECTED && this.status !== STATUS.PAIRING) {
      await this._waitForReady(waitMs)
    }
    return this.snapshot()
  }

  _waitForReady(timeoutMs) {
    return new Promise((resolve) => {
      let done = false
      const finish = () => {
        if (done) return
        done = true
        clearTimeout(timer)
        resolve()
      }
      const timer = setTimeout(finish, timeoutMs)
      this._readyResolvers.push(finish)
    })
  }

  _flushReady() {
    const fns = this._readyResolvers
    this._readyResolvers = []
    for (const fn of fns) {
      try { fn() } catch {}
    }
  }

  async stop() {
    this._stopping = true
    if (this._reconnectTimer) {
      clearTimeout(this._reconnectTimer)
      this._reconnectTimer = null
    }
    if (this.sock) {
      try {
        await this.sock.logout().catch(() => {})
      } finally {
        try { this.sock.end?.() } catch {}
        this.sock = null
      }
    }
    await fs.rm(this.authDir, { recursive: true, force: true }).catch(() => {})
    this._setStatus(STATUS.DISCONNECTED, { reason: 'Stopped by API.' })
  }

  async sendText(to, text) {
    if (!this.sock || this.status !== STATUS.CONNECTED) {
      throw new Error(`Cannot send — session is ${this.status}.`)
    }
    const jid = jidFor(to)
    await this.sock.sendMessage(jid, { text })
  }

  snapshot() {
    return {
      status: this.status,
      qr: this.status === STATUS.PAIRING ? this.qr : null,
      phone_number: this.phoneNumber,
      display_name: this.displayName,
      last_disconnect_reason: this.lastDisconnectReason,
    }
  }

  // -- Internals ------------------------------------------------------------

  async _connect() {
    await fs.mkdir(this.authDir, { recursive: true })
    const { state, saveCreds } = await useMultiFileAuthState(this.authDir)
    const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: undefined }))

    const sock = makeWASocket({
      auth: state,
      logger: pino({ level: 'silent' }),
      printQRInTerminal: false,
      browser: ['Legal AI OS', 'Chrome', '1.0.0'],
      version,
      syncFullHistory: false,
    })
    this.sock = sock
    sock.ev.on('creds.update', saveCreds)

    sock.ev.on('connection.update', (update) => this._onConnectionUpdate(update))
    sock.ev.on('messages.upsert', (m) => this._onMessages(m).catch((err) => {
      console.error(`[t:${this.tenantId}] message handler crashed:`, err?.message ?? err)
    }))
  }

  _onConnectionUpdate({ connection, qr, lastDisconnect }) {
    if (qr) {
      this.qr = qr
      this._setStatus(STATUS.PAIRING)
    }
    if (connection === 'open') {
      this.qr = null
      this.lastDisconnectReason = null
      const meId = this.sock?.user?.id ?? ''
      this.phoneNumber = parsePhoneFromJid(meId)
      this.displayName = this.sock?.user?.name ?? null
      this._setStatus(STATUS.CONNECTED)
      console.log(`[t:${this.tenantId}] connected as ${this.phoneNumber}`)
    }
    if (connection === 'close') {
      const code = lastDisconnect?.error?.output?.statusCode
      const loggedOut = code === DisconnectReason.loggedOut
      const reason = loggedOut
        ? 'Logged out. Re-pair to reconnect.'
        : `Disconnected (${code ?? 'unknown'}). Reconnecting…`
      console.log(`[t:${this.tenantId}] ${reason}`)
      if (loggedOut) {
        this._setStatus(STATUS.LOGGED_OUT, { reason })
      } else {
        this._setStatus(STATUS.DISCONNECTED, { reason })
        if (!this._stopping) {
          this._reconnectTimer = setTimeout(
            () => this._connect().catch((err) => {
              console.error(`[t:${this.tenantId}] reconnect failed:`, err?.message ?? err)
              this._setStatus(STATUS.ERROR, { reason: String(err?.message ?? err) })
            }),
            2000,
          )
        }
      }
    }
  }

  async _onMessages({ messages, type }) {
    if (type !== 'notify' && type !== 'append') return
    for (const msg of messages) {
      try {
        await this._handleOne(msg)
      } catch (err) {
        console.error(`[t:${this.tenantId}] handler error:`, err?.message ?? err)
      }
    }
  }

  async _handleOne(msg) {
    if (!msg.message) return
    if (msg.key.fromMe) return
    const jid = msg.key.remoteJid
    if (!jid) return
    if (jid.endsWith('@g.us')) return  // ignore group messages
    if (jid.endsWith('@broadcast')) return

    const sender = parsePhoneFromJid(jid)
    if (!sender) return

    const text = extractText(msg)
    let imageDataUrl = null
    const im = msg.message?.imageMessage
    if (im) {
      try {
        const stream = await downloadContentFromMessage(im, 'image')
        const chunks = []
        for await (const c of stream) chunks.push(c)
        const buf = Buffer.concat(chunks)
        if (buf.length > MAX_IMAGE_BYTES) {
          await this.sock.sendMessage(jid, { text: 'Image too large (>8 MB).' })
          return
        }
        const mime = im.mimetype || 'image/jpeg'
        imageDataUrl = `data:${mime};base64,${buf.toString('base64')}`
      } catch (err) {
        await this.sock.sendMessage(jid, { text: `Could not read image: ${err?.message ?? 'unknown'}` })
        return
      }
    }

    if (!text && !imageDataUrl) return

    try { await this.sock.sendPresenceUpdate('composing', jid) } catch {}

    const reply = await notifyInbound({
      tenant_id: this.tenantId,
      from_phone: sender,
      text,
      image_data_url: imageDataUrl,
      timestamp: Number(msg.messageTimestamp ?? 0) || null,
    })

    try { await this.sock.sendPresenceUpdate('paused', jid) } catch {}

    const replyText = reply?.text?.trim()
    if (replyText) {
      try {
        await this.sock.sendMessage(jid, { text: replyText })
      } catch (err) {
        console.error(`[t:${this.tenantId}] send failed:`, err?.message ?? err)
      }
    }
  }

  _setStatus(next, { reason } = {}) {
    this.status = next
    if (reason !== undefined) this.lastDisconnectReason = reason
    // PAIRING and CONNECTED are the two "ready to respond" transitions —
    // unblock any start() callers waiting on them.
    if (next === STATUS.PAIRING || next === STATUS.CONNECTED) {
      this._flushReady()
    }
    notifySessionUpdate({
      tenant_id: this.tenantId,
      status: next,
      qr: this.qr,
      phone_number: this.phoneNumber,
      display_name: this.displayName,
      last_disconnect_reason: this.lastDisconnectReason,
    })
  }
}

// -- Pure helpers -----------------------------------------------------------

function jidFor(to) {
  if (typeof to !== 'string') throw new Error('to must be a string')
  if (to.includes('@')) return to
  const digits = to.replace(/\D+/g, '')
  if (!digits) throw new Error(`invalid recipient: ${to}`)
  return `${digits}@s.whatsapp.net`
}

function parsePhoneFromJid(jid) {
  if (!jid) return null
  // Forms we see: 9665XXXX@s.whatsapp.net, 9665XXXX:7@s.whatsapp.net,
  // <lid>@lid. We want the digits before the first @ (and before any :).
  const before = String(jid).split('@')[0]
  const cleaned = before.split(':')[0]
  return cleaned.replace(/\D+/g, '') || null
}

function extractText(msg) {
  const m = msg.message ?? {}
  return (
    m.conversation ??
    m.extendedTextMessage?.text ??
    m.imageMessage?.caption ??
    m.videoMessage?.caption ??
    ''
  ).trim()
}
