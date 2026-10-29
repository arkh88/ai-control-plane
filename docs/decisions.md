# Architecture Decision Log — AI Governance & Security Control Plane

**Last updated:** 2026-10-29  
**Project status:** Day 22 complete (developer-reported), revised Day 23 next.  
**Purpose:** Preserve *why* the architecture and roadmap changed so future conversations can start from repository facts rather than reconstructing historical chat context.

## Conventions

- **Implemented / reported** means the functionality was described as completed and tested, but should be verified against current repository source and CI when connected.
- **Proposed** means a recommended direction, **not** yet implemented or conclusively approved.
- **Superseded** means replaced by a newer decision. Never silently delete a superseded decision; link to its replacement.
- Decision dates below are **recording dates** where exact original implementation timestamps are not available.
- Significant decisions should describe context, chosen approach, alternatives, consequences, security considerations, and follow-up work.

## Decision index

| ID | Decision | Status | Follow-up |
| --- | --- | --- | --- |
| ADR-001 | Build a small Python/FastAPI/HTTPX/Docker developer MVP | Implemented / reported | Revisit performance before production |
| ADR-002 | Use OPA/Rego as the runtime model-access authority; fail closed | Implemented / reported | Add trusted classification and policy integrity |
| ADR-003 | Use server-derived application identity and trusted fixed model routes | Implemented / reported | Normalize registries into PostgreSQL |
| ADR-004 | Commit governance evidence before inference; SQLite as an interim local store | Implemented / reported | Cut over safely to PostgreSQL in revised Day 29 |
| ADR-005 | Use gateway-controlled request IDs and privacy-minimized JSON policy logs | Implemented / reported | Link inference outcomes and retention rules |
| ADR-006 | Store reported policy versions and internal governance control references | Implemented / reported | Add artifact digests; tighten version contract |
| ADR-007 | Restore missing original roadmap scope and target 60 sessions, not 63 | **Proposed working revision** | Review revised Days 23–60 and record approval |
| ADR-008 | Use repository documentation and short weekly handoffs as project memory | **Proposed working method** | Connect GitHub and verify actual repository state |

---

## ADR-001 — Python-first, containerized development MVP

**Recorded:** 2026-10-29  
**Status:** Implemented / reported (Days 1–10)

**Context:** Development is primarily on a 16 GB Mac with a two-hour-per-session limit. The first goal is to prove the architecture and controls with minimal infrastructure.

**Decision:** Use FastAPI, Pydantic, HTTPX and pytest; run the gateway and deterministic mock model provider through Docker Compose; enforce Ruff and CI checks.

**Alternatives:** Full Kubernetes deployment, cloud-managed inference, larger microservice framework, or a real model provider from the outset.

**Consequences:** Faster iteration and deterministic tests; not a demonstration of production-scale throughput, high availability, or a real-model deployment. A real adapter is planned around Day 50.

**Verification:** Baseline gateway, Docker and test suites reported green.

## ADR-002 — OPA is authoritative; policy failures deny inference

**Recorded:** 2026-10-29  
**Status:** Implemented / reported (Days 15–18, validated Day 21)

**Context:** Static Python allowlists alone are insufficient as the eventual central authorization plane. Network failures and malformed responses must not accidentally authorize inference.

**Decision:** Evaluate an OPA/Rego default-deny rule before any provider call. Treat OPA denial as denial; treat timeouts, missing/invalid results and unsupported routes as errors that block inference. Do not silently fall back to permissive Python authorization.

**Alternatives:** Trust caller-supplied application/model claims; allow inference if OPA is unavailable; use Python allowlists as a permissive fallback.

**Consequences:** Inference availability depends on OPA health, which is intentional for the security MVP. Strict parsing and fail-closed tests are required. The static registry still supplies the trusted destination mapping.

**Future work:** Trusted data classification (revised Day 30), source/bundle integrity checks (revised Day 31), network confinement and threat model (Days 43–49).

## ADR-003 — Authenticate application identity and restrict provider routing

**Recorded:** 2026-10-29  
**Status:** Implemented / reported (Days 12–14)

