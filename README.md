# InviSense — Exam Integrity System

A Django app for running paperless exam-hall verification: one permanent
QR per student across a whole exam period, dynamic per-exam section
validation, HOD-controlled shared seating, and a live control-room feed.

## ⚠️ Database changes in this update — read this first

This update makes **halls/sections global** instead of belonging to one
exam period — that's the only way MCA and IMCA can share a physical room
while staying administratively separate. That's a real schema change, not
a column addition, so **the database needs resetting again**.

- **SQLite (local dev):** delete `db.sqlite3`. It rebuilds on `migrate`.
- **Supabase (or any shared Postgres):** in the SQL editor:
  ```sql
  DROP SCHEMA public CASCADE;
  CREATE SCHEMA public;
  ```
  This deletes everything — expected, since the old tables don't map to
  the new ones.

After either reset:
```bash
python manage.py migrate
python create_users.py
```

## What changed in this pass — production hardening

**Sections are global, MCA/IMCA stay separate.** A `Hall` ("CLC 306") no
longer belongs to one exam period. MCA and IMCA each get their own
`ExamPeriod` — separate roster, separate timetable, separate exam
sessions — but both can reserve seats in the same physical room. What
makes this safe: `ExamHall` carries a `capacity_allocated` — how many of
that room's seats *this* exam gets — and every time you reserve seats in
a room, the system sums up every other reservation for that room at an
**overlapping time** (across every exam period, not just the one you have
open) and refuses if the total would exceed the room's real capacity.
Section names display exactly as typed — never auto-prefixed with "Hall".

**Expired timetable rows are rejected, not silently dropped.** Uploading
a timetable checks every row's date/time against the clock (in the app's
configured timezone, not the browser's). A row whose exam has already
ended is rejected with a reason; you get a row-by-row report of what was
created and what wasn't, so nothing vanishes without explanation.

**Global conflict checks, not just within the open period.** Two things
are checked everywhere, across every exam period:
- **The same invigilator** can't be assigned to two sections with
  overlapping exam times.
- **The same student** (by roll number) can't end up seated in two
  overlapping exams. Auto-assign skips a conflicted student and reports
  them by name rather than seating them somewhere wrong.

**Concurrency-safe capacity.** If two admins try to reserve seats in the
same room at the same moment, the database row is locked
(`select_for_update`) for the duration of the check-and-write — the
second write always sees the first one's committed total, so a room can
never end up over capacity no matter how the requests interleave.

**Hall ticket readiness is real, not cosmetic.** A student's one hall
ticket only becomes downloadable once *every* exam session in their
period (excluding cancelled/stopped ones) has a confirmed seat for them.
`Download Hall Tickets` only ever includes students who are actually
ready — nobody gets a ticket with a blank row on it.

**Nothing with history gets hard-deleted.** Exam periods, exam sessions,
sections, and students all get a **Stop / Deactivate** action instead of
a delete once they have real exam activity attached (seating, attendance,
alerts). Delete is still available, but it's blocked with a clear message
when there's history to protect — you're pointed at Stop/Deactivate
instead. A lightweight `AuditLog` records who stopped/deleted/confirmed
what, and when.

**3-hour scanning window.** An invigilator's scanner turns on
automatically 3 hours before their assigned exam's start time and closes
at the exam's end time — no manual toggle, calculated fresh from the
clock on every request.

**Exam session lifecycle.** Each session moves through
`Draft → Scheduled → Ready → (Stopped / Archived)`. "Ready" only happens
when an admin explicitly confirms a complete allocation (blocked if
anyone on the roster is still unseated). A read-only "Completed" label
appears automatically once an exam's end time has passed — no background
job needed for that, it's computed at render time.

## Project structure

