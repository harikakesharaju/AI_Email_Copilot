# AI Email Copilot — Phase 1 (Gmail ingestion + classification + relationship-aware drafts)

This is a working skeleton: OAuth, scheduled Gmail polling, Gemini-based
classification/extraction, per-relationship-type tone drafting, and a basic
approval/feedback loop. No frontend yet — test everything via `/docs`.

## What's included
- `backend/app/models.py` — full data model (users, contacts, tone_profiles, emails, drafts, tasks, feedback)
- `backend/app/services/contacts.py` — relationship classification (work/family/friend/recruiter_hr/vendor_support)
- `backend/app/services/pipeline.py` — the whole ingestion → classify → embed → draft flow
- `backend/app/scheduler.py` — polls unread Gmail every 60s and runs new messages through the pipeline
- `backend/app/routers/` — OAuth and dashboard-API endpoints

## Step 1 — Google Cloud project (free)
1. Go to console.cloud.google.com → create a new project.
2. **APIs & Services → Library** → enable **Gmail API**.
3. **APIs & Services → Credentials** → Create Credentials → OAuth client ID → type "Web application".
   - Authorized redirect URI: `http://localhost:8000/auth/google/callback`
   - Copy the client ID and secret into `backend/.env`.

## Step 2 — Gemini API key (free, no card)
Go to aistudio.google.com → Get API key → copy it into `GEMINI_API_KEY` in `.env`.

## Step 3 — Environment
```bash
cd backend
cp .env.example .env
# fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GEMINI_API_KEY
```

## Step 4 — Run locally
```bash
docker compose up --build
```
This starts Postgres+pgvector and the FastAPI backend on `localhost:8000`.

The scheduler starts with the app and polls each connected mailbox for unread
messages every 60 seconds. No public tunnel or Pub/Sub setup is required.

## Step 5 — Connect your mailbox
Visit `http://localhost:8000/auth/google/login` in a browser, sign in, and grant
access. This stores your tokens. Within about a minute, unread inbox messages
are fetched and processed automatically.

## Step 6 — Test it
1. Send yourself a test email that asks a question ("Can you send the report by tomorrow?").
2. Leave it unread. Within about a minute, check:
   - `GET /api/emails` — the classified/summarized email
   - `GET /api/tasks` — the extracted deadline
   - Query the `drafts` table (or add a `GET /api/drafts` endpoint) to see the generated reply
3. Try `POST /api/drafts/{id}/edit` with different text — this logs a `feedback_events`
   row scoped to that contact's relationship type, which is the hook for Phase 4
   (style learning).

## Moving to production (still free)
- Swap `DATABASE_URL` in `.env` for your Supabase connection string (Project Settings →
  Database → Connection string). Run `Base.metadata.create_all` once against it, or better,
  set up Alembic migrations.
- Deploy `backend/` to Render as a free Web Service (connect the GitHub repo, it reads
  the Dockerfile automatically). Update `GOOGLE_REDIRECT_URI` to your Render URL.
- Keep the service warm enough that the 60-second poller can run (free Render instances
  can spin down when idle — wake with a request before a demo).

## What's next (Phase 2+, not yet built)
- `GET /api/drafts` + a `POST /api/drafts/{id}/send` that actually calls `gmail.send`
- Contact-confirmation UI for low-confidence relationship classifications
- Periodic job that summarizes `feedback_events` into updated `tone_profiles.tone_descriptor`
- Next.js dashboard consuming the `/api/*` endpoints
- Outlook/Microsoft Graph as a second provider
