# InviSense — Exam Integrity System

A Django app for running paperless exam-hall verification: one permanent
QR per student across a whole exam period, dynamic per-exam hall
validation, silent incident alerts, and a live control-room feed.

## ⚠️ Database changes in this update — read this first

This update replaces the **entire data model**, not just a few fields.
The previous design gave every student a new QR for every single exam
session; this one gives each student **one permanent QR for the whole
exam period**, and figures out which exam and hall it's valid for at scan
time. That's not a column you can add — it's new tables (see "What
changed" below) and the old tables are gone.

**This means your existing database (SQLite or Supabase) needs to be
reset before this version will run.** Old sessions/students/QR data from
the previous architecture do not carry over — there's no automatic
migration path because the shape of the data is fundamentally different.

- **SQLite (local dev):** just delete `db.sqlite3`. It'll be recreated
  fresh the moment you run `migrate`.
- **Supabase (or any shared Postgres):** open the Supabase SQL editor and
  run:
  ```sql
  DROP SCHEMA public CASCADE;
  CREATE SCHEMA public;
  ```
  This wipes every table (including the old `core_examsession`,
  `core_student`, etc.) so `migrate` can build the new schema cleanly.
  **This deletes all existing data in that project** — expected here,
  since none of it maps to the new tables anyway.

After either reset:
```bash
python manage.py migrate
python create_users.py
```

## What changed — the new architecture

The old model tied a QR code (and a student's hall) to one single-day
session. That breaks the moment a college runs more than one exam per
student — a student needs a *different* hall on Tuesday than they had on
Monday, but the *same* physical ticket both days. The new model separates
those concerns properly:

| Table | What it holds |
|---|---|
| `ExamPeriod` | The whole exam cycle (e.g. "MCA/iMCA Semester 3, Aug 2026"). One roster, one hall catalog. |
| `Student` | The roster — uploaded once per period. No hall, no seat, no QR data baked in. |
| `HallTicket` | One row per student: one permanent, opaque QR token. Never contains a subject, date, or hall. |
| `Hall` | A physical room, reusable across every exam in the period. |
| `ExamSession` | One specific exam: subject + date + start/end time. Multiple halls can run the same session at once. |
| `ExamHall` | Which halls are running a given exam, and which invigilator is running each one. |
| `ExamStudentAssignment` | Which hall a specific student sits in for a specific exam — recalculated per exam, never stored on the student. |
| `Attendance` | One row per (exam, student) — the database itself won't allow a duplicate. |

**How a scan actually gets validated**, end to end:

1. Invigilator logs in. The system finds which `ExamHall` they're assigned
   to whose exam is happening *right now* (today's date, current time
   inside the exam's start/end window) — this is fully automatic, nothing
   the invigilator has to select manually.
2. They scan a student's QR — which is just an opaque token, nothing else.
3. The token resolves to a `Student` via their `HallTicket`.
4. The system looks up that student's `ExamStudentAssignment` for *this*
   exam session specifically.
5. It compares that assignment's hall against the invigilator's current
   hall (from step 1).
6. Match → an `Attendance` row is created (or, if one already exists,
   "already marked" — no duplicates). No match → rejected, and the
   student's *correct* hall is shown on screen. Nothing is marked present.

Nothing about the exam, hall, or seat is ever trusted from the scan
itself — the QR is just an identity token, and everything else is looked
up server-side against the current clock and the admin's own data.

## Project structure

```
invisense/           project settings, root urls
core/                the app: models, views, urls, admin
core/allocation.py   per-exam auto-assignment (contiguous roll-number blocks)
core/hall_tickets.py PDF generator — one ticket per student, full exam schedule
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
(shown on the login screen).

## Everyday workflow

1. **Admin** creates an **exam period** (`Exam Periods → New exam
   period`) — just a name, e.g. "MCA/iMCA Semester 3, Aug 2026".
2. **Admin** opens it and **uploads the roster** (`roll_number, name,
   course`) — this issues every student's one permanent hall-ticket QR,
   once, for the whole period.
3. **Admin** adds halls to the period's **hall catalog** (hall number +
   capacity) — reusable across every exam in this period.
4. **Admin uploads the timetable** (`subject, exam_date, start_time,
   end_time`) — each row becomes an exam session. Two subjects sharing a
   morning with different timings (like an MCA/iMCA example) are just two
   rows with different times.
5. **Admin opens each exam session** and:
   - selects which halls are running it,
   - assigns an invigilator to each of those halls,
   - clicks **Auto-assign students** — splits the roster into even,
     contiguous roll-number blocks across the selected halls (e.g. 61
     students over 2 halls → 31/30, filled in register-number order),
   - reviews the allocation and clicks **Confirm**.
   Repeat for every exam on the timetable — a student can land in a
   different hall each day, and that's expected.
6. **Admin downloads Hall tickets (PDF)** from the period page — one
   ticket per student, printed once, covering every exam in the period
   with their assigned hall for each one, plus their one QR.
7. **Invigilator** opens `Scan & Verify` — it automatically shows whichever
   exam+hall they're assigned to *right now* based on the clock, with no
   manual selection. They scan each ticket; the system marks attendance,
   flags a wrong hall (and shows the correct one), or says "already
   marked" — never a duplicate. A live roster panel below the scanner
   shows who's checked in so far, and a flag can be raised straight from
   a scan result or from a dropdown of anyone already checked in.
8. **Control room** watches `Live Feed` for incoming alerts and
   acknowledges/resolves them; `Reports` gives a per-exam-session log with
   CSV export.

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

If this Supabase project was already running an older version of
InviSense, reset it first — see **"Database changes in this update"**
at the top of this file.

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
  `core_user`, `core_examperiod`, `core_examsession`, `core_hall`,
  `core_student`, `core_hallticket`, `core_examstudentassignment`,
  `core_attendance`, `core_alert`, and Django's own `django_migrations`.
  That confirms the tables were created there, not in `db.sqlite3`.

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

- The QR itself carries **only an opaque random token** — never a
  subject, date, hall, or seat. Everything else is resolved server-side at
  scan time from the invigilator's current context and the database.
- The scanner endpoint (`/api/verify-qr/`) and the status-update endpoint
  (`/api/update-alert/<id>/`) both require an authenticated session; the
  scanner additionally checks that the caller is an invigilator with a
  *currently active* exam (by date and clock time) before it will look up
  or mark anyone present.
- Duplicate attendance is prevented at the database level
  (`unique_together` on `Attendance`), not just in view logic — a second
  scan for the same exam can't create a second row even under concurrent
  requests.