```
invisense/            project settings, root urls
core/                 the app: models, views, urls, admin
core/validators.py    capacity/conflict/expired-date checks, concurrency-safe
core/allocation.py    per-exam auto-assignment against each section's quota
core/hall_tickets.py  PDF generator — one ticket per ready student
templates/            all HTML, organised by role
static/css/           styles.css — the whole design system, one file
create_users.py       seeds demo accounts for all three roles
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

## Everyday workflow

1. **Admin** creates two exam periods — e.g. *"First Internal Exam -
   MCA"* and *"First Internal Exam - IMCA"* — each with its own roster and
   timetable.
2. **Admin** uploads each period's roster (`roll_number, name, course`) —
   issues each student's one permanent hall-ticket QR.
3. **Admin** uploads each period's timetable (`subject, exam_date,
   start_time, end_time`). Any row whose date has already passed is
   rejected and reported, never silently created.
4. **Admin** sets up **Sections** once, globally (top nav → Sections) —
   e.g. "CLC 306", capacity 13. These are shared by both periods.
5. **Admin opens an exam session** and reserves seats in a section for
   it — e.g. 10 seats in CLC 306 for MCA's DBMS exam. The system checks
   that total against everything else already reserved in that room at
   an overlapping time (including IMCA's own exams) before allowing it —
   so IMCA can separately reserve the remaining 3 seats in the same room
   at the same time, and the system will refuse a 4th reservation that
   would push the room over capacity.
6. **Admin assigns an invigilator** per section per exam (conflict-checked
   globally) and clicks **Auto-assign students** — fills each section to
   its reserved quota in roll-number order, skipping and reporting any
   student who'd conflict with another exam.
7. **Admin confirms** the allocation once every roster student has a seat
   — this is what unlocks that exam session's row on every affected
   student's hall ticket.
8. Once **every** exam session in a period is confirmed for a student,
   **Admin downloads Hall Tickets (PDF)** for that period — one ticket per
   ready student, their one QR, and their full confirmed schedule.
9. **Invigilator** opens `Scan & Verify` — the scanner turns on
   automatically 3 hours before their assigned exam and shows a live
   roster of who's checked in. A flag can be raised from a scan result or
   from a dropdown of anyone already checked in.
10. **Control room** watches `Live Feed` and `Reports` as before.

## Connecting to Supabase

The project ships pointed at local SQLite so it runs with zero setup, but
it's built to switch to a real Postgres database — like Supabase — by
changing one line in `.env`. No code changes needed.

### 1. Create the Supabase project
Go to [supabase.com](https://supabase.com) → **New Project** → name it,
set a database password (save it), pick a region, create, wait ~1 minute.

### 2. Get the connection string
**Connect** (top bar) → **Session pooler** tab (not "Transaction pooler")
→ copy the URI → replace `[YOUR-PASSWORD]` with your real password.

### 3. Point the project at it
In `.env`:
```
DATABASE_URL=postgresql://postgres.xxxxxxxxxxxx:your-real-password@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```
`settings.py` detects Postgres automatically and enables SSL + connection
reuse — nothing else to change.

### 4. Reset (if this project ran an older InviSense version) and build
See **"Database changes in this update"** above, then:
```bash
pip install -r requirements.txt
python manage.py migrate
python create_users.py
python manage.py runserver
```

### 5. Check it worked
Log in normally, then check Supabase's **Table Editor** for
`core_examperiod`, `core_hall`, `core_examsession`, `core_examhall`,
`core_examstudentassignment`, `core_attendance`, `core_auditlog`, etc.

## Going to production

1. `DEBUG=False` and a fresh `SECRET_KEY` in `.env`.
2. Set `ALLOWED_HOSTS` (and `CSRF_TRUSTED_ORIGINS` for HTTPS).
3. Point `DATABASE_URL` at Postgres (see Supabase section above) — SQLite
   can't safely handle concurrent writers.
4. `python manage.py collectstatic --noinput`
5. `gunicorn invisense.wsgi` (a `Procfile` is included; its `release`
   step runs migrations automatically on deploy).
6. Change the three seeded demo passwords, or replace them from **Staff**.

## Mapping to the spec's test scenarios

- **Section 46 (expired-date tests):** covered by `check_not_expired` in
  `core/validators.py`, run per-row on timetable upload and again on any
  edit to an exam session's date/time.
- **Section 47 (mixed-seating tests, capacity=13):** covered by
  `check_hall_capacity` — sums every overlapping `ExamHall.capacity_allocated`
  for the room and rejects anything that would exceed `Hall.capacity`.
- **Section 48 (hall ticket gating):** covered by
  `Student.is_hall_ticket_ready` and enforced in `download_hall_tickets`.
- **Section 42 (concurrent admins):** covered by `select_for_update()` on
  the `Hall` row inside `check_hall_capacity`, called inside
  `transaction.atomic()` around every seat-reservation write.

## Notes for reviewers / graders

- The QR itself carries only an opaque random token — never a subject,
  date, section, or seat. Everything else is resolved server-side at scan
  time from the invigilator's current context (found from the clock) and
  the database.
- Duplicate attendance is prevented at the database level
  (`unique_together` on `Attendance`), not just in view logic.
- `AuditLog` is intentionally lightweight (who/what/when, not a full
  field-level diff) — enough to answer "who stopped this and when"
  without building a full versioning system.
