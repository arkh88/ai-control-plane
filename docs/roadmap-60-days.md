# AI Governance & Security Control Plane — Roadmap

**Project goal:** Build and publish an understandable, reproducible, open-source AI security gateway that enforces model-access policies, records control-linked governance evidence, and demonstrates governed inference.

**Time constraint:** Up to **2 hours per development session**. The original schedule was dated October 22–December 23, 2026, and contained **63 numbered days**, despite being described as a 60-day plan. The revised release plan targets **60 development sessions**. Calendar dates are planning references, not a requirement to slow down or speed up.

**Current checkpoint (November 6, 2026):** Day 30 completed. See [`progress.md`](progress.md) for the latest status.

> **Superseded for sessions 31–60:** the active schedule is now [`production-30-day-plan.md`](production-30-day-plan.md) (ADR-011). The revised Days 31–60 below are retained for comparison only.

## Roadmap governance

1. **Original baseline:** The full original 63-day task list appears below and must remain available for comparison.
2. **Working schedule:** Use the revised Days 23–60 section for upcoming tasks, while preserving original feature coverage wherever possible.
3. **Change control:** Record significant deviations in [`decisions.md`](decisions.md); do not silently change a day's objective.
4. **Evidence of completion:** A day is complete only when its code or documentation exists, applicable tests pass, relevant local/Docker checks are completed, and CI is green (or a blocker is explicitly recorded).
5. **Order of work:** Inspect actual repository files before editing. Prefer incremental changes and never weaken a working fail-closed security guarantee to make tests pass.
6. **Production claims:** Distinguish a local prototype, a tested MVP behavior, and a production-grade guarantee.

## Status against the original roadmap

| Original phase | Status at Day 22 | Remaining gaps / notes |
| --- | --- | --- |
| Week 1 — Project foundation, Days 1–7 | Completed | Verify documentation reflects deployed configuration. |
| Week 2 — AI gateway, Days 8–14 | Completed | Mock provider, auth, fixed model registry, tests. |
| Week 3 — Runtime security, Days 15–21 | Core milestone completed | **Trusted data-classification routing from original Day 19 is not implemented.** OPA enforcement was implemented on actual Day 18, earlier than original Day 20. |
| Week 4 — Governance data model, Days 22–28 | Partially implemented ahead of schedule | **PostgreSQL, SQLAlchemy, Alembic, and the normalized governance tables have not yet been implemented.** SQLite evidence is an interim local prototype. |
| Week 5 — Unified governance evidence, Days 29–35 | Partially implemented early | Internal controls and control mappings were implemented on actual Day 22; source digest verification and inference outcomes remain. |
| Weeks 6–9 — Evidence, security, real AI, release | Not yet started as complete phases | Some preliminary fail-closed regression tests have been completed early; do not count the later milestones as complete without their own acceptance checks. |

## Revised working schedule (Days 23–60)

**Why this revision exists:** The work completed through Day 22 drifted from the original order. The next priority is to close missing database and classification foundations before further policy-integrity work. Previously completed features should be reused, not rebuilt.

### Days 23–28 — Governance database foundation

| Day | Task | Acceptance focus |
| --- | --- | --- |
| **23** | Add **PostgreSQL** to Docker Compose and **SQLAlchemy** connectivity in Python. | Database is isolated and healthy; connection tests pass; the existing SQLite inference/evidence path remains untouched. |
| **24** | Introduce **Alembic** and baseline migrations. | Migrations apply to a fresh database and can be repeated safely. |
| **25** | Implement `applications`, `api_credentials`, and `models` tables. | Relationships and constraints tested; no plaintext API keys stored. |
| **26** | Light review: migrations, seeds, and database cleanup. | Repeatable fresh-start tests; no unreviewed destructive migration. |
| **27** | Implement `controls`, `policy_versions`, and control mappings. | Internal control IDs and reported policy versions represented relationally. |
| **28** | Implement `decisions` table and repository operations. | Transactional inserts, readback, duplicate protection, and failure handling tested. |

**Milestone:** A normalized governance schema exists without breaking the running gateway.

