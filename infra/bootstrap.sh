#!/usr/bin/env bash
# One-time setup: the bucket that stores Terraform state.
# Terraform cannot create the bucket its own state lives in, so this runs before `terraform init`.
#
# Usage: infra/bootstrap.sh <project-id> [region]
set -euo pipefail

PROJECT="${1:?usage: infra/bootstrap.sh <project-id> [region]}"
REGION="${2:-asia-east1}"
BUCKET="${PROJECT}-tfstate"

if gcloud storage buckets describe "gs://${BUCKET}" --project="${PROJECT}" >/dev/null 2>&1; then
  echo "state bucket gs://${BUCKET} already exists"
else
  gcloud storage buckets create "gs://${BUCKET}" \
    --project="${PROJECT}" \
    --location="${REGION}" \
    --uniform-bucket-level-access \
    --public-access-prevention
fi

# Versioning lets us recover an earlier state if one is ever corrupted.
gcloud storage buckets update "gs://${BUCKET}" --versioning

echo "next: terraform -chdir=infra/terraform init -backend-config=bucket=${BUCKET}"
