# Lumera Headless Backend API (`lumera-backend`)

## Purpose
`lumera-backend` is the authoritative core backend service for the Lumera e-commerce platform. It encapsulates all domain models, business logic, inventory verification, pricing rules, payment processing coordination, authentication, and role-based access control (RBAC).

**Critical Architecture Rules:**
* **Django Admin Excluded:** `django.contrib.admin` is completely omitted from the application. Operational management is conducted exclusively via `lumera-cms`.
* **Single Authority:** The backend is the sole source of truth for business decisions, data validation, and transactional integrity.

---

## Architecture Role
In the Lumera ecosystem:
* Exposes a modular, multi-namespaced REST API under `/api/v1/`:
  * `/api/v1/health/` — Liveness & database connection checks
  * `/api/v1/auth/` — Customer authentication and token rotation
  * `/api/v1/storefront/` — Public catalog & configuration endpoints
  * `/api/v1/customer/` — Protected customer account & profile endpoints
  * `/api/v1/admin/` — Protected staff operational CMS endpoints (RBAC-enforced)
  * `/api/v1/internal/` — Machine-to-machine & webhook integration
* Enforces standard normalized error responses:
  ```json
  {
    "error": {
      "code": "error_code",
      "message": "Human readable explanation",
      "details": {}
    }
  }
  ```

```text
lumera-frontend (Storefront) ────┐
                                 ├──► lumera-backend (Django REST Framework) ──► PostgreSQL
lumera-cms (Admin Operations) ───┘
```

---

## Technology Stack
* **Language:** Python 3.12+
* **Framework:** Django 5.1+
* **API Toolkit:** Django REST Framework 3.15+
* **Authentication:** SimpleJWT (JWT with token rotation)
* **Database:** PostgreSQL (with SQLite support for isolated local tests)
* **Test Runner:** Pytest + pytest-django

---

## Repository Structure
```text
lumera-backend/
├── apps/
│   ├── users/               # Custom User model, Role RBAC, auth & admin endpoints
│   │   ├── migrations/      # Database migrations
│   │   ├── models.py        # User & Role entity models
│   │   ├── permissions.py   # IsStaffMember & HasPermission DRF classes
│   │   ├── serializers.py   # User & Token serializers
│   │   ├── urls_auth.py     # /api/v1/auth/ routes
│   │   ├── urls_customer.py # /api/v1/customer/ routes
│   │   └── urls_admin.py    # /api/v1/admin/ routes
│   └── common/              # Common utilities, exceptions, health, storefront config
│       ├── exceptions.py    # custom_exception_handler (normalized error format)
│       ├── pagination.py    # Standard cursor and page pagination
│       ├── urls_storefront.py # /api/v1/storefront/ routes
│       ├── urls_internal.py   # /api/v1/internal/ routes
│       └── views.py         # health_check, custom_404_view, custom_500_view
├── config/                  # Project configuration & settings split
│   ├── settings/
│   │   ├── base.py          # Shared baseline settings (NO django.contrib.admin)
│   │   ├── development.py   # Development settings
│   │   └── production.py    # Production settings
│   ├── asgi.py
│   ├── wsgi.py
│   └── urls.py              # Root namespaced URL dispatcher
├── tests/                   # Pytest test suite (health, auth, rbac, errors)
├── Dockerfile               # Multi-stage production container build
├── manage.py                # Django CLI entrypoint
├── pytest.ini               # Pytest configuration
├── requirements.txt         # Pinned python dependencies
└── AGENTS.md                # AI agent operating instructions
```

---

## Local Development
### Prerequisites
* Python 3.12+
* PostgreSQL 16 (or local Docker container)

### Installation & Run
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env

# Run database migrations
python manage.py migrate

# Start local server
python manage.py runserver 127.0.0.1:8000
```
Open [http://127.0.0.1:8000/api/v1/health/](http://127.0.0.1:8000/api/v1/health/) to verify system health.

---

## Environment Variables
Defined in `.env.example`:
```env
DJANGO_SECRET_KEY=insecure-dev-key-change-in-production-lumera-2026
DJANGO_SETTINGS_MODULE=config.settings.development
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,backend
DATABASE_URL=postgres://lumera_user:lumera_pass@localhost:5432/lumera_db
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000,http://127.0.0.1:3001
CSRF_TRUSTED_ORIGINS=http://localhost:3000,http://localhost:3001
JWT_ACCESS_MINUTES=15
JWT_REFRESH_DAYS=7
```
Never commit `.env` or production credentials.

---

## Running Tests
```bash
# Run full pytest suite
pytest -v

# Check for missing database migrations
python manage.py makemigrations --check
```

---

## Build
```bash
# Docker build
docker build -t lumera-backend .
```

---

## Related Repositories
* [lumera-spec](https://github.com/yeasin-dev-me/lumera-spec) — Single Source of Truth for architecture & contracts
* [lumera-frontend](https://github.com/yeasin-dev-me/lumera-frontend) — Customer-facing Next.js Storefront
* [lumera-cms](https://github.com/yeasin-dev-me/lumera-cms) — Operational Next.js CMS
* [lumera-integration](https://github.com/yeasin-dev-me/lumera-integration) — Cross-system contract and E2E tests
* [lumera-devops](https://github.com/yeasin-dev-me/lumera-devops) — Deployment, Docker, and Nginx configurations

---

## Documentation
* Architecture: [lumera-spec/architecture/architecture.md](https://github.com/yeasin-dev-me/lumera-spec/blob/main/architecture/architecture.md)
* Database Schema: [lumera-spec/architecture/database.md](https://github.com/yeasin-dev-me/lumera-spec/blob/main/architecture/database.md)
* API Architecture: [lumera-spec/architecture/api-architecture.md](https://github.com/yeasin-dev-me/lumera-spec/blob/main/architecture/api-architecture.md)
* API Contract: [lumera-spec/contracts/api-contract.yaml](https://github.com/yeasin-dev-me/lumera-spec/blob/main/contracts/api-contract.yaml)

---

## Contribution / Git Workflow
1. Branch from `main`: `feature/<domain>` or `fix/<bug-name>`.
2. Follow Conventional Commits (`feat: ...`, `fix: ...`, `chore: ...`).
3. Ensure `pytest` passes and `python manage.py makemigrations --check` is clean.
4. Merge to `main` via squash-and-merge.