### Days 29–35 — Complete the governance MVP

| Day | Task | Acceptance focus |
| --- | --- | --- |
| **29** | Cut over evidence persistence from SQLite to PostgreSQL through a tested repository abstraction. | **Commit before inference** maintained; DB outage returns 503 and reaches zero provider calls. Retain SQLite data safely; do not silently discard it. |
| **30** | Add trusted **data-classification routing** and Rego enforcement (deferred original Day 19). | Classification comes from a trusted server-side source, not caller claims; downgrade attempts denied. |
| **31** | Verify versioned policy artifact/bundle **SHA-256 digests** (original Week 5 scope; planned Day 23 work deferred). | Approved source/bundle and deployed OPA artifact can be compared; limitations documented. |
| **32** | Light review: stored evidence, sensitive-field minimization, and migration cleanup. | No prompts, raw responses, or API keys in governance records. |
| **33** | Add inference outcome events: success, failure, and unknown. | Authorization evidence and inference execution outcome remain distinct. |
| **34** | Administrator-only decision lookup endpoints. | Explicit administrator authorization, pagination/limits, and negative tests. |
| **35** | Create a control-linked denial demo. | Demonstrate denial, persisted evidence, policy reference, control reference, and correlation ID. |

**Milestone:** An inference request is governed by trusted authorization and classification controls and produces linked, durable evidence in PostgreSQL.

### Days 36–42 — Evidence integrity and export (retained from original)

| Day | Task |
| --- | --- |
| 36 | Define an evidence event JSON schema and canonical serialization. |
| 37 | Implement SHA-256 hashing for evidence records. |
| 38 | Add previous-hash references and ordered insertion. |
| 39 | Light review: document integrity guarantees and limitations. |
| 40 | Implement JSONL evidence export. |
| 41 | Build an offline evidence verification command. |
| 42 | Test record tampering, deletion, ordering errors, and valid exports. |

**Milestone:** Exportable evidence with changes detectable relative to a separately trusted chain checkpoint; no unqualified immutability claim.

### Days 43–49 — Security engineering (retained from original)

| Day | Task |
| --- | --- |
| 43 | Write a threat model identifying assets, attackers, and trust boundaries. |
| 44 | Test invalid credentials, revoked keys, and application identity spoofing. |
| 45 | Test classification downgrade attempts and unauthorized model access. |
| 46 | Light review: prioritize findings and update the threat model. |
| 47 | Restrict service networking, provider egress, and management interfaces. |
| 48 | Test OPA failures, database failures, timeouts, and request-size limits. |
| 49 | Add security regression tests to CI and address critical findings. |

**Milestone:** Demonstrated, automated protection of important trust boundaries and failure conditions.

### Days 50–56 — Real AI integration and usability (retained from original)

| Day | Task |
| --- | --- |
| 50 | Connect an Ollama provider adapter to the gateway. |
| 51 | Test a small local model or a remote test provider if the Mac cannot support it comfortably. |
| 52 | Demonstrate allowed and denied real inference end-to-end. |
| 53 | Light review: collect demo results and remaining defects. |
| 54 | Add `/v1/models`, `/v1/controls`, and policy metadata lookup endpoints. |
| 55 | Improve README, API documentation, and configuration examples. |
| 56 | Create a reproducible demo script for authorization and evidence export. |

**Milestone:** Governed inference with a real provider and a repeatable demonstration.

### Days 57–60 — Condensed open-source release

The original plan had Days **57–63**. To honor the 60-session commitment, consolidate those activities without weakening release criteria.

| Day | Task |
| --- | --- |
| **57** | Finalize architecture and threat-model documentation; add/review `LICENSE`, `SECURITY.md`, and `CONTRIBUTING.md`. |
| **58** | Install from a fresh checkout; fix critical setup blockers; verify CI. |
| **59** | Run final security regression tests; produce demo, evidence export, release notes, and an explicit known-limitations list. |
| **60** | Release `v0.1.0` **only if acceptance criteria pass**; otherwise publish a clearly labeled preview release and document blockers. |

