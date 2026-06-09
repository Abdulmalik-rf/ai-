// HTTP server the FastAPI side talks to. Only exposes the surface the API
// needs. Every request is auth'd via X-Bridge-Secret.
//
// Endpoints:
//   POST   /sessions/start         { tenant_id }       → status + qr (if pairing)
//   GET    /sessions/:tenant_id                          → status + qr (if pairing)
//   DELETE /sessions/:tenant_id                          → 204
//   POST   /messages/send          { tenant_id, to, text } → 204
//   GET    /health                                       → ok
//
// To run:
//   cd apps/whatsapp-bridge
//   cp .env.example .env  # set BRIDGE_SECRET to match the API .env
//   npm install
//   npm start

import express from 'express'

import { config } from './config.js'
import * as sessions from './sessions.js'

const app = express()
app.use(express.json({ limit: '1mb' }))

// Auth middleware — every endpoint except /health.
app.use((req, res, next) => {
  if (req.path === '/health') return next()
  const provided = req.header('X-Bridge-Secret')
  if (!provided || provided !== config.bridgeSecret) {
    return res.status(401).json({ error: 'invalid bridge secret' })
  }
  next()
})

app.get('/health', (_req, res) => res.json({ ok: true }))

app.post('/sessions/start', async (req, res) => {
  const tenantId = String(req.body?.tenant_id ?? '').trim()
  if (!tenantId) return res.status(400).json({ error: 'tenant_id required' })
  try {
    const session = sessions.getOrCreate(tenantId)
    const snapshot = await session.start()
    res.json(snapshot)
  } catch (err) {
    console.error(`[start ${tenantId}]`, err?.message ?? err)
    res.status(500).json({ error: String(err?.message ?? err) })
  }
})

app.get('/sessions/:tenantId', async (req, res) => {
  const tenantId = req.params.tenantId
  const session = sessions.get(tenantId)
  if (!session) {
    return res.json({
      status: 'disconnected',
      qr: null,
      phone_number: null,
      display_name: null,
      last_disconnect_reason: null,
    })
  }
  res.json(session.snapshot())
})

app.delete('/sessions/:tenantId', async (req, res) => {
  await sessions.destroy(req.params.tenantId)
  res.status(204).end()
})

app.post('/messages/send', async (req, res) => {
  const { tenant_id: tenantId, to, text } = req.body ?? {}
  if (!tenantId || !to || !text) {
    return res.status(400).json({ error: 'tenant_id, to, and text are required' })
  }
  const session = sessions.get(String(tenantId))
  if (!session) return res.status(409).json({ error: 'no session for tenant' })
  try {
    await session.sendText(String(to), String(text))
    res.status(204).end()
  } catch (err) {
    res.status(500).json({ error: String(err?.message ?? err) })
  }
})

// Catch-all error handler so a thrown promise doesn't crash the process.
app.use((err, _req, res, _next) => {
  console.error('[unhandled]', err?.message ?? err)
  res.status(500).json({ error: 'internal error' })
})

app.listen(config.port, async () => {
  console.log(`whatsapp-bridge listening on :${config.port}`)
  console.log(`API base: ${config.apiBaseUrl}`)
  console.log(`Auth dir: ${config.authDir}`)
  // Auto-resume already-paired tenants. Each session reconnects in the
  // background; messages received while the bridge was down show up via
  // Baileys' offline catch-up (messages.upsert with type === 'append').
  const resumed = await sessions.resumeAll().catch((err) => {
    console.error('[resume] failed:', err?.message ?? err)
    return []
  })
  if (resumed.length > 0) {
    console.log(`resumed ${resumed.length} tenant session(s): ${resumed.join(', ')}`)
  }
})
