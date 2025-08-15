#!/bin/bash
set -euo pipefail

# Usage: ./scripts/rollback.sh [environment]
# Rolls back to the previous image stored in deploy_history.log

ENVIRONMENT=${1:-production}
COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"

if [ ! -f deploy_history.log ] || [ $(wc -l < deploy_history.log) -lt 2 ]; then
  echo "No previous deployment to roll back to." >&2
  exit 1
fi

LAST_TAG=$(tail -n 2 deploy_history.log | head -n 1)
IMAGE_NAME="cierre_farmacias"

docker tag ${LAST_TAG} ${IMAGE_NAME}:latest

docker compose -f ${COMPOSE_FILE} up -d --build

echo "Rolled back to ${LAST_TAG}" 
