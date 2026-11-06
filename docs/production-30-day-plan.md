# Production-Ready MVP — 30-Session Plan (Sessions 31–60)

**Recorded:** 2026-11-06
**Status:** Active working schedule — supersedes the revised Days 31–60 in [`roadmap-60-days.md`](roadmap-60-days.md)
**Decision record:** [ADR-011](decisions.md#adr-011--re-scope-sessions-3160-to-a-production-ready-single-organization-mvp)
**Session budget:** 30 sessions × up to 2 hours (≈60 hours)

## Why this plan exists

Two independent code reviews after the Day 30 PostgreSQL cutover agreed that the
project is a well-structured, security-first MVP (≈7.5/10 code quality) with
significant production gaps (≈4/10 production readiness). The remaining revised
roadmap (Days 31–60) would deliver a lab-grade v0.1, not a production-ready one.
Doing both in 30 sessions is not realistic, so scope is cut deliberately.

## Target definition

**Production-ready MVP** means:

- One organization, self-hosted on a single VM with Docker Compose behind TLS.
- Multiple applications with database-backed, revocable, rotatable API keys.
- Policy decisions from a verified OPA bundle with a required policy version/digest.
- One real model provider through an OpenAI-compatible adapter (Ollama, vLLM, hosted).
- Durable, append-only, hash-chained evidence with export and offline verification.
- Authorization decisions and inference outcomes recorded separately.
- Metrics, structured logs, readiness checks, backups and a tested restore.

**Explicitly not included:** high availability, multi-tenancy, streaming,
SSO/federated IAM, Kubernetes, distributed rate limiting.

**Deferred to v0.2:** trusted data-classification routing (CTRL-002, revised
Day 30/31). This is the largest trade-off; if classification is more important
than load testing and tracing, swap it into sessions P25–P26.

## Review findings this plan addresses

| Finding | Session(s) |
| --- | --- |
| Compose stack never runs Alembic migrations; image lacks `alembic/` | P2, P3 |
| Governance configuration duplicated across Rego, `model_registry.py`, test fake and DB | P6 |
| HTTP clients created per request; configuration read per request | P4 |
| SQLite compatibility branch and sync repository still on the runtime path | P5 |
| Single env-configured API key; no revocation/rotation | P8, P9 |
| `policy_version` optional; no deployed-artifact provenance | P11 |
| Evidence records authorization but not inference outcome | P13 |
| No `/health/ready` | P4 |
| Dev/unused dependencies in the runtime image; no dependency scanning | P1, P24 |
| `main` not branch-protected; no `LICENSE`/`SECURITY.md` | P1 |
| README out of date with implemented behavior | P5, P28 |
| Hash chain assumes a single ordered writer | P16 |
| Gateway tests use mocked OPA; no full-stack acceptance test | P3, P6, P27 |

## Week 1 — Make it run; remove duplicate paths (Sessions 31–37)

| Session | Work | Done when |
| --- | --- | --- |
| **P1** (31) | Enable branch protection with required CI. Add `LICENSE`, `SECURITY.md`, Dependabot. Split runtime/dev requirements, remove unused packages, add `pip-audit` to CI. | Runtime image has no pytest/ruff; CI fails on known CVEs |
| **P2** (32) | Add a one-shot `migrate` Compose service; copy `alembic/` and `alembic.ini` into the image; gateway `depends_on` healthy postgres/opa/migrate. Archive the historical SQLite evidence (per ADR-010) before removing its mount and env var. | Fresh `docker compose up` serves an allowed request with HTTP 200 |
| **P3** (33) | CI Compose smoke-test job: start the stack, send allowed and denied requests, assert rows in `decisions`. | Full gateway + OPA + PostgreSQL job green in CI |
| **P4** (34) | Typed settings (pydantic-settings) validated at startup; lifespan-owned HTTPX clients; `/health/ready` checking PostgreSQL and OPA. | Invalid config fails startup; readiness fails when the DB is down |
| **P5** (35) | Remove the SQLite runtime path, sync repository and `isinstance` branch; default test fixture becomes an async fake evidence writer; refresh README. | Single evidence code path; README matches behavior |
| **P6** (36) | Single source of truth: `policies/data.json` (applications, models, routes) loaded into OPA as data; Rego and the Python route table both read it; replace the Python re-implementation of Rego in `conftest.py` with real OPA in CI. | Changing one file changes behavior everywhere |
| **P7** (37) | **Buffer.** One-page threat model v1: assets, actors, trust boundaries. | Threat model committed |

## Week 2 — Identity, policy integrity, limits (Sessions 38–44)

| Session | Work | Done when |
| --- | --- | --- |
| **P8** (38) | DB-backed API keys: `aicp_<credential_id>_<secret>` format, lookup by ID, constant-time SHA-256 digest comparison, `is_active` and expiry checks; identity derived from the database. | Multiple applications authenticate; env-var key removed |
| **P9** (39) | Admin CLI: create/rotate/revoke keys, seed applications and models. Tests for revoked, expired and spoofed credentials. | A revoked key returns 401 on the next request |
| **P10** (40) | Administrator authentication: separate credential type and role; negative tests. | Application keys cannot reach admin routes |
| **P11** (41) | Build an OPA bundle in CI and record its digest; OPA loads the bundle; `policy_version`/revision required and checked against the expected digest from configuration, at readiness and per decision. | Missing or mismatched policy version returns 503 |
| **P12** (42) | Request limits: body size, message count, provider timeout budget, per-application rate limit (per instance, documented). | 413 and 429 paths tested |
| **P13** (43) | `inference_outcomes` table (success / failure / unknown) linked by `request_id`; a timeout records `unknown`. | AC-009 passes |
| **P14** (44) | **Buffer** and review; update the threat model. | — |

## Week 3 — Evidence integrity and real provider (Sessions 45–51)

| Session | Work | Done when |
| --- | --- | --- |
| **P15** (45) | Canonical JSON serialization and per-record SHA-256 hash. | Deterministic hash tests pass |
| **P16** (46) | Hash chain with ordering enforced by a PostgreSQL advisory lock, so multiple gateway instances remain correct. | Concurrent-insert test keeps the chain valid |
| **P17** (47) | Database roles: the application role may only INSERT/SELECT evidence tables; a separate role owns migrations. | UPDATE/DELETE fail for the application role |
| **P18** (48) | Admin decision lookup (paginated) and JSONL export endpoints. | Admin-only, with negative tests |
| **P19** (49) | Offline `verify` CLI; tests for modified, deleted, reordered and truncated exports against a trusted checkpoint. | AC-010 passes |
| **P20** (50) | OpenAI-compatible provider adapter (covers Ollama, vLLM and most hosted APIs); provider credentials from secrets. | A real model answers through the gateway |
| **P21** (51) | **Buffer.** End-to-end real-model demo: allow, deny, export, verify. | Demo script committed |

## Week 4 — Operations and release (Sessions 52–60)

| Session | Work | Done when |
| --- | --- | --- |
| **P22** (52) | Structured logs and Prometheus metrics: requests, decisions by outcome, fail-closed count, latency. | `/metrics` scraped; alert rules written |
| **P23** (53) | File-based secrets (Docker secrets) instead of environment variables; Caddy TLS reverse proxy in a `prod` Compose profile. | No secrets in `docker inspect`; only HTTPS exposed |
| **P24** (54) | Image hardening: pinned image digests, read-only root filesystem, dropped capabilities; Trivy scan and SBOM in CI. | No critical CVEs in the image |
| **P25** (55) | PostgreSQL backups, restore drill, retention policy. | Restored database passes `verify` |
| **P26** (56) | Load test (k6 or Locust); set a gateway p99 latency budget; tune connection pools. | Baseline numbers documented |
| **P27** (57) | Run AC-001 to AC-010 against the Compose stack; fix critical findings. | All pass, or failures documented |
| **P28** (58) | Deployment guide, operations runbook (key rotation, policy rollout, restore), known-limitations list. | A new operator can deploy from the docs |
| **P29** (59) | Fresh-VM install following only the docs; fix blockers. | End-to-end install works |
| **P30** (60) | Tag `v0.1.0` with release notes, or publish a labeled preview release listing blockers. | Release published |

## Working rules

1. **One deliverable per session**, merged through a PR with green CI. Unmerged work is not done.
2. **Slippage:** use buffer sessions (P7, P14, P21) first. Then cut, in order: load
   test (P26) → alert rules (P22) → admin lookup endpoint (P18, keep export).
3. **Never cut:** P2–P3, P8–P9, P11, P13, P16–P17, P25. These make the release production-grade.
4. **Never weaken a fail-closed test** to make a feature pass.
5. **Keep project memory current:** update [`progress.md`](progress.md) after each
   session and record significant deviations in [`decisions.md`](decisions.md).
6. **No unqualified claims:** passing CI is not proof of security; document limitations honestly.
