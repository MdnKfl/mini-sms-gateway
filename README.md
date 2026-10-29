# Mini SMS Gateway

A small REST API that accepts SMS send requests, charges credits, sends through fake providers with failover, and refunds when all providers fail.

Built while learning FastAPI + SQLAlchemy. The main goal was getting the **atomic credit handling** right.

---

## Setup

```bash
pip install -r requirements.txt
fastapi dev app/main.py
```

Open **http://127.0.0.1:8000/docs** to try the endpoints.

The `sms.db` file is created automatically on first run at the project root. Two routes (`ROUTE_A`, `ROUTE_B`) are added with some default failure rates.

**Note:** run from inside `app/` because imports are local.

---

## Endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/register` | Create user with 100 credits |
| POST | `/login` | Form-data (`username`=email, `password`) → returns JWT |
| GET | `/me` | User info + balance |
| POST | `/sms/send` | Send an SMS |
| GET | `/sms/logs` | Paginated history, filterable by status/number/date |
| GET | `/routes/health` | Balance + success rate + health % per route |
| POST | `/demo/set-failure-rate` | Change a route's failure rate (for demo) |

### Example send

```json
POST /sms/send
{
  "to": ["9841234567", "+9779801122334"],
  "message": "hello"
}
```

Returns parts, cost, new balance, and per-recipient status.

---

## How the send works

```
1. Check JWT → find user
2. Clean up phone numbers (reject invalid)
3. Count SMS parts × number of recipients = cost
4. Deduct credits (atomic, all-or-nothing)
5. Create a message row per recipient, status = pending
6. Try each route by priority. If a route succeeds, break. If all fail, mark failed.
7. Refund if failed (atomic, won't double-refund)
```

---

## SMS counting rules

| Type | 1 part | Multi-part |
|---|---|---|
| GSM-7 (ASCII) | 160 chars | 153 chars each |
| Unicode (Nepali/emoji) | 70 chars | 67 chars each |

- Any non-ASCII character makes the whole message Unicode.
- One SMS part = 1 credit.

Example: 200 English chars = `ceil(200/153)` = 2 parts = 2 credits.

---

## The two things that make this safe

This is the part I spent the most time on. Two SQL statements do all the real work.

### 1. Atomic debit

```sql
UPDATE users
SET balance = balance - cost
WHERE id = ? AND balance >= cost
```

The check `balance >= cost` and the subtraction happen in **one SQL statement**. If two requests hit at the same moment, the database runs them one after another. The second sees the reduced balance, the `WHERE` fails, 0 rows change, so we return `402 Insufficient credits`.

If I had done it the "normal" way:

```python
user = get_user()
if user.balance >= cost:
    user.balance -= cost
    save()
```

…then two parallel requests could both read the old balance, both think there's enough, and both subtract. The wallet could go negative. The single UPDATE prevents that.

### 2. Atomic refund

```sql
UPDATE sms_messages
SET status = 'refunded'
WHERE id = ? AND status = 'failed'
```

Then only if that matched:

```sql
UPDATE users
SET balance = balance + cost
WHERE id = ?
```

If the refund somehow runs twice, the second time `WHERE status = 'failed'` finds nothing (already refunded) → 0 rows → the credit add is skipped. So a message can only be refunded once.

---

## Failover

Routes are sorted by priority. For each message:

- If the route's balance is too low, skip it
- Roll `random.random()` against its failure rate
- Success → mark sent, stop
- Failure → try the next route
- All fail → mark failed → refund

**Failover doesn't cost extra.** The message is charged once before routes are tried. Trying more routes doesn't add charges.

---

## Health formula

```
health = 0.7 × success_rate_24h + 0.3 × (balance / 1000)
```

- 70% weight on how often the route succeeded in the last 24 hours
- 30% weight on how much balance it has left (capped at 1.0)
- If a route had no attempts in 24h, success rate is treated as 1.0 (no evidence of failure)

The idea: a route with lots of recent failures is unhealthy even if it has plenty of balance, and vice versa.

---

## Tests

Both tests need the server running in another terminal.

```bash
# Terminal 1
cd app && fastapi dev main.py

# Terminal 2 (from project root)
python test_currency.py
python test_failover.py
```

### `test_currency.py`

Fires 20 parallel requests from 20 threads against a wallet with exactly 10 credits. Route failures are turned off first so the result is clean.

Expected output:

```
Set race@test.com balance = 10, routes = 0% failure
Success (201):       10
Insufficient (402):  10
Final balance:       0
PASSED: no overspend.
```

This is the main proof that the atomic debit works.

### `test_failover.py`

Three scenarios:

1. Normal send → sent via ROUTE_A
2. ROUTE_A forced to fail → sent via ROUTE_B
3. Both routes forced to fail → message refunded, balance unchanged

---

## Project layout

```
mini-sms-gateway/
├── app/
│   ├── database.py        # DB engine + session
│   ├── models.py          # User, Route, SmsMessage, RouteAttempt
│   ├── utils.py           # phone cleaning + SMS part counting
│   ├── security.py        # password hash, JWT create/verify, auth dependency
│   ├── main.py            # app entry + route seeding
│   └── routers/
│       ├── auth.py        # /register /login /me
│       ├── sms.py         # /sms/send /sms/logs  +  refund_message
│       └── routes.py      # /routes/health /demo/set-failure-rate
├── test_currency.py
├── test_failover.py
├── requirements.txt
├── .gitignore
└── README.md
```

---

## What I would improve

Things I didn't have time to add:

- **Crash recovery:** if the server crashes between the debit and the send loop, messages stay `pending` and credits stay debited. Fix: on startup, look for old `pending` messages and refund them. I didn't implement this.
- **PostgreSQL instead of SQLite:** SQLite locks the whole file for writes. Postgres would handle parallel writes to different rows. Fine for this scale, but not for production.
- **Credit ledger:** right now I update balance in place. A separate ledger table (one row per debit/refund) would make auditing and reconciliation easier.
- **Background queue:** `/sms/send` blocks until routes are tried. A queue (Redis + worker) would return immediately and process sends in the background.
- **Rate limiting per user:** none right now.
- **Absolute imports:** the app runs from `app/` because imports are local. I'd change to `from app.database import ...` so it can run from the project root.
- **Migrations:** using `Base.metadata.create_all()` instead of Alembic. Fine for a demo, not for schema changes.

---

## What I learned

- Writing the check **inside** the UPDATE statement is what makes the debit safe. Moving the check outside (into Python) reopens the race.
- `yield` dependencies in FastAPI are nice for cleanup — `get_db` opens a session and closes it after the request, automatically.
- The idempotent refund pattern (flip status → add credits, in that order) is the same shape as the debit but for a different reason: it guards against double-execution, not against overspend.
- SQLite is fine for learning but has real limitations on concurrent writes. `timeout=30` and `check_same_thread=False` were needed because of how FastAPI threads work.