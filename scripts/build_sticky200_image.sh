#!/usr/bin/env bash
# Build and tag betfair-rest-client for sticky K=200 deployment.
# Usage:
#   export IMAGE_NAME=ghcr.io/myorg/betfair-rest-client   # or your registry/image
#   ./scripts/build_sticky200_image.sh
# Optionally push: docker push "${IMAGE_NAME}:${TAG}"

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SHORT_SHA=$(git rev-parse --short HEAD)
DATE_TAG=$(date +%Y%m%d)
TAG="sticky200-${DATE_TAG}-${SHORT_SHA}"
IMAGE_NAME="${IMAGE_NAME:-netbet/betfair-rest-client}"

echo "Building ${IMAGE_NAME}:${TAG} from ./betfair-rest-client"
docker build -t "${IMAGE_NAME}:${TAG}" ./betfair-rest-client

echo "Built ${IMAGE_NAME}:${TAG}"
echo "Push with: docker push ${IMAGE_NAME}:${TAG}"
