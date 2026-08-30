# Agent Guidelines & Continuity Context — AI Customer Support SaaS

This repository contains a multi-tenant AI Customer Support SaaS platform built with FastAPI, PostgreSQL (`pgvector`), Redis, Celery, and React/TypeScript.

## Project Quickstart for Agents

### How to Run the Environment
```bash
docker compose up --build -d
```

### How to Run Database Migrations
```bash
docker compose run --rm backend alembic upgrade head
```

### How to Run Tests
```bash
docker compose exec backend pytest -v
```

---

## Architectural & Coding Rules (Mandatory)

1. **Logical Multi-Tenancy**: Every database query on organization resources MUST explicitly filter by `organization_id`. Never rely on frontend filtering.
2. **Layered Architecture**: Route $\rightarrow$ Service $\rightarrow$ Repository/Model $\rightarrow$ Database. Do NOT put heavy business logic inside FastAPI route handlers.
3. **AI Abstraction Protocol**:
   - `LLMProvider` protocol in `app.services.ai.llm_provider`
   - `EmbeddingProvider` protocol in `app.services.ai`
   - Never call third-party SDKs directly in route handlers or unrelated services.
4. **Offline Mock Fallbacks**: When `LLM_API_KEY` or `EMBEDDING_API_KEY` is set to `"mock-key"`, AI providers must return deterministic mock responses/vectors so the entire test suite runs offline without external network dependency.
5. **Alembic Migrations**: Any database schema modification requires generating an Alembic migration revision.
6. **Testing Requirement**: Every completed feature must include automated tests in `backend/tests/`. Never declare a task complete without `pytest` passing.

---

## Current Architecture Map

- **Config**: [backend/app/core/config.py](file:///home/hizkyas/Documents/customersupport/backend/app/core/config.py)
- **Database Session & Base**: [backend/app/db/session.py](file:///home/hizkyas/Documents/customersupport/backend/app/db/session.py)
- **Auth & Tenant Dependencies**: [backend/app/api/dependencies.py](file:///home/hizkyas/Documents/customersupport/backend/app/api/dependencies.py)
- **Document Extractor & Chunker**: [backend/app/services/documents/](file:///home/hizkyas/Documents/customersupport/backend/app/services/documents/)
- **Document Pipeline Worker**: [backend/app/workers/document_pipeline.py](file:///home/hizkyas/Documents/customersupport/backend/app/workers/document_pipeline.py)
- **AI Provider Protocols & RAG**: [backend/app/services/ai/](file:///home/hizkyas/Documents/customersupport/backend/app/services/ai/)
- **Support Queue & Escalation**: [backend/app/api/routes/support.py](file:///home/hizkyas/Documents/customersupport/backend/app/api/routes/support.py)
- **Rate Limiter & Exceptions**: [backend/app/core/rate_limit.py](file:///home/hizkyas/Documents/customersupport/backend/app/core/rate_limit.py), [backend/app/core/exceptions.py](file:///home/hizkyas/Documents/customersupport/backend/app/core/exceptions.py)
- **Audit Logging Service & API**: [backend/app/services/audit_service.py](file:///home/hizkyas/Documents/customersupport/backend/app/services/audit_service.py), [backend/app/api/routes/audit.py](file:///home/hizkyas/Documents/customersupport/backend/app/api/routes/audit.py)

---

## Phase Status Overview

- [x] **Phase 1 — Foundation**: Docker Compose, PostgreSQL + pgvector, Redis, FastAPI, Celery worker, logging, healthcheck.
- [x] **Phase 2 — Auth & Multi-Tenancy**: User, Organization, Membership models, JWT login/signup, tenant isolation, RBAC.
- [x] **Phase 3 — Knowledge Base Pipeline**: Document model, pgvector chunk storage (1536-dim), text extraction (PDF, DOCX, TXT, MD), paragraph chunking, async Celery pipeline.
- [x] **Phase 4 — AI Chat & RAG**: Conversation models, vector search, LLM grounding, citation generation, chat endpoints.
- [x] **Phase 5 — Human Support & Escalations**: Support queue, agent assignment, human replies, internal notes, AI suggested replies, resolve/reopen flow.
- [x] **Phase 6 — Admin Dashboard Frontend**: React + TypeScript + Vite dashboard for managing documents, support queue, chat timeline, team members, and AI settings.
- [x] **Phase 7 — Embeddable Widget**: Embeddable website chat widget with floating launcher, session persistence, RAG chat, document citations, human escalation, and copyable script snippet generator.
- [x] **Phase 8 — Production Quality & Polish**: Rate limiting, audit logs, error handling, final portfolio documentation & README.
