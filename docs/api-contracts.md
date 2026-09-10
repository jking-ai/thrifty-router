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
Every generation response includes informative metadata headers:
| Header | Example | Description |
|---|---|---|
| `X-Thrifty-Tier` | `lite` | Chosen or final serving model tier (`lite`, `standard`, `pro`) |
| `X-Thrifty-Model` | `gemini-2.5-flash` | Concrete Vertex AI model identifier used |
| `X-Thrifty-Cost-Usd` | `0.000045` | Calculated micro-dollar cost rounded to 6 decimal places |
| `X-Thrifty-Latency-Ms` | `342` | End-to-end gateway execution latency in milliseconds |
| `X-Thrifty-Cached` | `false` | `true` if served from exact or semantic cache; `false` otherwise |
| `X-Thrifty-Strategy` | `cascade` | Strategy responsible for dispatch |
| `X-Thrifty-Escalations` | `0` | Count of model escalations performed (cascade strategy) |

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
  "tiers": [
    {
      "name": "lite",
      "model": "gemini-2.5-flash",
      "input_cost_per_m": 0.075,
      "output_cost_per_m": 0.30,
      "description": "Fastest and cheapest tier for simple tasks"
    },
    {
      "name": "standard",
      "model": "gemini-1.5-flash",
      "input_cost_per_m": 0.075,
      "output_cost_per_m": 0.30,
      "description": "General-purpose workhorse model"
    },
    {
      "name": "pro",
      "model": "gemini-2.5-pro",
      "input_cost_per_m": 1.25,
      "output_cost_per_m": 5.00,
      "description": "Maximum reasoning capabilities for complex tasks"
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
  "daily_spend_usd": 0.428150,
  "daily_budget_usd": 10.0,
  "budget_remaining_usd": 9.571850,
  "request_count": 128,
  "cache_hit_rate": 0.185,
  "tier_breakdown": {
    "lite": 82,
    "standard": 34,
    "pro": 12
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
  "max_tokens": 1024,
  "schema": null
}
```

#### Request Fields
| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `prompt` | String | Yes | - | Prompt text (length >= 1) |
| `strategy` | Enum | No | `cascade` | `fixed`, `semantic`, `classifier`, `cascade` |
| `tier` | Enum | No | `null` | Required only if `strategy == fixed`; optional override |
| `temperature` | Float | No | `0.7` | Temperature (0.0 to 2.0) |
| `max_tokens` | Integer | No | `null` | Max output tokens |
| `schema` | Object | No | `null` | Optional JSON Schema definition for strict output validation |

#### Response `200 OK`
```json
{
  "text": "TCP is connection-oriented and ensures reliable, ordered packet delivery through acknowledgments, whereas UDP is connectionless and prioritizes minimal latency over guaranteed delivery.",
  "tier": "lite",
  "model": "gemini-2.5-flash",
  "strategy": "cascade",
  "escalations": 0,
  "cost_usd": 0.000034,
  "latency_ms": 284,
  "cached": false,
  "tokens": {
    "prompt_tokens": 18,
    "candidates_tokens": 42,
    "thinking_tokens": 0,
    "total_tokens": 60
  }
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
| `402 Payment Required`| `BUDGET_EXCEEDED`| `daily_spend_usd >= daily_budget_usd` |
| `422 Unprocessable` | `VALIDATION_ERROR`| Malformed request payload, empty prompt, or invalid strategy |
| `429 Too Many Req` | `RATE_LIMIT_EXCEEDED`| Slowapi client IP rate limit threshold exceeded |
| `500 Internal Error` | `INTERNAL_ERROR` | Unhandled upstream or provider error |
