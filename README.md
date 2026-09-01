# InviSense — Exam Integrity System

A Django app for running paperless exam-hall verification: QR-based seat
check-in, silent incident alerts, and a live control-room feed.

## What changed in this rebuild

**Same core logic, hardened and completed:**
- Fixed: invigilators could never actually be assigned to a hall before (the
  field existed but no screen used it). Added a **Session detail** page
  where halls get an invigilator from a dropdown.
- Fixed: there was no way to close a finished session — sessions stayed
  "active" forever. Added an open/close toggle.
- Fixed: `@csrf_exempt` was set on the two JSON endpoints even though the
  front-end was already sending a CSRF token — removed the exemption so
  CSRF protection is actually enforced.
- Fixed: duplicate rows in an uploaded CSV silently created duplicate
  students. Added a database uniqueness constraint (`session` + `roll_number`
  + `subject_code`) plus a pre-check that reports how many rows were
  skipped and why.
- Fixed: scanning the same student twice just re-verified them with no
  feedback. It now says "already checked in."
- Added: an admin **Staff** screen to create invigilator / control-room
  logins from the UI instead of editing a script.
- Added: CSV export of a session's full incident log for reporting.
- Added: pagination on the reports list, indexes on the columns that get
  filtered/joined most, and `Meta.ordering` everywhere so list order is
  deterministic.
- Added: environment-driven security settings (cookies, HSTS, allowed
  hosts), structured logging, and Whitenoise for serving static files in
  production — so `DEBUG=False` is actually deployable, not just a flag.
- Renamed the built-in Django admin URL to `/django-admin/` so it doesn't
  sit next to the app's own `/admin-dashboard/`.

**Interface:** fully rebuilt from scratch — a quiet, editorial "paper &
ink" look (warm white surfaces, a single clay accent, hairline rules
instead of drop shadows/glass blur) with its own structure: a top bar
instead of a floating sidebar, an inline SVG icon set instead of an icon
font, and a split-screen sign-in screen. Every CSS class is namespaced
`isx-*` and is unique to this project.

## Project structure

```
invisense/           project settings, root urls
core/                the app: models, views, urls, admin
templates/           all HTML, organised by role (admin/invigilator/control_room)
templates/partials/  shared inline-SVG icon partial
static/css/          styles.css — the whole design system, one file
create_users.py      seeds demo accounts for all three roles
```

## Local setup (PyCharm or terminal)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # already provided with dev-safe defaults
python manage.py migrate
python create_users.py           # seeds admin / invigilator1 / controlroom
python manage.py runserver
```

Open `http://127.0.0.1:8000/` and sign in with one of the seeded accounts
(shown on the login screen). In PyCharm: open the folder as a project, point
the Python interpreter at `.venv`, then run `manage.py` with the `runserver`
argument from the Run Configuration, or just use the terminal commands above.

### Everyday workflow

1. **Admin** creates a session (`Setup Exam`) — just the date, shift, and
   each hall's *capacity* (how many seats it has). No row planning needed.
2. **Admin** opens the session and assigns one invigilator per hall.
3. **Admin** uploads a roster CSV (`Upload Roster` — just `roll_number,
   name, subject_code`, no seating info) for one or more departments/exams
   sitting together.
4. **Admin** clicks **Auto-allocate seating** on the session page. This
   fills every hall to capacity and interleaves subject/department codes so
   neighbouring seats differ where possible (zig-zag anti-copying seating) —
   then generates each student's QR code.
5. **Admin** downloads **Hall tickets (PDF)** — one printable ticket per
   student (name, roll no., subject, hall/row/seat, QR code), two per A4
   page, ready to print and hand out.
6. **Invigilator** opens `Scan & Verify`, scans each student's ticket QR;
   the app confirms the hall/seat or warns if it's the wrong hall — this
   check is based on the invigilator's *login*, not a separate invigilator
   QR code, so there's nothing extra to print or lose. The invigilator can
   raise a silent alert straight from a scan result.
7. **Control room** watches `Live Feed` for incoming alerts and acknowledges
   / resolves them; `Reports` gives a per-session log with CSV export.

If you already have a fixed seating plan you don't want auto-allocated,
`Upload Roster` also accepts the original format with `hall_number, row,
seat` columns added — those rows are seated exactly as specified instead.

### Since the last update

