from copy import deepcopy

from .base import *  # noqa: F403

DEBUG = False

# The project uses PostgreSQL-specific migrations and constraints, so pytest
# must run against PostgreSQL instead of SQLite.
DATABASES = deepcopy(DATABASES)  # noqa: F405
DATABASES["default"]["TEST"] = {
    "NAME": "test_intelligent_patient_flow_backend",
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
