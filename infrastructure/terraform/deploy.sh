#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="$ROOT_DIR/infrastructure/terraform"
FRONTEND_DIR="$ROOT_DIR/frontend"

for command in terraform aws npm python3.12 zip; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required command: $command" >&2
    exit 1
  }
done

cd "$TF_DIR"
"$TF_DIR/package.sh"
terraform init
terraform validate
terraform plan -out=techpulse.tfplan
echo
echo "Review the plan above. This script will not apply infrastructure without confirmation."
read -r -p "Apply this Terraform plan and publish the frontend? [y/N] " answer
if [[ ! "$answer" =~ ^[Yy]$ ]]; then
  echo "Plan saved at $TF_DIR/techpulse.tfplan. Nothing was applied."
  exit 0
fi

terraform apply techpulse.tfplan

API_URL="$(terraform output -raw api_endpoint)"
FRONTEND_URL="$(terraform output -raw frontend_url)"
FRONTEND_BUCKET="$(terraform output -raw frontend_bucket_name)"
DISTRIBUTION_ID="$(terraform output -raw cloudfront_distribution_id)"
COGNITO_URL="$(terraform output -raw cognito_hosted_ui_url)"
COGNITO_CLIENT_ID="$(terraform output -raw cognito_client_id)"

cd "$FRONTEND_DIR"
npm install
VITE_API_BASE_URL="$API_URL" \
VITE_COGNITO_HOSTED_UI_URL="$COGNITO_URL" \
VITE_COGNITO_CLIENT_ID="$COGNITO_CLIENT_ID" \
VITE_COGNITO_REDIRECT_URI="$FRONTEND_URL/" \
VITE_COGNITO_LOGOUT_URI="$FRONTEND_URL/" \
npm run build

aws s3 sync "$FRONTEND_DIR/dist/" "s3://$FRONTEND_BUCKET/" --delete
aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION_ID" --paths "/*" >/dev/null

echo
echo "TechPulse deployment completed: $FRONTEND_URL"
echo "Remember: Cognito users must be created by an administrator for the pilot."