**Context:** Caller-controlled identities and provider destinations would undermine centralized policy enforcement.

**Decision:** Verify a Bearer API key against a configured SHA-256 digest using constant-time comparison, derive the application identity from trusted server-side configuration, and route logical model names only through a static approved registry.

**Alternatives:** Accept an application ID from request headers, use unvalidated caller-provided URLs, or make the provider dynamically selectable.

**Consequences:** Small, testable trust boundaries. The initial one-key/configuration approach does not yet provide database-backed credential lifecycle management, revocation, or multi-tenant administration.

**Future work:** `api_credentials`, application and model tables (revised Day 25), revocation and spoofing tests (Day 44), network/egress controls (Day 47).

## ADR-004 — Persist authorization evidence before provider inference

**Recorded:** 2026-10-29  
**Status:** Implemented / reported with **SQLite as an interim implementation** (Days 20–21)

**Context:** Operational logs are not reliable durable governance evidence. The gateway should not execute an authorized inference if it cannot write the required decision record.

**Decision:** Write a structured SQLite `policy_evidence` record and commit it before sending the provider HTTPX request. If the evidence transaction fails, return HTTP 503 and do not invoke the provider. Record allows, denials and evaluation/route errors when persistence is available.

**Alternatives:** Best-effort logging, writing evidence asynchronously after inference, or immediate PostgreSQL introduction before proving the security requirement.

**Consequences:** A clear local fail-closed invariant proven with unit, integration and outage tests. However, single-node SQLite lacks the planned normalized governance schema and production-grade multi-instance behavior. A committed authorization record does not prove inference execution or exactly-once delivery.

**Future work:** Add PostgreSQL/SQLAlchemy (Day 23), Alembic (Day 24), relational decisions repository (Day 28), and **a tested evidence cutover (Day 29)**. Keep SQLite operational until PostgreSQL has passed the same fail-closed regression suite. Decide how historic records will be retained or migrated; do not quietly delete them.

## ADR-005 — Correlated, minimal operational policy logging

**Recorded:** 2026-10-29  
**Status:** Implemented / reported (Day 19)

**Context:** Debugging OPA failures and explaining security decisions requires stable correlation without exposing credentials, prompts or provider responses.

**Decision:** Generate server-controlled UUIDv4 request IDs, return them via `X-Request-ID`, and emit single-line structured JSON policy events with trusted application, logical model, outcome and reason. Do not trust caller-selected correlation IDs. Keep structured logs distinct from committed governance evidence.

**Alternatives:** Unstructured plaintext logs; user-supplied IDs; logging entire inbound/outbound AI requests; treating Docker logs as audit storage.

**Consequences:** Operational traceability and reduced sensitive-data exposure. Logs still need retention, access controls and review if deployed beyond development. A policy `allow` log does not imply inference success.

**Future work:** Separate inference outcomes (Day 33) and formal evidence export/retention rules (Days 36–42).

## ADR-006 — Record reported policy versions and internal control mappings

**Recorded:** 2026-10-29  
**Status:** Implemented / reported (Day 22)

**Context:** An access decision should be understandable in relation to the governing rule and the project's internal control model.

**Decision:** Add `model-access/v1` to OPA decision results; validate recognized values in the Python policy client; persist a reported policy version and JSON control ID list. Use internal IDs `AICP-AC-001`, `AICP-RT-001`, `AICP-FC-001` and `AICP-EV-001`. Upgrade the existing SQLite schema without falsely relabeling historic records; old rows retain `not_reported` and `[]`.

**Alternatives:** Infer policy versions from deployment dates; retroactively label all historic evidence v1; claim internal IDs correspond to external certified controls.

**Consequences:** Better explanatory evidence with a clear provenance limitation. The version is **self-reported**, not a cryptographic proof of loaded Rego source. The temporary Python `policy_version: ... | None` compatibility field permits old mocks; strict rejection of missing versions has not yet been implemented.

**Future work:** Relational control and policy tables (Day 27), digest verification (Day 31), stricter versioned deployment contracts, and reviewed external control mappings.

## ADR-007 — Reconcile original 63 numbered days to a 60-session delivery plan

