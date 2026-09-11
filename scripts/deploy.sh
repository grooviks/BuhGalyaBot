#!/usr/bin/env sh
set -eu

APP_DIR=${APP_DIR:-/opt/buhgalya}
IMAGE_TAG=${1:-}
if [ -z "$IMAGE_TAG" ]; then
  echo "Usage: $0 <image-tag>" >&2
  exit 2
fi
cd "$APP_DIR"
[ -f .env ] || { echo "Missing $APP_DIR/.env" >&2; exit 1; }
set -a
. ./.env
set +a
IMAGE_TAG=${1:-}
export IMAGE_TAG

if grep -q '^IMAGE_TAG=' .env; then
  sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${IMAGE_TAG}/" .env
else
  printf '\nIMAGE_TAG=%s\n' "$IMAGE_TAG" >> .env
fi

iam_token=$(curl --fail --silent \
  --header Metadata-Flavor:Google \
  http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token \
  | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
if [ -z "$iam_token" ]; then
  echo "Could not obtain IAM token from VM metadata service" >&2
  exit 1
fi
printf '%s' "$iam_token" | docker login --username iam --password-stdin cr.yandex >/dev/null

docker compose -f compose.prod.yaml pull
docker compose -f compose.prod.yaml run --rm api uv run alembic upgrade head
docker compose -f compose.prod.yaml up -d

attempt=0
until curl --fail --silent http://127.0.0.1:8000/health >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "API health check failed" >&2
    docker compose -f compose.prod.yaml ps
    exit 1
  fi
  sleep 2
done

docker image prune -f
echo "Deployed ${IMAGE_REPOSITORY}:${IMAGE_TAG}"
