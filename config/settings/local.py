from datetime import timedelta

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]  # noqa: F405
AUTH_COOKIE_SECURE = False  # noqa: F405
SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] = timedelta(days=7)  # noqa: F405
SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] = timedelta(days=30)  # noqa: F405
