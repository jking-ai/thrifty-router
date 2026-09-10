#!/usr/bin/env bash
# Deploy Thrifty Router to GCP.
#   - Backend → Cloud Run
#   - Report  → Firebase Hosting
#
# Usage: bash scripts/deploy.sh [backend|report|all]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"
REPORT_DIR="$PROJECT_DIR/report"

GCP_PROJECT="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
if [ -z "$GCP_PROJECT" ]; then
    echo "Error: GCP_PROJECT is not set and no active gcloud project found."
    exit 1
fi
GCP_REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-thrifty-router}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-${SERVICE_NAME}-sa@${GCP_PROJECT}.iam.gserviceaccount.com}"

TARGET="${1:-all}"

deploy_backend() {
    echo "═══════════════════════════════════════"
    echo "  Deploying Backend → Cloud Run"
    echo "═══════════════════════════════════════"

    cd "$BACKEND_DIR"

    gcloud run deploy "$SERVICE_NAME" \
        --source . \
        --region "$GCP_REGION" \
        --project "$GCP_PROJECT" \
        --service-account "$SERVICE_ACCOUNT" \
        --allow-unauthenticated \
        --memory 512Mi \
        --cpu 1 \
        --min-instances 0 \
        --max-instances 1 \
        --timeout 120 \
        --set-env-vars="GCP_PROJECT_ID=${GCP_PROJECT},GCP_REGION=${GCP_REGION},GEMINI_LOCATION=global,CACHE_ENABLED=true" \
        --set-secrets="API_KEY=thrifty-router-api-key:latest"

    BACKEND_URL=$(gcloud run services describe "$SERVICE_NAME" \
        --region "$GCP_REGION" \
        --project "$GCP_PROJECT" \
        --format="value(status.url)")

    echo ""
    echo "✓ Backend deployed: $BACKEND_URL"
    echo "  Health check: $BACKEND_URL/api/v1/health"
    echo ""

    echo "Verifying health endpoint..."
    if curl -sf "$BACKEND_URL/api/v1/health" | python3 -m json.tool; then
        echo ""
        echo "✓ Backend is healthy"
    else
        echo ""
        echo "⚠ Health check failed — warming up"
    fi
}

deploy_report() {
    echo "═══════════════════════════════════════"
    echo "  Deploying Report → Firebase Hosting"
    echo "═══════════════════════════════════════"

    cd "$PROJECT_DIR"

    echo "Applying hosting target 'router-report' -> 'thrifty-router'..."
    firebase target:apply hosting router-report thrifty-router --project "$GCP_PROJECT"

    echo "Deploying hosting target..."
    firebase deploy --only hosting:router-report --project "$GCP_PROJECT"

    echo ""
    echo "✓ Report deployed to https://thrifty-router.web.app"
    echo ""
}

case "$TARGET" in
    backend)
        deploy_backend
        ;;
    report)
        deploy_report
        ;;
    all)
        deploy_backend
        deploy_report
        ;;
    *)
        echo "Usage: bash scripts/deploy.sh [backend|report|all]"
        exit 1
        ;;
esac

echo "═══════════════════════════════════════"
echo "  Deployment completed!"
echo "═══════════════════════════════════════"
