#!/bin/sh
PY_VERSION=${1:-"3.14"}

export UV_PROJECT_ENVIRONMENT=.venv-test
export UV_PYTHON=$PY_VERSION

uv run ruff format src/ tests/
uv run ruff check src/ tests/ 
uv run mypy --cache-fine-grained src/ tests/
uv run pytest
# check if kubernertes cluster is available for e2e tests
kubectl version --short
if [ $? -ne 0 ]; then
    echo "Skipping e2e tests as kubectl is not configured"
    exit 0
fi
PODS_COUNT=$(kubectl get pods  --output=json | jq '.items | length')
if [ $PODS_COUNT -ne 0 ]; then
    echo "Skipping e2e tests as kubernetes default namespace is not empty"
    exit 0
fi
uv run pytest e2e-tests/
