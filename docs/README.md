# Thrifty Router Documentation

Welcome to the documentation suite for **Thrifty Router**, an intelligent cost-optimizing LLM proxy for Google Cloud Vertex AI.

## Documentation Index

1. [Architecture & System Design](architecture.md)
   - Comprehensive system diagrams, request lifecycles, routing algorithms, cost ledgers, and caching topology.
2. [API Contracts & Schema Specifications](api-contracts.md)
   - Detailed specification of endpoints (`/health`, `/v1/tiers`, `/v1/usage`, `/v1/complete`), Pydantic models, and custom headers.
3. [Milestones & Implementation Deliverables](milestones.md)
   - Phased breakdown from Gateway Core to Eval Harness and Labs site showcase.
4. [Local Development Guide](local-dev-guide.md)
   - Step-by-step instructions for Python 3.12+ environment bootstrap, local server execution, configuration options, and debugging.
5. [Testing & Quality Assurance Guide](local-testing-guide.md)
   - Unit testing, mocked Vertex AI integration, rate limiting validation, and golden dataset verification.
6. [Production Deployment Guide](production-deployment.md)
   - Google Cloud Run container deployment, Firestore vector search configuration, environment secrets, and Cloud CDN/Firebase Hosting routing.
7. [Original Project Specifications](specs/thrifty-router-overview.md)
   - Upstream specifications and reference requirements.
