#!/usr/bin/env bash
# Smoke test script for Thrifty Router API

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
API_KEY="${2:-dev}"

echo "════════════════════════════════════════════════════"
echo "  Thrifty Router Smoke Test"
echo "  Target: $BASE_URL"
echo "════════════════════════════════════════════════════"

# 1. Health check
echo -e "\n1. GET /api/v1/health (no auth)..."
curl -s -f "$BASE_URL/api/v1/health" | python3 -m json.tool

# 2. Tiers list
echo -e "\n2. GET /api/v1/tiers (no auth)..."
curl -s -f "$BASE_URL/api/v1/tiers" | python3 -m json.tool

# 3. Auth failure test
echo -e "\n3. POST /api/v1/complete without key (expect 401)..."
AUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/complete" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"hello","strategy":"fixed","tier":"lite"}')
echo "HTTP Status: $AUTH_CODE"
if [ "$AUTH_CODE" -ne 401 ]; then
  echo "Expected 401 but received $AUTH_CODE"
  exit 1
fi
echo "✓ Auth protection verified"

# 4. Fixed strategy call
echo -e "\n4. POST /api/v1/complete (fixed: lite)..."
curl -s -X POST "$BASE_URL/api/v1/complete" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is 2+2? Answer in one word.","strategy":"fixed","tier":"lite"}' | python3 -m json.tool

# 5. Semantic strategy call
echo -e "\n5. POST /api/v1/complete (semantic)..."
curl -s -X POST "$BASE_URL/api/v1/complete" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is the capital of France?","strategy":"semantic"}' | python3 -m json.tool

# 6. Classifier strategy call
echo -e "\n6. POST /api/v1/complete (classifier)..."
curl -s -X POST "$BASE_URL/api/v1/complete" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Explain the difference between TCP and UDP.","strategy":"classifier"}' | python3 -m json.tool

# 7. Cascade strategy call
echo -e "\n7. POST /api/v1/complete (cascade)..."
curl -s -X POST "$BASE_URL/api/v1/complete" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is the square root of 144?","strategy":"cascade"}' | python3 -m json.tool

# 8. Usage check
echo -e "\n8. GET /api/v1/usage..."
curl -s -H "X-API-Key: $API_KEY" "$BASE_URL/api/v1/usage" | python3 -m json.tool

echo -e "\n════════════════════════════════════════════════════"
echo "  ✓ All smoke tests completed successfully!"
echo "════════════════════════════════════════════════════"
