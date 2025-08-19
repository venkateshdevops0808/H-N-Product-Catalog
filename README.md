# H&N FitApp — Application (FastAPI + SQLModel)

Application for the H&N / FitApp product catalog: a compact FastAPI service with a static Tailwind UI to create, list, search, recommend, and manage health skills (e.g., breathing exercises, medication reminders). Runs locally with SQLite or in the cloud with PostgreSQL. Container-ready and CI-friendly.
---

## Contents
- **Project Description**
- **Product Catalog & Features**
- **How the Application Works**
- **Tech Stack**
- **API Design & Best Practices**
- **API Endpoints**
- **Docker Image (high-level)**
- **GitHub Actions (high-level)**
- **Run Locally (Python)**
- **Build & Run with Docker**
- **Run via GitHub Actions**
- **Branching Strategy**
- **Future Improvements**
- **Quick Reference**

---

## Project Description
- A small, opinionated REST API plus a static admin UI that manages a catalog of “skills” the assistant can suggest. Focus areas:
- Clarity (consistent JSON, explicit errors)
- Safety (typed validation)
- Extensibility (versioned routes, filters, pagination)
- Ops-ready (health, docs, containerization, CI/CD)

## Product Catalog & Features

Each catalog item includes:

name (title), category (sleep|stress|mobility|meds|safety|nutrition)

description (optional), device (watch|phone|any)

price (admin-only metadata), reward (optional incentive)

voice_prompt (what the assistant will say)

## Included features:

CRUD: create, list, get, delete

Search & filters: q (ILIKE name), category, device

Pagination: page, page_size

Simple recommendations by goal + optional device

Admin-lite UI (Tailwind, no framework build step)

Demo seed endpoint (7–8 items)

Health check (/health), DB info (/__dbinfo), and OpenAPI docs (/docs)

Backward-compat mode (Postel’s Law / robustness principle):
Create accepts reward (preferred) or legacy prize; server normalizes to reward.

## How the Application Works

UI/clients call FastAPI routes.

Validation via SQLModel/Pydantic.

Persistence via SQLAlchemy engine:

Local: SQLite (DB_URL=sqlite:///./app.db)

Cloud: PostgreSQL (postgresql+psycopg://...&sslmode=require)

Responses: clean JSON with predictable ordering, filters, and pagination.

Static UI served at / to browse, add, delete, and seed items.

## Tech Stack

Python 3.12, FastAPI, SQLModel (Pydantic + SQLAlchemy)

Uvicorn ASGI server

SQLite (local) / PostgreSQL with psycopg (cloud)

Tailwind CSS static UI (no JS framework)

Docker for builds/run

GitHub Actions for CI/CD

## API Design & Best Practices

Versioned routes: /api/v1/...

Pagination: page (≥1), page_size (1..50); stable ordering by id desc

Filtering: q (ILIKE on name), category, device

Input validation: types and bounds (e.g., price ≥ 0)

HTTP semantics: 201 on create, 204 on delete, 404 on missing, 422 on bad input

CORS: permissive for demo; restrict in production

Observability: /health, /__dbinfo, /docs

Robustness: accept reward or legacy prize (Postel’s Law)

Rate limiting (recommended): add starlette-limiter + Redis, or enforce at gateway (API Management/Front Door)

Cache/ETag (optional): add Cache-Control/ETag for reads if needed

## API Endpoints

GET / — serve the static admin UI

GET /health — liveness probe ({"status":"ok"})

GET /__dbinfo — redacted DB details, server version (best effort), items count

GET /docs / GET /redoc — OpenAPI docs (Swagger / ReDoc)

Catalog

POST /api/v1/items — create item; accepts reward or legacy prize

GET /api/v1/items — list items (q, category, device, page, page_size)

GET /api/v1/items/{id} — fetch one

DELETE /api/v1/items/{id} — delete (idempotent, returns 204)

POST /api/v1/items/seed_demo — seed 7–8 demo items (no-op if not empty)

Recommendations

GET /api/v1/recommend?goal=<category>&device=<watch|phone|any> — simple recs

## Docker Image (high-level)

Multi-stage build → small runtime image

Installs requirements.txt, copies app, sets non-root user

Entrypoint runs Uvicorn (app.main:api) and respects PORT (default 8030)

Reads DB_URL from environment

/health is safe for container probes

(See the Dockerfile in the repo for exact steps.)

## GitHub Actions (high-level)

Triggers: pushes to dev, PRs to main, merges to main

Steps (typical):

Setup Python, install deps, lint/test (if configured)

Build image with Docker/Buildx

Login to ACR/GHCR (OIDC or secrets)

Push image (tags include branch/commit for traceability)

(Optional) Deploy/update Container App, or let infra repo pick up the new tag

(See .github/workflows/*.yml in the repo.)

## Run Locally (Python)

```bash

Prereqs: Python 3.12, pip

# 1) clone
git clone <your-app-repo>
cd <your-app-repo>

# 2) venv
python3.12 -m venv .venv
source .venv/bin/activate

# 3) install
pip install -r requirements.txt

# 4) DB (choose one)
export DB_URL="sqlite:///./app.db"
# or:
# export DB_URL="postgresql+psycopg://USER:PASS@HOST:5432/fitapp?sslmode=require"

# 5) optional port
export PORT=8030

# 6) run
uvicorn app.main:api --host 0.0.0.0 --port ${PORT:-8030} --reload

```


## Open UI and docs:

```bash
UI: http://localhost:8030/

Docs: http://localhost:8030/docs
```

## Build & Run with Docker
```bash
Build

docker build -t fitapp-api:local .


Run with SQLite (bind mount for persistence)

mkdir -p data
docker run --rm -it \
  -e DB_URL="sqlite:////data/app.db" \
  -e PORT=8030 \
  -p 8030:8030 \
  -v "$(pwd)/data:/data" \
  fitapp-api:local


Run with PostgreSQL

docker run --rm -it \
  -e DB_URL="postgresql+psycopg://USER:PASS@HOST:5432/fitapp?sslmode=require" \
  -e PORT=8030 \
  -p 8030:8030 \
  fitapp-api:local
```

## Run via GitHub Actions

Push to dev → CI builds and pushes image (e.g., dev-<shortsha>).

Open PR from dev → main for review.

Merge to main → CI builds and pushes prod/main tag.

## Deploy either:

Automatically in this repo’s workflow (Azure login + az containerapp update), or

Via the Terraform infra repo by updating container_image_tag and running terraform apply.

## Branching Strategy

Branches: dev, main

Work in dev → open PR into main

On merge to main, the pipeline triggers automatically

Images are tagged by branch/commit for traceability

## Future Improvements

AuthN/AuthZ: JWT or Azure AD; RBAC (admin vs caregiver)

Schema migrations: add Alembic

Caching: HTTP caching for reads; CDN for static UI

Observability: structured logs (JSON), OpenTelemetry, Sentry

Rules: stricter enums; business constraints (e.g., reward ≤ price)

Search: full-text on name/description

## Quick Reference

UI: /

Docs: /docs

Health: /health

DB Info: /__dbinfo

Items: /api/v1/items (GET/POST)

Item: /api/v1/items/{id} (GET/DELETE)

Seed: /api/v1/items/seed_demo (POST)

Recommend: /api/v1/recommend?goal=stress&device=watch
