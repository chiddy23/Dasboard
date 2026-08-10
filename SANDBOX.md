# JustInsurance Student Dashboard — SANDBOX

A **completely separate project** from production. Separate GitHub repo,
separate Render service, separate Absorb account. Nothing here can affect
`dashboard.justinsuranceco.com`.

| | Production | Sandbox (this repo) |
|---|---|---|
| Repo | `chiddy23/Dasboard` | `chiddy23/justinsurance-dashboard-sandbox` |
| Branch deployed | `main` | `main` |
| Render service | `dashboard.justinsuranceco.com` | `justinsurance-dashboard-sandbox` |
| Absorb account | `chad@justinsuranceco.com` | **`chadapitest`** |
| Runtime | Python (native) | Python (native) — same |
| Scheduler | off | off |

Git history is shared with prod up to `6fb70e2`, so commits can be cherry-picked
in either direction. See "Moving a feature to prod" below.

---

## Why the Absorb account must differ

Absorb is **single-session-per-account** — calling `/Authenticate` revokes the
previous token for that account. Two environments on one account revoke each
other's tokens on every login. That cost a 36-hour debugging marathon in
June 2026 before the cause was identified.

This sandbox uses **`chadapitest`**. Never point it at `chad@justinsuranceco.com`.

If a session ever misbehaves, the only reliable way to confirm which account is
actually in use is this log line:

```
[TOKEN REFRESH] Refreshed Absorb token for <username> (locked)
```

The `[LOGIN]` lines show only the department, not the user. Browser autofill has
silently substituted the wrong account before — trust the `[TOKEN REFRESH]` line
over what you think you typed.

---

## Render setup

**New** → **Web Service** → connect `chiddy23/justinsurance-dashboard-sandbox`.

Render will detect `render.yaml` and prefill the build and start commands. If you
configure manually instead, use exactly:

**Build**
```
cd frontend && npm install && npm run build && cd .. && pip install -r backend/requirements.txt
```

**Start**
```
cd backend && gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1 --threads 8
```

Set runtime to **Python** (not Docker) so it matches prod's runtime.

### Environment variables

Copy from prod's Environment tab (Render → prod service → Environment):

```
ABSORB_API_KEY
ABSORB_PRIVATE_KEY
GOOGLE_SHEETS_CREDENTIALS_JSON
```

These are tenant-level credentials shared across environments — the per-user
Absorb login is what differs, not the API key.

Set fresh, do **not** reuse prod's:

```
FLASK_SECRET_KEY       ← render.yaml generates this automatically
EXAM_ADMIN_PASSWORD    ← generate a new one
```

```powershell
# EXAM_ADMIN_PASSWORD
[Convert]::ToBase64String((1..24 | ForEach-Object { Get-Random -Min 0 -Max 256 })).Substring(0,32)
```

Leave **absent entirely** (not blank — absent):

```
SYNC_ABSORB_USERNAME
SYNC_ABSORB_PASSWORD
```

Boot log confirms the scheduler stayed off:

```
[SYNC SCHEDULER] Not started - set SYNC_ABSORB_USERNAME and SYNC_ABSORB_PASSWORD to enable
```

### Allowlist

`chadapitest` must be in the allowlist sheet (`AllowedUsers` tab) or it cannot
log in. The allowlist is shared infrastructure, not per-environment.

Note: if the allowlist table is **empty**, `is_user_allowed` returns `True` for
everyone — so an unseeded sandbox is open to any authenticated Absorb user.

---

## First-run verification

Each item has a specific signal, so "looks fine" isn't the bar.

- [ ] Boot log shows `[SYNC SCHEDULER] Not started - ...`
- [ ] `[TOKEN REFRESH]` line names **`chadapitest`**, not `chad@...`
- [ ] Load Spencer's dept `7905288A-4D07-4FCE-B4B6-761017F14513` (~1,316 users —
      the only dept large enough to trigger the year-bucket split path).
      Expect `[API] COMPLETE: multi-bucket path, ~1316 unique users`, then a
      matching count with enrollment data.
