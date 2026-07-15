---
name: run-app
description: Launch the Auto-Reply backend (FastAPI) and frontend (Next.js) and drive/screenshot them. Use when asked to "run the app", "start the server/client", "show me the dashboard/client UI", or verify a change end-to-end in the browser.
---

# Running Auto-Reply (backend + frontend)

Two parts: `server/` (FastAPI, uv-managed) and `frontend/` (Next.js, npm). Neither
has a fixed dev port baked in — pick free ports each time (see gotcha below).

## 1. Backend

```bash
cd server
uv sync                              # first time / after dependency changes
uv run python seed_admin.py          # creates the bootstrap admin (idempotent, uses .env)
uv run uvicorn app.main:app --host 127.0.0.1 --port 8010    # background it
```

Wait for real readiness, don't sleep-guess:
```bash
until curl -sf http://127.0.0.1:8010/health >/dev/null; do sleep 0.5; done
```

**Port 8000 gotcha:** on this machine port 8000 is already occupied by an
unrelated pre-existing service (health check returns `{"modems_online":...}`,
not this app). Don't kill it — just use a different port (8010 works, or check
`ss -ltnp | grep <port>` first).

## 2. Frontend

```bash
cd frontend
echo "NEXT_PUBLIC_API_BASE=http://localhost:8010" > .env.local   # match the backend port
npm run dev -- -p 3010
```

Wait for readiness the same way (`curl -sf http://localhost:3010/login`).

**CORS gotcha:** the backend's `.env` `CORS_ORIGINS` must include the exact
frontend origin (`http://localhost:3010`) or every fetch from the browser fails
with a CORS error, not an auth error — easy to misdiagnose. Edit
`server/.env`, then **restart the backend** (`Settings` is cached via
`lru_cache`, so it only re-reads `.env` on process start).

**Stray-process gotcha:** if a previous `npm start` (production) or `npm run
dev` was left running and never cleanly killed, Next.js may silently bind to a
*different* free port instead of the one you asked for while the old process
keeps squatting on your target port — `curl` against your target port then
hits stale content (e.g. an old `NEXT_PUBLIC_API_BASE` baked into the old
build). Before relaunching: `ss -ltnp | grep <port>` and confirm the PID
matches what you just started; if not, `kill -9 <pid>` the stray one and
`rm -rf frontend/.next` to drop any stale cache, then relaunch.

## 3. Seeding realistic demo data (for screenshots / manual testing)

```bash
B=http://127.0.0.1:8010
ADMIN_TOKEN=$(curl -s -X POST $B/auth/login -d "username=admin&password=admin123" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X POST $B/users -H "Authorization: Bearer $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"user_id":"ali_khan","zone_section":"North","password":"pass123"}'

ALI_TOKEN=$(curl -s -X POST $B/auth/login -d "username=ali_khan&password=pass123" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -s -X POST $B/requests -H "Authorization: Bearer $ALI_TOKEN" -H "Content-Type: application/json" \
  -d '{"numbers":["03001234567"],"duration_days":90,"case_officer":"Sana","justification":"demo","request_date":"2026-07-14"}'

# Trigger an auto-match (drop a file with the number+date directly in main/'s top level):
printf 'demo' > main/03001234567_2026-07-14.pdf
```

## 4. Driving it with a browser (no `chromium-cli` here)

This environment doesn't have `chromium-cli`. Use Playwright directly instead —
it's already a `frontend/devDependencies` entry and Chromium is already
downloaded (`npx playwright install chromium` — only needed once per machine).

Write a `.mjs` script **inside `frontend/`** (so the local `playwright`
resolves) and run with `node`:

```js
import { chromium } from "playwright";
const browser = await chromium.launch({ args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
page.on("pageerror", (e) => console.log("[pageerror]", String(e)));

await page.goto("http://localhost:3010/login", { waitUntil: "networkidle" });
await page.locator("input").nth(0).fill("ali_khan");   // User ID field
await page.locator("input").nth(1).fill("pass123");    // Password field
await page.click('button:has-text("Sign in")');
await page.waitForURL("http://localhost:3010/client", { timeout: 15000 });
await page.waitForSelector("text=My Requests");
await page.screenshot({ path: "/tmp/client.png", fullPage: true });
await browser.close();
```

Same pattern for `admin` / `admin123` → redirects to `/dashboard`.

Delete the throwaway `.mjs` script after use; keep `playwright` in
`package.json` and the cached Chromium install so the next run doesn't pay the
install cost again.

## 5. Stopping

```bash
pkill -f "uvicorn app.main"
pkill -f "next dev"
```
