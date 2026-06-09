// In-memory map: tenant_id → TenantSession.
//
// The bridge process holds at most one socket per tenant. On startup we
// scan the auth directory and auto-resume any tenants that already have
// credentials on disk — without this, paired tenants would silently miss
// every message until someone hit /sessions/start from the dashboard.

import fs from 'node:fs/promises'
import path from 'node:path'

import { config } from './config.js'
import { TenantSession } from './session.js'

const sessions = new Map()

export function getOrCreate(tenantId) {
  let s = sessions.get(tenantId)
  if (!s) {
    s = new TenantSession(tenantId)
    sessions.set(tenantId, s)
  }
  return s
}

export function get(tenantId) {
  return sessions.get(tenantId) ?? null
}

export async function destroy(tenantId) {
  const s = sessions.get(tenantId)
  if (!s) return
  await s.stop().catch(() => {})
  sessions.delete(tenantId)
}

// Tenant ids are UUIDs — anything else in the auth dir is junk we ignore.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export async function resumeAll() {
  let entries
  try {
    entries = await fs.readdir(config.authDir, { withFileTypes: true })
  } catch (err) {
    if (err?.code === 'ENOENT') return []
    console.error('[resume] could not read auth dir:', err?.message ?? err)
    return []
  }
  const resumed = []
  for (const entry of entries) {
    if (!entry.isDirectory()) continue
    const tenantId = entry.name
    if (!UUID_RE.test(tenantId)) continue
    // Only resume if there's actual creds.json — empty dirs from aborted
    // pairings shouldn't trigger a fresh QR.
    const credsPath = path.join(config.authDir, tenantId, 'creds.json')
    try {
      await fs.access(credsPath)
    } catch {
      continue
    }
    const session = getOrCreate(tenantId)
    session.start().catch((err) => {
      console.error(`[resume t:${tenantId}]`, err?.message ?? err)
    })
    resumed.push(tenantId)
  }
  return resumed
}
