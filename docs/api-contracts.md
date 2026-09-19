# API Contracts & Specification

All requests must adhere to HTTP/1.1 or HTTP/2 over TLS. Authenticated endpoints require an `X-API-Key` header or `Authorization: Bearer <key>`.

---

## Headers

### Request Headers
| Header | Type | Required | Description |
|---|---|---|---|
| `X-API-Key` | String | Optional | Gateway master key (can also use `Authorization: Bearer <key>`) |
| `Content-Type` | String | Required for POST | Must be `application/json` |

### Response Headers
The gateway sets no custom response headers. Tier, model, cost, cache status and latency are returned in the `/v1/complete` response body (`routing`, `usage`, `cache`, `latency_ms`).

---

## Endpoints

### 1. Health Check
`GET /health`
- **Auth Required:** No
- **Rate Limited:** No
- **Response `200 OK`:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-09-10T19:30:00.000000Z"
}
```

---

### 2. List Tiers
`GET /v1/tiers`
- **Auth Required:** Yes
- **Rate Limited:** Yes
- **Response `200 OK`:**
```json
{
  "default_tier": "lite",
  "tiers": [
    {
      "name": "lite",
      "model": "gemini-3.1-flash-lite",
      "price_per_m_input_usd": 0.25,
      "price_per_m_output_usd": 1.50,
      "description": "Fast lookup, formatting, and short classification"
    },
    {
      "name": "standard",
      "model": "gemini-3-flash-preview",
      "price_per_m_input_usd": 0.50,
      "price_per_m_output_usd": 3.00,
      "description": "Structured extraction and multi-step bounded tasks"
    },
    {
      "name": "pro",
      "model": "gemini-3.1-pro-preview",
      "price_per_m_input_usd": 2.00,
      "price_per_m_output_usd": 12.00,
      "description": "Deep reasoning, code architecture, and open-ended synthesis"
    }
  ]
}
```

---

### 3. Usage & Budget Telemetry
`GET /v1/usage`
- **Auth Required:** Yes
- **Rate Limited:** Yes
- **Response `200 OK`:**
```json
{
  "date": "2026-09-10",
  "requests": 128,
  "total_cost_usd": 0.428150,
  "daily_budget_usd": 2.0,
  "by_tier": {
    "lite": { "requests": 82, "cost_usd": 0.021500 },
    "standard": { "requests": 34, "cost_usd": 0.084650 },
    "pro": { "requests": 12, "cost_usd": 0.322000 }
  },
  "cache": {
    "lookups": 128,
    "hits_exact": 9,
    "hits_semantic": 15
  }
}
```

---

### 4. Generation / Routing Completion
`POST /v1/complete`
- **Auth Required:** Yes
- **Rate Limited:** Yes (`60/minute, 1000/day`)

#### Request Body
```json
{
  "prompt": "Explain the difference between TCP and UDP in 2 sentences.",
  "strategy": "cascade",
  "tier": null,
  "temperature": 0.2,
  "max_output_tokens": null,
  "json_schema": null,
  "use_cache": true
}
```

#### Request Fields
| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `prompt` | String | Yes | - | Prompt text (length >= 1) |
| `strategy` | Enum | No | `fixed` | `fixed`, `semantic`, `classifier`, `cascade` |
| `tier` | Enum | No | `null` | Required only if `strategy == fixed`; optional override |
| `temperature` | Float | No | `0.2` | Temperature (0.0 to 2.0). Responses are cached only when `temperature <= 0.3` |
| `max_output_tokens` | Integer | No | `null` | Max output tokens; falls back to the gateway's `MAX_OUTPUT_TOKENS` (default 8192, which includes Gemini 3.x thinking tokens) |
| `json_schema` | Object | No | `null` | Optional JSON Schema definition for strict output validation |
| `use_cache` | Boolean | No | `true` | Whether to read from and write to the semantic cache |

#### Response `200 OK`
```json
{
  "request_id": "req_3f9c2a1b7d",
  "output": "TCP is connection-oriented and ensures reliable, ordered packet delivery through acknowledgments, whereas UDP is connectionless and prioritizes minimal latency over guaranteed delivery.",
  "routing": {
    "strategy": "cascade",
    "tier": "lite",
    "model": "gemini-3.1-flash-lite",
    "reason": "cascade accepted at lite (confidence 95)",
    "attempts": [
      {
        "role": "completion",
        "tier": "lite",
        "model": "gemini-3.1-flash-lite",
        "latency_ms": 284,
        "input_tokens": 18,
        "output_tokens": 42,
        "thinking_tokens": 0,
        "cost_usd": 0.000068,
        "accepted": true,
        "reject_reason": null
      }
    ]
  },
  "usage": {
    "input_tokens": 18,
    "output_tokens": 42,
    "thinking_tokens": 0,
    "total_cost_usd": 0.000068
  },
  "cache": {
    "hit": false,
    "kind": null,
    "similarity": null
  },
  "latency_ms": 284
}
```

---

## Error Handling

All error responses adhere to a consistent JSON error schema:
```json
{
  "detail": {
    "code": "ERROR_CODE",
    "message": "Human-readable description of the error."
  }
}
```

| HTTP Status | Error Code | Cause |
|---|---|---|
| `401 Unauthorized` | `UNAUTHORIZED` | Missing or invalid API key |
| `429 Too Many Req` | `DAILY_BUDGET_EXCEEDED` | `total_cost_usd >= daily_budget_usd`; checked before any model call |
| `422 Unprocessable` | `VALIDATION_ERROR`| Malformed request payload, empty prompt, or invalid strategy |
| `429 Too Many Req` | `RATE_LIMIT_EXCEEDED`| Slowapi client IP rate limit threshold exceeded |
| `500 Internal Error` | `INTERNAL_ERROR` | Unhandled upstream or provider error |
