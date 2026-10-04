# AGENTS.md — lumera-backend

## Repository Responsibility
`lumera-backend` is the authoritative core backend service for the Lumera e-commerce platform. It owns all domain entities, database persistence, transactions, business rules, pricing authority, inventory validation, and RBAC authorization.

## Allowed Technologies
* Python 3.12+
* Django 5.1+
* Django REST Framework 3.15+
* SimpleJWT
* PostgreSQL (psycopg2/psycopg)
* Pytest + pytest-django

## Directory Conventions
* `apps/<domain>/`: Modular domain applications (`users`, `common`, and future: `catalog`, `orders`, `cart`, `payments`).
* `apps/<domain>/models.py`: Database entities adhering to primary key rules (BIGINT internal, UUID `public_id` external).
* `apps/<domain>/permissions.py`: Granular RBAC permission checks (`IsStaffMember`, `HasPermission`).
* `apps/<domain>/serializers.py`: DRF input validation and output serialization.
* `apps/<domain>/urls_*.py`: Namespaced routing files mapped in `config/urls.py`.
* `config/settings/`: Settings split into `base.py`, `development.py`, and `production.py`.
* `tests/`: Automated pytest unit and integration tests.

## Coding Conventions
* PEP 8 compliance, explicit type hints where feasible.
* **No `django.contrib.admin`**: Never add `django.contrib.admin` or `django.contrib.admindocs` to `INSTALLED_APPS` or `urls.py`.
* Error format: All errors must go through `custom_exception_handler` producing `{"error": {"code": "...", "message": "...", "details": {...}}}`.
* Namespaces: Respect routing namespaces (`/api/v1/health/`, `/api/v1/auth/`, `/api/v1/storefront/`, `/api/v1/customer/`, `/api/v1/admin/`, `/api/v1/internal/`).

## Testing Requirements
* Pytest suite must pass 100%: `pytest -v`.
* Database migration check must be clean: `python manage.py makemigrations --check`.
* Write tests for new models, serializers, views, and permission boundaries.

## Git Rules
* Branch naming: `feature/<feature-name>`, `fix/<bug-name>`, `chore/<chore-name>`.
* Commit messages: Conventional Commits (`feat: ...`, `fix: ...`, `chore: ...`).
* Target branch: `main` (protected; changes merged via PR).

## Security Rules
* **Authoritative validation**: Never trust client-submitted prices, discounts, or permissions. Always recalculate and verify server-side.
* **Zero secrets committed**: Never commit real database passwords, secret keys, or API tokens.
* **Staff authorization**: Every `/api/v1/admin/` endpoint must require `IsStaffMember` and appropriate granular permissions.
* **UUID Exposure**: Never expose internal integer primary keys in public API responses; expose `public_id` (UUID).

## What the Agent Must NOT Modify
* Do not introduce frontend Next.js or React code into this repository.
* Do not attempt to mount or configure Django Admin.
* Do not alter root project architecture without an approved ADR in `lumera-spec`.

## Where Shared Project Specification Lives
All shared architectural specifications, API contracts, and database schemas live in:
`lumera-spec/` (e.g., `architecture/database.md`, `contracts/api-contract.yaml`).

## How to Handle Architecture Changes
If a data model or endpoint contract needs modification:
1. Update `lumera-spec/contracts/api-contract.yaml` and relevant architecture docs.
2. Implement model/serializer/view changes in `lumera-backend`.
3. Create and verify database migrations (`python manage.py makemigrations`).
4. Update unit tests in `tests/`.

## Definition of Done
* `pytest` passes with 0 failures.
* `python manage.py makemigrations --check` detects no uncommitted migrations.
* API responses adhere strictly to `contracts/api-contract.yaml`.
