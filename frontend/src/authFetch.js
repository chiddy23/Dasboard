// ── Single mint authority (browser side) ────────────────────────────
// Data routes never refresh Absorb tokens server-side — an abandoned
// request's mint could revoke the live session minutes later (the
// 2026-08-12 token wars). When any response reports an expired token,
// every caller in every component funnels through this ONE single-flight
// refresh: at most one /auth/refresh-token call in flight per tab, and
// the refreshed cookie is shared by all subsequent requests (and tabs).
const API_BASE = '/api'

let _refreshPromise = null

export const ensureFreshToken = async () => {
  if (!_refreshPromise) {
    _refreshPromise = fetch(`${API_BASE}/auth/refresh-token`, {
      method: 'POST',
      credentials: 'include',
    })
      .then(r => (r.ok ? r.json() : { success: false }))
      .catch(() => ({ success: false }))
    _refreshPromise.finally(() => {
      // Hold the settled promise briefly so a burst of callers dedupes,
      // then clear so a later genuine expiry can refresh again.
      setTimeout(() => { _refreshPromise = null }, 2000)
    })
  }
  const res = await _refreshPromise
  return !!(res && res.success)
}

// fetch() that treats a 401 as "token expired": refresh once (single-
// flight) and retry with the new cookie. Only a post-refresh 401 —
// a genuinely dead session — reaches the caller.
export const fetchWithAuthRetry = async (url, opts) => {
  let res = await fetch(url, opts)
  if (res.status === 401 && await ensureFreshToken()) {
    res = await fetch(url, opts)
  }
  return res
}