**Recorded:** 2026-10-29  
**Status:** Proposed working revision; **not yet independently ratified through a repository commit**

**Context:** The original plan was advertised as 60 days but enumerated **63**. Early work stayed aligned through Day 17, then advanced OPA enforcement and evidence/logging while skipping trusted classification and the planned PostgreSQL stack. Continuing without a baseline would hide scope changes.

**Proposed decision:** Preserve the full original schedule in [`roadmap-60-days.md`](roadmap-60-days.md) and explicitly use its revised Days 23–60: PostgreSQL/SQLAlchemy (23), Alembic (24), core tables (25), review (26), governance tables (27), decisions repository (28), safe PostgreSQL cutover (29), trusted classification routing (30), policy digests (31), remaining Week 5 deliverables (32–35), original Weeks 6–8 (36–56), condensed release (57–60).

**Alternatives:** Continue ad hoc day planning; discard early work and restart the schedule; keep 63 sessions while describing it as 60.

**Consequences:** Better accountability while preserving substantial working code. Compressing release tasks increases pressure to keep documentation and security checks current throughout the project. The two-hour limit remains non-negotiable.

**Approval step:** Review the revised schedule and record the selected working roadmap in Git. Until approved, this is a documented recommendation, not an assumed completed migration of the plan.

## ADR-008 — GitHub-backed status and weekly conversation handoffs

**Recorded:** 2026-10-29  
**Status:** Proposed working method

**Context:** The original long chat is becoming difficult to audit, and historical suggestions may not match the latest committed code. Future sessions need reliable source-of-truth documents.

**Proposed decision:** Keep a canonical roadmap, progress checkpoint, architecture snapshot and decision log in `docs/`. Connect GitHub with minimal repository permissions; inspect actual source and CI at the beginning of a day; start a fresh conversation each development week with these documents as context.

**Alternatives:** Rely solely on ChatGPT conversation history; paste an entire repository in every new conversation; treat remembered code snippets as current source.

**Consequences:** Reduced context drift and fewer speculative full-file rewrites. Repository access and CI status must be **explicitly checked** when planning; a connection is not automatic continuous monitoring, and tests still need independent execution or CI evidence.

**Follow-up:** Add these four docs to the repository, connect GitHub if desired, confirm repository structure and CI, and update `progress.md` after every development session.

---

## Pending decisions to resolve as work progresses

| Target | Decision needed | Security or delivery concern |
| --- | --- | --- |
| Day 23 | SQLAlchemy sync vs async engine, connection lifecycle, and test database strategy | Avoid tying existing inference path to an unready DB |
| Day 24 | Migration ownership and safety policy | Ensure repeatable startup without implicit destructive upgrades |
| Day 25 | Credential hashing, credential identifiers, rotation and revocation design | Never store plaintext keys; avoid auth identity spoofing |
| Day 29 | Evidence migration/cutover approach and historic SQLite record retention | Preserve commit-before-inference and prevent evidence loss |
| Day 30 | Trusted source of data classification and downgrade handling | No untrusted request field may lower classification |
| Day 31 | Artifact packaging, trusted digest source, OPA source inspection limits | Self-reported version is not proof of deployed policy |
| Days 36–42 | Canonical serialization, checkpoint trust, export integrity | Hash chains without trusted checkpoints do not prove immutability |
| Days 43–49 | OPA management API and provider egress boundary | Limit policy modification and unauthorized outbound requests |
| Days 57–60 | Release acceptance threshold and preview fallback | Do not claim production readiness solely because CI passes |

## How to add a new entry

```markdown
## ADR-009 — Short, action-oriented decision title

**Recorded:** YYYY-MM-DD  
**Status:** Proposed | Accepted | Implemented / reported | Superseded

**Context:** What problem requires a decision?

**Decision:** What specific design or workflow did we choose?

**Alternatives:** What other realistic options were considered?

**Consequences:** Benefits, risks, and tradeoffs.

**Security / operations:** Trust boundary, failure behavior, data or deployment implications.

**Follow-up:** Required tests, migrations, documentation, or next milestones.
```