**Final milestone:** An open-source AI security gateway with enforced policies, control-linked evidence, audit export, reproducible tests, and an honest security limitations statement.

## Daily handoff checklist

Add or update this block in [`progress.md`](progress.md) after each session:

```text
Day:
Goal:
Implemented:
Files changed:
Tests passing:
Docker verification:
CI status:
Known limitations / blockers:
Next task:
```

---

## Original 63-day baseline (preserved for comparison)

The following records the original day-by-day tasks supplied by the project owner. These are **not** silently replaced by the revised working schedule above.

### Original Week 1 — Project foundation (October 22–28)

| Day | Date | Task (up to 2 hours) |
| --- | --- | --- |
| 1 | Thu Oct 22 | Create Git repository, Python environment, README, and project folders. |
| 2 | Fri Oct 23 | Initialize FastAPI application with `/health/live`. |
| 3 | Sat Oct 24 | Define MVP scope, system components, and first architecture diagram. |
| 4 | Sun Oct 25 | Light review: clean up README and record open questions. |
| 5 | Mon Oct 26 | Add pytest and first automated API tests. |
| 6 | Tue Oct 27 | Dockerize FastAPI; verify it runs locally. |
| 7 | Wed Oct 28 | Add Docker Compose, Ruff, and a basic GitHub Actions test workflow. |

**Original milestone:** Run the Python API from Docker and pass automated tests.

### Original Week 2 — AI gateway (October 29–November 4)

| Day | Date | Task |
| --- | --- | --- |
| 8 | Thu Oct 29 | Define `/v1/chat/completions` request and response models with Pydantic. |
| 9 | Fri Oct 30 | Build a deterministic mock AI model provider. |
| 10 | Sat Oct 31 | Implement gateway request forwarding to the mock provider. |
| 11 | Sun Nov 1 | Light review: test requests with curl and document behavior. |
| 12 | Mon Nov 2 | Add application API-key authentication. |
| 13 | Tue Nov 3 | Add model registry and fixed, approved provider routing. |
| 14 | Wed Nov 4 | Test valid keys, invalid keys, and unknown models. |

**Original milestone:** An authenticated request successfully passes through the gateway and reaches the mock AI model.

### Original Week 3 — Runtime security enforcement (November 5–11)

| Day | Date | Task |
| --- | --- | --- |
| 15 | Thu Nov 5 | Add OPA to Docker Compose and verify its health endpoint. |
| 16 | Fri Nov 6 | Write your first Rego application/model allowlist policy. |
| 17 | Sat Nov 7 | Implement Python's asynchronous OPA policy client. |
| 18 | Sun Nov 8 | Light review: write and test sample allow/deny policy inputs. |
| 19 | Mon Nov 9 | Add trusted data-classification routing rules. |
| 20 | Tue Nov 10 | Integrate OPA decisions into FastAPI's request flow. |
| 21 | Wed Nov 11 | Test fail-closed behavior and confirm denied requests never reach the provider. |

**Original milestone:** An unauthorized application or model request is denied before inference.

### Original Week 4 — Governance data model (November 12–18)

| Day | Date | Task |
| --- | --- | --- |
| 22 | Thu Nov 12 | Add PostgreSQL and SQLAlchemy. |
| 23 | Fri Nov 13 | Configure Alembic database migrations. |
| 24 | Sat Nov 14 | Implement `applications`, `api_credentials`, and `models` tables. |
| 25 | Sun Nov 15 | Light review: migration tests and database cleanup. |
| 26 | Mon Nov 16 | Implement `controls`, `policy_versions`, and control mappings. |
| 27 | Tue Nov 17 | Implement the `decisions` table and repository operations. |
| 28 | Wed Nov 18 | Persist decisions before forwarding approved requests; test database failure behavior. |

**Original milestone:** Every accepted inference request has a durably committed authorization record before it reaches the model.

### Original Week 5 — Unified governance evidence (November 19–25)

