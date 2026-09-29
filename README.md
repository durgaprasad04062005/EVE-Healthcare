# EVE Healthcare — Diagnostic Booking API

A backend service for booking diagnostic tests and processing simulated payments.

Built for the **EVE Healthcare SDE Intern Backend Engineering Assignment**.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Technology Stack](#technology-stack)
4. [Project Structure](#project-structure)
5. [Database Schema Design](#database-schema-design)
6. [Authentication Flow](#authentication-flow)
7. [Booking Flow](#booking-flow)
8. [Payment Flow](#payment-flow)
9. [Webhook Idempotency Strategy](#webhook-idempotency-strategy)
10. [API Endpoints](#api-endpoints)
11. [Example Requests](#example-requests)
12. [Environment Variables](#environment-variables)
13. [Local Setup (without Docker)](#local-setup-without-docker)
14. [Docker Setup](#docker-setup)
15. [Running Tests](#running-tests)
16. [Important Assumptions](#important-assumptions)
17. [Known Limitations](#known-limitations)
18. [What I Would Improve With More Time](#what-i-would-improve-with-more-time)

---

## Project Overview

This service provides:

- **User authentication** — signup, login, JWT-based access tokens
- **Diagnostic centre catalogue** — manage centres and the tests they offer
- **Booking system** — authenticated users book tests at specific centres
- **Simulated payment processing** — mock payment endpoint (no real gateway)
- **Payment webhook** — idempotent endpoint that processes payment-status updates

---

## Architecture

The application follows a clean layered architecture:

```
HTTP Request
    │
    ▼
API Layer (app/api/)          ← validates input, calls service, returns HTTP response
    │
    ▼
Service Layer (app/services/) ← business logic, state machine, transactions
    │
    ▼
ORM Models (app/models/)      ← SQLAlchemy mapped classes, relationships
    │
    ▼
PostgreSQL Database
```

**Key principles:**
- Routes are thin — no business logic in routers
- Services own domain logic and are independently testable
- Pydantic schemas are strictly separate from ORM models (no field leakage)
- State machine rules live in one place (`models/booking.py`)

---

## Technology Stack

| Component | Technology |
|---|---|
| Framework | FastAPI |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| Auth | JWT via python-jose, bcrypt for hashing |
| Validation | Pydantic v2 |
| Testing | pytest + pytest-asyncio + httpx |
| Containerisation | Docker + docker-compose |

---

## Project Structure

```
eve_healthcare/
├── app/
│   ├── main.py                  # FastAPI app, router registration
│   ├── core/
│   │   ├── config.py            # Settings (reads from env vars)
│   │   ├── security.py          # Password hashing, JWT creation/validation
│   │   └── logging.py           # Logging configuration
│   ├── db/
│   │   └── database.py          # Async engine, session factory, Base, get_db
│   ├── models/
│   │   ├── user.py
│   │   ├── centre.py
│   │   ├── test.py
│   │   ├── centre_test.py       # M2M association with price
│   │   ├── booking.py           # Includes state machine logic
│   │   ├── payment.py
│   │   └── webhook_event.py     # Idempotency store
│   ├── schemas/                 # Pydantic request/response models
│   ├── services/                # Business logic
│   │   ├── auth_service.py
│   │   ├── catalogue_service.py
│   │   ├── booking_service.py
│   │   └── payment_service.py
│   └── api/                     # FastAPI routers
│       ├── auth.py
│       ├── centres.py
│       ├── tests.py
│       ├── bookings.py
│       ├── payments.py
│       └── deps.py              # Shared dependencies (get_current_user)
├── alembic/                     # Database migration scripts
├── tests/
│   ├── conftest.py              # pytest fixtures, test DB setup
│   ├── test_auth.py
│   ├── test_catalogue.py
│   ├── test_bookings.py
│   ├── test_payments.py
│   └── test_state_machine.py   # Pure unit tests for state machine + security
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
├── pytest.ini
├── .env.example
└── .gitignore
```

---

## Database Schema Design

### Tables

```
users
  id (PK, UUID)
  email (UNIQUE, indexed)
  hashed_password
  full_name
  is_active

diagnostic_centres
  id (PK, UUID)
  name
  location
  description

diagnostic_tests
  id (PK, UUID)
  name (UNIQUE)
  description

centre_tests                          ← M2M with price
  id (PK, UUID)
  centre_id (FK → diagnostic_centres)
  test_id   (FK → diagnostic_tests)
  price     (NUMERIC 10,2)
  UNIQUE(centre_id, test_id)
  CHECK(price > 0)

bookings
  id (PK, UUID)
  user_id   (FK → users)
  test_id   (FK → diagnostic_tests)
  centre_id (FK → diagnostic_centres)
  appointment_datetime
  amount    (NUMERIC 10,2) ← locked from CentreTest.price at booking time
  status    (ENUM: PENDING, CONFIRMED, FAILED, CANCELLED)

payments
  id (PK, UUID)
  booking_id (FK → bookings, UNIQUE) ← one payment per booking
  payment_reference (UNIQUE)
  amount
  status (ENUM: PENDING, SUCCESS, FAILED)
  provider_event_id

payment_webhook_events               ← idempotency store
  id (PK, UUID)
  event_id (UNIQUE)                  ← the idempotency key
  booking_id
  payload (TEXT)
  status (ENUM: RECEIVED, DUPLICATE, FAILED)
```

### Key Design Decision: Price on CentreTest, not DiagnosticTest

The same test (e.g. "Full Blood Count") can cost R150 at a government clinic and R400 at a private lab. Price is a property of the *relationship* between a centre and a test — not the test itself. Storing it on `centre_tests` is the correct normalised design.

### Booking Amount is Locked at Creation Time

When a booking is created, the server copies `CentreTest.price` into `Booking.amount`. This means if the price changes later, historical bookings still show what was charged at the time — correct accounting behaviour.

---

## Authentication Flow

```
1. POST /auth/signup  { email, password, full_name }
   → server hashes password with bcrypt
   → creates User row
   → returns JWT access token

2. POST /auth/login   { email, password }
   → server looks up user by email
   → verifies bcrypt hash
   → returns JWT access token (same message for bad email or bad password)

3. Protected endpoints: include header
   Authorization: Bearer <token>
   → server validates JWT signature + expiry
   → loads user from DB
   → proceeds or returns 401
```

**JWT payload:** `{ "sub": "<user_uuid>", "exp": <unix_timestamp> }`

---

## Booking Flow

```
1. Browse centres:  GET /centres/
2. See tests at centre: GET /centres/{id}/tests
3. Create booking:  POST /bookings/
   { test_id, centre_id, appointment_datetime }
   → server validates test is offered at centre
   → server fetches price from CentreTest (client cannot supply amount)
   → booking created with status PENDING
4. Pay:  POST /payments/  { booking_id }
   → PENDING → CONFIRMED (if payment succeeds)
   → PENDING → FAILED (if payment fails)
5. Cancel:  POST /bookings/{id}/cancel
   → only PENDING bookings can be cancelled
```

---

## Payment Flow

```
POST /payments/  { booking_id }
│
├── Validate: booking exists + belongs to caller + is PENDING
├── Validate: no existing payment for this booking
├── Generate payment_reference (PAY-XXXXXXXXXXXX)
├── Generate provider_event_id (EVT-XXXXXXXXXXXXXXXX)
├── Simulate outcome: 80% SUCCESS, 20% FAILED
├── Create Payment row
├── Update Booking status (CONFIRMED or FAILED)
└── Return payment details
```

**This is a simulated payment — no real gateway is used.**

In production, this endpoint would redirect to a payment provider (Stripe, PayFast, etc.) and the result would arrive asynchronously via the webhook.

---

## Webhook Idempotency Strategy

The webhook endpoint (`POST /payments/webhook/`) must handle duplicate events safely. The same event can arrive multiple times due to network retries, provider bugs, or replay attacks.

### How it works

1. Every webhook event has a unique `event_id` provided by the caller.
2. When a webhook arrives, we **attempt to INSERT** a row into `payment_webhook_events` with that `event_id`.
3. The `event_id` column has a **`UNIQUE` constraint at the database level**.
4. If the INSERT succeeds → new event → process it (update payment + booking).
5. If the INSERT raises `IntegrityError` (UNIQUE violation) → **duplicate** → return 200 OK immediately **without reprocessing**.

### Why database-level, not in-memory?

| Approach | Problem |
|---|---|
| Python `set()` in memory | Lost on restart, not shared across multiple server instances |
| DB check then insert | Race condition: two concurrent requests both pass the check, both insert |
| **DB UNIQUE constraint + IntegrityError** | **Atomic at the database level — only one INSERT ever succeeds** |

### Transaction safety

The entire webhook processing runs inside a single transaction:
```
BEGIN
  INSERT payment_webhook_events (event_id=X)  ← atomic gate
  UPDATE payments SET status = SUCCESS
  UPDATE bookings SET status = CONFIRMED
COMMIT
```

If the booking update fails, the event INSERT also rolls back — so the event can be retried safely.

---

## API Endpoints

### Auth
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/signup` | No | Register a new user |
| POST | `/auth/login` | No | Login, receive JWT |
| GET | `/auth/me` | Yes | Get current user profile |

### Centres
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/centres/` | No | List all centres |
| POST | `/centres/` | Yes | Create a centre |
| GET | `/centres/{id}` | No | Get a centre |
| PATCH | `/centres/{id}` | Yes | Update a centre |
| GET | `/centres/{id}/tests` | No | List tests at centre (with prices) |
| POST | `/centres/{id}/tests/{test_id}` | Yes | Add test to centre |
| PUT | `/centres/{id}/tests/{test_id}` | Yes | Update price at centre |
| DELETE | `/centres/{id}/tests/{test_id}` | Yes | Remove test from centre |

### Tests
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/tests/` | No | List all tests |
| POST | `/tests/` | Yes | Create a test |
| GET | `/tests/{id}` | No | Get a test |
| PATCH | `/tests/{id}` | Yes | Update a test |

### Bookings
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/bookings/` | Yes | Create a booking |
| GET | `/bookings/` | Yes | List own bookings |
| GET | `/bookings/{id}` | Yes | Get a booking |
| POST | `/bookings/{id}/cancel` | Yes | Cancel a booking |

### Payments
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/payments/` | Yes | Initiate payment for a booking |
| POST | `/payments/webhook/` | No | Receive payment status update |

### Other
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | No | Health check |
| GET | `/docs` | No | Swagger UI |
| GET | `/redoc` | No | ReDoc documentation |

---

## Example Requests

### Signup
```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "patient@example.com", "password": "securepassword1", "full_name": "John Patient"}'

# Response: {"access_token": "eyJ...", "token_type": "bearer"}
```

### Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "patient@example.com", "password": "securepassword1"}'
```

### Create a Diagnostic Centre
```bash
curl -X POST http://localhost:8000/centres/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "City Health Lab", "location": "45 Main Street, Cape Town"}'
```

### Create a Diagnostic Test
```bash
curl -X POST http://localhost:8000/tests/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Full Blood Count", "description": "Measures red/white blood cells"}'
```

### Add Test to Centre (with price)
```bash
curl -X POST http://localhost:8000/centres/<centre_id>/tests/<test_id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"price": "350.00"}'
```

### Create a Booking
```bash
curl -X POST http://localhost:8000/bookings/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "test_id": "<test_id>",
    "centre_id": "<centre_id>",
    "appointment_datetime": "2027-01-15T09:00:00Z"
  }'

# Response includes status: "PENDING" and server-determined amount
```

### Initiate Payment
```bash
curl -X POST http://localhost:8000/payments/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"booking_id": "<booking_id>"}'

# Response includes status: "SUCCESS" or "FAILED"
# Booking status updates accordingly
```

### Send Webhook Event
```bash
curl -X POST http://localhost:8000/payments/webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "EVT-UNIQUE-12345",
    "booking_id": "<booking_id>",
    "status": "SUCCESS"
  }'

# Sending same event_id again: received=false (idempotent, no duplicate processing)
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | PostgreSQL async URL (`postgresql+asyncpg://...`) |
| `JWT_SECRET_KEY` | Yes | — | JWT signing secret (min 32 chars recommended) |
| `JWT_ALGORITHM` | No | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | Token lifetime in minutes |
| `APP_ENV` | No | `development` | `development` or `production` |
| `POSTGRES_USER` | Docker only | `eve` | PostgreSQL username |
| `POSTGRES_PASSWORD` | Docker only | — | PostgreSQL password |
| `POSTGRES_DB` | Docker only | `eve_healthcare` | PostgreSQL database name |

---

## Local Setup (without Docker)

**Prerequisites:** Python 3.12+, PostgreSQL running locally

```bash
# 1. Clone the repository
git clone <repo-url>
cd eve_healthcare

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env: set DATABASE_URL to point to your local PostgreSQL
# Edit .env: set JWT_SECRET_KEY to a strong random value

# 5. Create the PostgreSQL database
psql -U postgres -c "CREATE DATABASE eve_healthcare;"

# 6. Run database migrations
python -m alembic upgrade head

# 7. Start the API server
uvicorn app.main:app --reload --port 8000

# API is now available at:
#   http://localhost:8000
#   http://localhost:8000/docs  (Swagger UI)
```

---

## Docker Setup

**Prerequisites:** Docker and Docker Compose installed

```bash
# 1. Clone the repository
git clone <repo-url>
cd eve_healthcare

# 2. Create your environment file
cp .env.example .env
# Edit .env: set JWT_SECRET_KEY and POSTGRES_PASSWORD to real values

# 3. Build and start all services
docker-compose up --build

# The API will be available at http://localhost:8000
# PostgreSQL will be available at localhost:5432

# Run in the background
docker-compose up -d --build

# View logs
docker-compose logs -f api

# Stop everything
docker-compose down

# Stop and remove database data (full reset)
docker-compose down -v
```

Migrations run automatically when the API container starts (see `docker-compose.yml` command).

---

## Running Tests

Tests use an in-memory SQLite database — **no PostgreSQL required**.

```bash
# Run all tests
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_auth.py -v

# Run a specific test
python -m pytest tests/test_payments.py::test_webhook_duplicate_event -v

# Run with environment variables (required even for tests)
DATABASE_URL=sqlite+aiosqlite:///:memory: \
JWT_SECRET_KEY=testsecret \
python -m pytest tests/ -v
```

You can also set variables in a `.env` file and pytest will pick them up via `pydantic-settings`.

**Test count: 70 tests across 5 test files.**

---

## Important Assumptions

1. **Price is per centre-test, not global.** The same test can cost different amounts at different centres. Price is stored on the `centre_tests` association table.

2. **Booking amount is server-determined.** The client cannot supply an amount. The server reads `CentreTest.price` at booking time. This prevents price manipulation.

3. **Write endpoints require any valid JWT.** In production, creating centres and tests would be restricted to admin users. Since the assignment doesn't define an admin role, any authenticated user can create/update catalogue entries. This assumption is documented here.

4. **One payment per booking.** If a payment fails, the booking is `FAILED` and cannot be retried. A new booking must be created. This keeps the data model simple and auditable.

5. **Webhook signature not verified.** In production, the webhook endpoint would verify a HMAC signature from the payment provider to prevent spoofing. This is not implemented since there is no real provider.

6. **Simulated payment is synchronous.** In production, `POST /payments/` would redirect to the payment gateway and the result would arrive later via webhook. Here, the outcome is immediate and random (80% success rate).

7. **Tests use SQLite instead of PostgreSQL.** SQLite doesn't support all PostgreSQL features (e.g. some CHECK constraint types). In production, tests would run against a real PostgreSQL instance.

---

## Known Limitations

- No admin/role-based access control
- No pagination cursor (uses offset/limit — not ideal for large datasets)
- No webhook signature verification
- No email notifications
- SQLite used for tests (not identical to production PostgreSQL)
- Single-server deployment (no horizontal scaling considerations)

---

## What I Would Improve With More Time

1. **Admin roles** — restrict centre/test creation to admin users using a role field and a separate `Depends(require_admin)` dependency.

2. **Real PostgreSQL for tests** — use `pytest-postgresql` or a Docker-based test database for full parity with production.

3. **Webhook signature verification** — validate HMAC-SHA256 signatures on the webhook endpoint to prevent spoofing.

4. **Retry queue** — use Celery + Redis to retry failed webhook processing, with exponential backoff.

5. **Cursor-based pagination** — more efficient than offset/limit for large result sets.

6. **Rate limiting** — add per-IP rate limiting to auth endpoints to prevent brute force attacks.

7. **Structured JSON logging** — use `structlog` for proper JSON log output compatible with log aggregation systems (Datadog, CloudWatch, etc.).

8. **OpenAPI response examples** — add `openapi_examples` to all schemas for a richer Swagger UI.

9. **Integration tests against PostgreSQL** — SQLite doesn't test all constraint behaviour (e.g. ENUM types, CHECK constraints).

10. **CI/CD pipeline** — GitHub Actions workflow to run tests and build the Docker image on every push.
