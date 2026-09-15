const path = require('path')
const fs   = require('fs')

// ---------------------------------------------------------------------------
// Load src/.env (the single shared env file) so that NEXT_PUBLIC_* variables
// defined there are available to Next.js at build time — without needing a
// separate src/frontend/.env.local file.
//
// Resolution order (same as dotenv):
//   1. Already-set environment variables (Docker build-args, CI, shell exports)
//      are NEVER overwritten — they take priority.
//   2. src/.env  — the shared file one level above src/frontend/
// ---------------------------------------------------------------------------
const sharedEnvPath = path.resolve(__dirname, '..', '.env')

if (fs.existsSync(sharedEnvPath)) {
  const lines = fs.readFileSync(sharedEnvPath, 'utf-8').split('\n')
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith('#')) continue
    const eqIdx = trimmed.indexOf('=')
    if (eqIdx === -1) continue
    const key = trimmed.slice(0, eqIdx).trim()
    const val = trimmed.slice(eqIdx + 1).trim()
    // Only inject NEXT_PUBLIC_* and never overwrite values already in the env
    // (e.g. passed via Docker --build-arg or CI variables).
    if (key.startsWith('NEXT_PUBLIC_') && !(key in process.env)) {
      process.env[key] = val
    }
  }
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  // 'standalone' is required for Docker (copies minimal server files into
  // .next/standalone). It must NOT be set on Vercel — Vercel manages its own
  // output format and errors if standalone is forced.
  // Set NEXT_OUTPUT=standalone in your Docker build env to enable it.
  ...(process.env.NEXT_OUTPUT === 'standalone' && { output: 'standalone' }),
}

module.exports = nextConfig