| Day | Date | Task |
| --- | --- | --- |
| 29 | Thu Nov 19 | Define governance control identifiers, objectives, and metadata. |
| 30 | Fri Nov 20 | Map OPA policy rules to governance controls. |
| 31 | Sat Nov 21 | Track policy bundle versions and SHA-256 digests. |
| 32 | Sun Nov 22 | Light review: inspect stored evidence and remove sensitive fields. |
| 33 | Mon Nov 23 | Add inference outcome events: success, failure, and unknown. |
| 34 | Tue Nov 24 | Implement administrator-only decision lookup endpoints. |
| 35 | Wed Nov 25 | Build a demo showing a denied request and its control-linked evidence. |

**Original milestone:** Show which policy and governance control authorized or denied an AI request.

### Original Week 6 — Evidence integrity and audit export (November 26–December 2)

| Day | Date | Task |
| --- | --- | --- |
| 36 | Thu Nov 26 | Define an evidence event JSON schema and canonical serialization. |
| 37 | Fri Nov 27 | Implement SHA-256 hashing for evidence records. |
| 38 | Sat Nov 28 | Add previous-hash references and ordered insertion. |
| 39 | Sun Nov 29 | Light review: document integrity guarantees and limitations. |
| 40 | Mon Nov 30 | Implement JSONL evidence export. |
| 41 | Tue Dec 1 | Build an offline evidence verification command. |
| 42 | Wed Dec 2 | Test record tampering, deletion, ordering errors, and valid exports. |

**Original milestone:** Export evidence and detect changes checked against a previously trusted chain checkpoint.

### Original Week 7 — Security engineering (December 3–9)

| Day | Date | Task |
| --- | --- | --- |
| 43 | Thu Dec 3 | Write a threat model identifying assets, attackers, and trust boundaries. |
| 44 | Fri Dec 4 | Test invalid credentials, revoked keys, and application identity spoofing. |
| 45 | Sat Dec 5 | Test classification downgrade attempts and unauthorized model access. |
| 46 | Sun Dec 6 | Light review: prioritize findings and update the threat model. |
| 47 | Mon Dec 7 | Restrict service networking, provider egress, and management interfaces. |
| 48 | Tue Dec 8 | Test OPA failures, database failures, timeouts, and request-size limits. |
| 49 | Wed Dec 9 | Add security regression tests to CI and address critical findings. |

**Original milestone:** Automated evidence of key access and failure controls.

### Original Week 8 — Real AI integration and usability (December 10–16)

| Day | Date | Task |
| --- | --- | --- |
| 50 | Thu Dec 10 | Connect an Ollama provider adapter to the gateway. |
| 51 | Fri Dec 11 | Test a small local model, or use a remote test provider if the Mac struggles. |
| 52 | Sat Dec 12 | Demonstrate allowed inference and denied inference end-to-end. |
| 53 | Sun Dec 13 | Light review: collect demo results and remaining defects. |
| 54 | Mon Dec 14 | Add `/v1/models`, `/v1/controls`, and policy metadata lookup endpoints. |
| 55 | Tue Dec 15 | Improve README, API documentation, and configuration examples. |
| 56 | Wed Dec 16 | Create a reproducible demo script showing authorization and evidence export. |

**Original milestone:** Govern real inference and produce matching audit evidence.

### Original Week 9 — Open-source release (December 17–23)

| Day | Date | Task |
| --- | --- | --- |
| 57 | Thu Dec 17 | Publish architecture and threat-model documentation. |
| 58 | Fri Dec 18 | Add `LICENSE`, `SECURITY.md`, and `CONTRIBUTING.md`. |
| 59 | Sat Dec 19 | Test the installation from a fresh checkout. |
| 60 | Sun Dec 20 | Light review: identify blockers and narrow scope if needed. |
| 61 | Mon Dec 21 | Fix release-blocking bugs and verify CI. |
| 62 | Tue Dec 22 | Run final security tests, produce a demo, and write release notes. |
| 63 | Wed Dec 23 | Tag and publish `v0.1.0` if acceptance tests pass; otherwise publish an explicitly labeled preview release. |

**Original milestone:** Publish a reproducible open-source AI security gateway with policy enforcement, control-linked evidence, audit history, and security tests.
