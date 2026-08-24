# Intelligent Patient Flow Backend

Repository name: `intelligent_patient_flow_backend`

The Intelligent Patient Flow and Appointment Scheduling System is a healthcare management product designed to help hospitals and clinics organize patient appointments, doctor schedules, check-ins, and service queues. The system will allow patients to book, reschedule, or cancel appointments, select doctors or specialties, check in through reception, mobile devices, or QR codes, and monitor their queue status in real time. Healthcare staff will use the web system to manage practitioner availability, shifts, consultation rooms, service points, patient flow, and daily operations. The product will also provide reports on waiting time, appointment utilization, attendance, and practitioner workload. In later phases, intelligent features will be added to predict waiting times, forecast patient arrivals, and recommend suitable appointment slots. The backend will serve both the web dashboard and the mobile application through secure, versioned APIs.


## Architecture

- Django 5 with Django REST Framework
- Modular-monolith organized around `apps/`, `common/`, and `config/`
- PostgreSQL, Redis, and Celery prepared for later business implementation
- drf-spectacular for schema and docs
- pytest, pytest-django, and Ruff for the development foundation

## Django Applications

- `accounts`
- `facilities`
- `patients`
- `practitioners`
- `scheduling`
- `queueing`
- `checkins`
- `notifications`
- `reporting`
- `audit`
- `intelligence`

## Internal App Structure

Each app is prepared with:

- `migrations/`
- `serializers/`
- `selectors/`
- `services/`
- `permissions/`
- `views/`
- `urls/`
- `tests/`
- `admin.py`
- `apps.py`
- `__init__.py`

Business models, business APIs, and RBAC are intentionally not implemented yet.

## Local Setup

1. Copy `.env.example` to `.env`
2. Start the stack:
   `docker compose up --build`

Detached mode:
`docker compose up --build -d`
`docker compose exec -T api python manage.py seed_mwimbiri_demo --days 90`

## Environment Variables

- `DJANGO_SETTINGS_MODULE`
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CORS_ALLOWED_ORIGINS`
- `DJANGO_ENVIRONMENT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `APP_ENV`
- `EMAIL_BACKEND`
- `DEFAULT_FROM_EMAIL`

## Docker

Main startup command:
`docker compose up --build`

Also supported:

- `docker compose up`
- `docker compose up --build -d`
- `docker compose down`
- `docker compose down -v`

Services started:

- `api`
- `postgres`
- `redis`
- `celery_worker`
- `celery_beat`

Startup behavior:

- waits for PostgreSQL
- waits for Redis
- runs `python manage.py migrate --noinput`
- runs `python manage.py collectstatic --noinput`
- starts Django on `0.0.0.0:8000`

No manual migration command is required after `docker compose up` or `docker compose up --build`.

## Health Endpoints

- `GET /health/live/`
- `GET /health/ready/`

## API Documentation

- OpenAPI schema: `/api/schema/`
- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`

## Tests And Linting

- Run tests: `docker compose exec api pytest`
- Run Ruff: `docker compose exec api ruff check .`

## Current Scope

- business models have not been implemented
- database design has not been finalized
- business APIs have not been implemented
- dynamic roles and permissions will be designed later
