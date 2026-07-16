from datetime import timedelta

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]  # noqa: F405
CORS_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS or [  # noqa: F405
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CSRF_TRUSTED_ORIGINS = [  # noqa: F405
    *CORS_ALLOWED_ORIGINS,  # noqa: F405
]
AUTH_COOKIE_SECURE = False  # noqa: F405
SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(days=7)  # noqa: F405
SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(days=30)  # noqa: F405