- **Live hall roster.** The invigilator's scan screen now also shows every
  student assigned to their hall with a Present / Not yet tag, updating
  every few seconds without restarting the camera. A "Flag" link sits next
  to each checked-in student.
- **Flag any scanned student, not just the last one.** `Raise Alert` now
  offers a dropdown of everyone already checked in for that hall (row, seat,
  and name shown), instead of only being reachable right after a scan.
- **Per-subject exam time.** The roster CSV accepts an optional `exam_time`
  column (e.g. `9:30–11:30 AM`) so two departments sharing a shift — say
  MCA and iMCA — can each show their own timing on their hall ticket. Leave
  it blank to fall back to the session's shift label.

## Connecting to Supabase

The project ships pointed at local SQLite so it runs with zero setup, but
it's built to switch to a real Postgres database — like Supabase — by
changing one line in `.env`. No code changes needed.

### 1. Create the Supabase project

1. Go to [supabase.com](https://supabase.com) and sign in (GitHub login is
   fastest).
2. Click **New Project**.
3. Pick your organisation, give it a name (e.g. `invisense`), and set a
   **database password** — write this down, you'll need it in a moment and
   Supabase won't show it again.
4. Pick a region close to your college/server, then **Create new project**.
5. Wait about a minute while it provisions.

### 2. Get the connection string

1. In your new project, click **Connect** (top bar) — or **Project
   Settings → Database**.
2. Under **Connection string**, choose the **Session pooler** tab (not
   "Transaction pooler" — Django doesn't play well with that one, and not
   "Direct connection" unless you know you want it — the session pooler is
   the right default here).
3. Copy the URI. It looks like:
   ```
   postgresql://postgres.xxxxxxxxxxxx:[YOUR-PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
   ```
4. Replace `[YOUR-PASSWORD]` with the database password from step 1.

### 3. Point the project at it

Open `.env` and add (or uncomment) this line with your real connection
string:

```
DATABASE_URL=postgresql://postgres.xxxxxxxxxxxx:your-real-password@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```

That's the only change required — `settings.py` detects it's Postgres and
automatically enables SSL and connection reuse.

### 4. Create the tables and seed accounts

```bash
pip install -r requirements.txt   # psycopg2-binary is already listed
python manage.py migrate          # creates every table in Supabase
python create_users.py            # seeds the demo admin/invigilator/control-room logins
python manage.py runserver
```

### 5. Check it worked

- Log in as usual at `http://127.0.0.1:8000/` — if it works, you're already
  reading/writing Supabase.
- In the Supabase dashboard, open **Table Editor** — you should see
  `core_user`, `core_examsession`, `core_hall`, `core_student`,
  `core_alert`, and Django's own `django_migrations` etc. That confirms the
  tables were created there, not in `db.sqlite3`.

You can delete `db.sqlite3` at this point — it's no longer used once
`DATABASE_URL` is set. If you ever remove/comment out `DATABASE_URL` again,
the app falls straight back to SQLite with no other changes.

**One thing to know:** Supabase's free tier pauses a project after about a
week of no activity. The next request just wakes it up (takes a few
seconds) — nothing breaks, just don't be surprised by a slow first login
after a break.

## Going to production

1. Set `DEBUG=False` and a fresh `SECRET_KEY` in `.env`.
2. Set `ALLOWED_HOSTS` (and `CSRF_TRUSTED_ORIGINS` if serving over HTTPS
   behind a custom domain).
3. Point `DATABASE_URL` at Postgres — see **Connecting to Supabase** above.
   SQLite is fine for evaluation, not for concurrent invigilators writing
   at once.
4. `python manage.py collectstatic --noinput`
5. Run with `gunicorn invisense.wsgi` (a `Procfile` is included for
   Heroku-style platforms; `release: python manage.py migrate --noinput`
   runs migrations automatically on deploy).
6. Change the three seeded demo passwords, or delete those accounts and
   create real ones from the **Staff** screen.

## Notes for reviewers / graders

- QR payloads only carry `roll_number`, `subject_code`, `hall_number`,
  `seat` — no personally identifying data beyond what's already in the
  CSV you upload.
- The scanner endpoint (`/api/verify-seat/`) and the status-update endpoint
  (`/api/update-alert/<id>/`) both require an authenticated session; the
  scanner additionally checks that the caller is an invigilator with an
  active hall before it will mark anyone present.
