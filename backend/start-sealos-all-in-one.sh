#!/bin/sh
set -eu

alembic upgrade head

celery -A app.worker.celery_app worker --loglevel=INFO &

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
