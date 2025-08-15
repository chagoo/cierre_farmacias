#!/bin/bash
set -euo pipefail

# Usage: ./scripts/deploy.sh [environment]
# Default environment is production.

ENVIRONMENT=${1:-production}
COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
IMAGE_NAME="cierre_farmacias"
TAG=$(date +%Y%m%d%H%M%S)
FULL_TAG="${IMAGE_NAME}:${TAG}"

# Build and tag image
docker build --build-arg ENVIRONMENT=${ENVIRONMENT} -t ${FULL_TAG} .
docker tag ${FULL_TAG} ${IMAGE_NAME}:latest

echo ${FULL_TAG} >> deploy_history.log

docker compose -f ${COMPOSE_FILE} up -d --build

echo "Deployed ${FULL_TAG} using ${COMPOSE_FILE}" 
