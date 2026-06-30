#!/usr/bin/env bash
set -e

bash ./scripts/wait-for-services.sh
celery -A config worker --loglevel=info