- [ ] **Isolation test:** while the sandbox is loading Spencer, use prod in
      another browser. Both must work. If either 401s, the two are sharing an
      Absorb account — stop and fix that before anything else.
- [ ] Dual-LOA student modal (OH/MI Life+Health): status text agrees with the
      progress bar — not "Not Started" beside a non-zero percentage.
- [ ] Multi-dept chips show real department names, not the literal `Department`.

---

## Config deltas from prod (deliberate)

Three fixes are applied here that prod does not have. Each is a candidate to
port back once validated:

**1. `--workers 1 --threads 8` instead of `--workers 4`**

Prod's `render.yaml` and `Procfile` both specify 4 workers. `Dockerfile:62`
specifies 1 worker and explains why: each gunicorn worker is a separate OS
process with its own `_latest_user_tokens` CAS map, `_active_user_logins`
zombie-guard, and `_last_mint_at` debounce dict. Four workers means four
processes minting Absorb tokens that revoke each other, with no visibility
across process boundaries. Threads share memory, giving concurrency without
the token war.

> **This is worth testing here first.** If prod is genuinely running 4 workers,
> it is a strong candidate root cause for the intermittent "no students"
> reports. Reproduce it: set the sandbox to `--workers 4`, hammer it, then drop
> to `--workers 1 --threads 8` and see whether the flakiness stops.

**2. `FLASK_SECRET_KEY` instead of `SECRET_KEY` in the blueprint**

Prod's `render.yaml` generates an env var named `SECRET_KEY`, but `config.py:15`
reads `FLASK_SECRET_KEY`. The generated value was never read — Flask silently
fell back to the literal `'dev-secret-key-change-in-production'` until the var
was set by hand in June 2026. Corrected here.

**3. `EXAM_ADMIN_PASSWORD` and `GOOGLE_SHEETS_CREDENTIALS_JSON` declared**

Both were missing from the prod blueprint entirely.

---

## Moving a feature to prod

The two repos share history up to `6fb70e2`, so cherry-pick works. From the
**prod** working copy:

```bash
cd C:/Users/Chidd/Downloads/justinsurance-student-dashboard
git remote add sandbox C:/Users/Chidd/Downloads/justinsurance-dashboard-sandbox
git fetch sandbox
git log --oneline main..sandbox/main        # what's new in the sandbox
git cherry-pick <sha>
python -m unittest discover -s backend/tests -p "test_*.py" -v
git push origin main
```

Run the 22 tests before every prod push. They pin the dual-LOA
`derive_combined_status` contract and are the only automated guard on that
logic — course classification and time-field fallbacks remain unpinned.

---

## Expected sandbox behaviors (not bugs)

- **Every deploy logs everyone out.** Flask sessions are filesystem-backed on
  Render's ephemeral disk. A restart also wipes `_student_cache`,
  `_dept_name_cache`, `_latest_user_tokens`, `_active_user_logins`, and
  `_last_mint_at`. Don't deploy while someone is mid-test.
- **A redeploy is the cure for a poisoned cache.** Root cause was fixed in
  `6fb70e2`, but the restart escape hatch is still worth knowing.
- **First load of a dept is slow; later loads are instant** — the student cache
  is warm.
- **Spencer takes 25–35 seconds** to load cold. That's why the gunicorn timeout
  is 120s.

---

## Rules carried over from prod — settled, do not re-litigate

- Keep the `Bearer ` prefix on Absorb calls. Bare token drops ~600 students on
  this tenant; tested three separate times.
- Keep the heartbeat a no-op. It must never call Absorb.
- No cookie handling in `set_token`. Absorb sets no cookies — proven `cookies=n=0`.
- Keep the per-user 3-retry in `_process_single_user`. Cutting it to 1 retry
  dropped 783 of Spencer's 1,302 students.
- When a token dies, don't blame TTL or "another login" without a log line
  proving it. That guess was wrong nine times out of ten.
- "Fresh token dies within 1–3 seconds of mint" is the account back-pressure
  signature. Stop shipping code and wait it out, or switch accounts.

Full detail lives in project memory under `feedback-dashboard-absorb-auth-rules`.
