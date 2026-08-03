#!/usr/bin/env bash
set -euo pipefail

CHART_DIR="./helm/apowerb"
DOCKERHUB_NAMESPACE="${DOCKERHUB_NAMESPACE:-$DOCKERHUB_USERNAME}"

helm lint "$CHART_DIR"
helm package "$CHART_DIR"

echo "$DOCKERHUB_TOKEN" | helm registry login registry-1.docker.io \
  --username "$DOCKERHUB_USERNAME" \
  --password-stdin

CHART_TGZ=$(ls -1 *.tgz | head -n 1)
helm push "$CHART_TGZ" "oci://registry-1.docker.io/${DOCKERHUB_NAMESPACE}"
