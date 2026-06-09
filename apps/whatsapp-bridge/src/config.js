import 'dotenv/config'

export const config = {
  port: Number(process.env.PORT ?? 8787),
  bridgeSecret: process.env.BRIDGE_SECRET ?? '',
  apiBaseUrl: (process.env.API_BASE_URL ?? 'http://localhost:8000').replace(/\/+$/, ''),
  authDir: process.env.AUTH_DIR ?? './baileys_auth',
  qrRefreshMs: Number(process.env.QR_REFRESH_MS ?? 20000),
}

if (!config.bridgeSecret) {
  console.error('FATAL: BRIDGE_SECRET is empty. Set it (and match it on the API side).')
  process.exit(1)
}
