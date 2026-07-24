#!/bin/sh
set -e

# Schema vor jedem Start auf den neuesten Stand bringen — idempotent (alembic upgrade
# head ist ein No-Op, wenn die DB bereits aktuell ist), macht das Deployment aber
# ready-to-use ohne manuellen "docker compose exec app alembic upgrade head"-Schritt.
# depends_on.db.condition: service_healthy in docker-compose.yml stellt sicher, dass
# Postgres beim Start dieses Containers bereits erreichbar ist.
alembic upgrade head

exec "$@"
