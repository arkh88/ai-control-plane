# AI Control Plane — MVP Scope and Acceptance Criteria

**Document version:** 0.1  
**Status:** Proposed baseline 
**Release target:** v0.1.0  
**Architecture reference:** [`architecture.md`](architecture.md)  
**Implementation:** Python, FastAPI, OPA/Rego, PostgreSQL, pytest, Docker Compose

## 1. Purpose

### Problem

Teams deploying AI applications need to govern which applications can call which models, under what conditions, and with what evidence. Written policies alone cannot establish that each inference request was authorized and governed at runtime.

### MVP solution

Provide a self-hosted **AI security gateway** that authenticates applications, evaluates versioned authorization rules before inference, routes permitted requests only to registered model providers, and creates durable, control-linked evidence of each policy decision.

### Primary user

An AI platform engineer or security engineer operating internal AI applications and needing demonstrable model-access controls and decision history.

### Value proposition

> Enforce an AI access policy at runtime and show which governance control was applied to each decision.

## 2. Release goal and definition of done

**Single end-to-end use case:** An authenticated application sends a non-streaming chat-completion request to the gateway. The gateway evaluates an OPA policy, records the decision and associated control/policy version, and either forwards to an approved model or rejects the request. An administrator can later retrieve and export the evidence.

MVP v0.1 is done when:

1. One-command local deployment runs the API, OPA, PostgreSQL, and a deterministic mock inference provider.
2. Authorized requests are forwarded **only after** the relevant authorization evidence has been durably committed.
3. Denied, invalid, or failed-authorization requests are **never** forwarded to the model provider.
4. Policy decisions reference immutable policy-version metadata and governance control IDs.
5. The system exposes administrator-protected decision lookup and export, with integrity verification.
6. Automated tests cover the functional paths and fail-closed security properties in Section 7.
7. A clean checkout can reproduce allow, deny, and evidence demonstrations without a GPU.

## 3. Scope boundaries

### In scope (v0.1)

| Area | Capability | Notes |
|---|---|---|
| Inference API | `POST /v1/chat/completions` | Compatible subset; non-streaming, text messages only |
| Identity | Application API keys | Validated server-side; associate each key with one application |
| Authorization | OPA policy decisions | Default-deny; explicit application/model allowlists |
| Data classification | Trusted classification inputs | Prevent untrusted classification downgrade; no automatic content classification |
| Routing | Registered model endpoints only | Mock provider first; Ollama integration as follow-up |
| Governance | Policy versions and control mapping | Track approved policy digest, decision reason, related control IDs |
| Evidence | PostgreSQL decision and outcome events | Metadata-only by default; authorization committed before provider call |
| Evidence export | JSONL export and integrity checks | Deterministic serialization, hash chain, offline verification |
| Operations | Docker Compose deployment | Local development with environment-based configuration |
| Quality | Tests, docs, basic CI | Integration and negative-path security tests |

### Explicitly out of scope (v0.1)

- Web administration dashboard, billing, and organization-wide user management.
- Kubernetes, service mesh, multi-region operation, or high-availability guarantees.
- Multi-tenancy or enterprise SSO / federated IAM.
- Streaming completions, multimodal inputs, embeddings, or fine-tuning.
- Agent tool-call interception, human-in-the-loop approvals, or sandboxed code execution.
- Automatic sensitive-data discovery, prompt-injection prevention, or AI content safety guarantees.
- Automatic certification or claims of compliance with the EU AI Act, ISO/IEC 42001, or any other standard.
- Control over applications that can bypass the gateway and call a provider directly.

## 4. Users, actors, and assumptions

| Actor | Responsibility | Trust assumption |
|---|---|---|
| Application client | Sends chat-completion requests | Untrusted until authenticated |
| Gateway | Authenticates, validates, authorizes, persists evidence, routes | Trusted runtime enforcement point |
| OPA | Evaluates deployed Rego policy | Trusted only via configured internal endpoint and verified policy bundle |
| PostgreSQL | Stores configuration and evidence | Availability and integrity are security dependencies; DB admin can still alter data |
| Model provider | Generates inference output | Output is untrusted; provider must not administer policies |
| Administrator | Registers applications/models and inspects evidence | Separate privileged identity; authenticated and authorized |

**Environment assumptions:** Single-operator lab, one gateway instance, single ordered evidence writer, private Docker network, no public internet exposure, no dependency on GPU acceleration for initial tests.

## 5. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | Authenticate the calling application using a revocable API key; derive application identity from validated credentials. | Must |
| FR-002 | Accept validated non-streaming, text-only chat-completion requests. | Must |
| FR-003 | Evaluate authorization through OPA with trusted identity, model, environment, and classification input. | Must |
| FR-004 | Reject unauthorized requests before contacting a model provider. | Must |
| FR-005 | Route allowed requests only to configured, registered provider endpoints. | Must |
| FR-006 | Commit an authorization decision event durably before any allowed inference begins. | Must |
| FR-007 | Attach a verified policy version/digest and governance control references to each decision. | Must |
| FR-008 | Provide authenticated administrator access to filter and export redacted decision evidence. | Must |
| FR-009 | Record provider outcome separately as success, failure, or unknown; do not invent success after timeout. | Must |
| FR-010 | Provide a deterministic mock provider and runnable end-to-end demonstration. | Must |
| FR-011 | Support Ollama as a second provider adapter. | Should |
| FR-012 | Provide streaming, frontend, and agent/tool interception. | Later |

### Proposed API surface

| Method | Path | Intended behavior |
|---|---|---|
| `GET` | `/health/live` | Process-liveness response (already implemented on Day 2) |
| `GET` | `/health/ready` | Dependency readiness; must not be mistaken for authorization |
| `POST` | `/v1/chat/completions` | Authenticated inference through enforcement path |
| `GET` | `/v1/models` | List available registered models with appropriate access control |
| `GET` | `/v1/controls` | List governance control metadata (administrator) |
| `GET` | `/v1/decisions` | Filter decisions (administrator) |
| `GET` | `/v1/decisions/{id}` | Retrieve one decision (administrator) |
| `GET` | `/v1/evidence/export` | Download redacted JSONL evidence (administrator) |

**Error contract (initial):** `400` malformed/untrusted classification, `401` invalid credential, `403` denied policy, `404` unknown model, `429` rate limit if configured, `502/503` provider unavailable, `503` policy/evidence dependencies unavailable. An OPA outage must **not** result in an allow.

## 6. Initial governance controls

| Control ID | Name | Objective | Evidence |
|---|---|---|---|
| `CTRL-001` | Authorized model access | Only approved authenticated applications use registered models. | Identity reference, requested model, allow/deny, rule ID |
| `CTRL-002` | Classification-aware routing | Confidential workloads only use explicitly approved private routes. | Trusted classification, model route, decision and reason |
| `CTRL-003` | Decision accountability | Every authorized inference has a durable, attributable authorization record before execution. | Decision ID, timestamp, policy version/digest, referenced controls, commit status |

**Policy version rule:** The version recorded with a decision must be the version actually evaluated, not merely the newest published version. Store or retain the associated policy artifact/digest for traceability.

## 7. Acceptance criteria and test scenarios

Test with a mock provider that counts incoming calls. Start each test with a known count and assert the expected delta.

| Test ID | Given / when | Expected result |
|---|---|---|
| AC-001 — Allow | Valid app key + authorized model + authorized classification | Allow; committed decision record; exactly one provider call; response returned |
| AC-002 — Deny | Valid app key but unauthorized model | `403`; denial evidence committed when store available; zero provider calls |
| AC-003 — Bad key | Missing, expired, revoked, or invalid credential | `401`; zero provider calls; no impersonation of another application |
| AC-004 — OPA outage | Policy engine times out or is unreachable | `503`; zero provider calls; fail closed |
| AC-005 — Bad OPA response | Missing or malformed decision result | `503`; zero provider calls; fail closed |
| AC-006 — Evidence failure | Allowed by OPA but required decision commit fails | `503`; zero provider calls |
| AC-007 — Classification downgrade | Caller claims a classification below the trusted workload classification | Reject or evaluate at trusted higher classification; no unauthorized provider calls |
| AC-008 — Unknown route | Request names an unregistered model or attempts custom provider URL | `404` / `400`; zero provider calls; no arbitrary outbound connection |
| AC-009 — Provider timeout | Request forwarded, but provider response status uncertain | Outcome `unknown`; do not claim success or auto-retry non-idempotent work |
| AC-010 — Evidence integrity | Export is modified, reordered, or truncated relative to a trusted checkpoint | Offline verifier detects discrepancy |
| AC-011 — Governance link | Authorized/denied request has mapped control ID and policy version | Evidence query links the event to correct policy/control metadata |
| AC-012 — Privacy | Requests contain sample sensitive text | Prompts, completions, API keys absent from default logs and evidence exports |
| AC-013 — Reproducibility | Fresh checkout and documented setup | `docker compose up --build` starts required services; demo works |

### Required release demonstration

1. **Allow:** `finance-assistant` calls `local-small`; policy permits, evidence commits, provider is called.
2. **Deny:** An unauthorized model or confidential external route is requested; gateway returns `403`, provider remains untouched.
3. **Prove:** An administrator filters decisions by application, exports events and verifies integrity; each decision points to a governance control and evaluated policy version.

## 8. Non-functional and security requirements

- **SEC-001 — No bypass:** Model service is private and reachable from the gateway, not directly from test application containers. This is a *deployment* control; an external application with its own provider credentials cannot be governed by this gateway.
- **SEC-002 — Fail closed:** Authentication failure, OPA unavailability, invalid policy response, or inability to commit mandatory allow evidence prevents inference.
- **SEC-003 — Evidence before execution:** Commit decision evidence before calling providers, and record inference outcomes as separate events.
- **SEC-004 — Trusted attributes:** Application identity comes from validated credentials; classification uses trusted configuration or an explicit trusted attestation, not unchecked caller headers.
- **SEC-005 — Privacy by default:** Do not persist raw prompts/completions or plaintext credentials; redact errors, headers, and telemetry.
- **SEC-006 — Protected administration:** Admin APIs use a separate authorization check and are not exposed to inference API keys.
- **SEC-007 — Fixed routing:** Only configured destinations can be reached; prohibit user-supplied arbitrary provider URLs.
- **SEC-008 — Policy traceability:** A decision retains the exact evaluated policy bundle identifier and verifiable digest.
- **SEC-009 — Least privilege:** Separate database roles, internal networking, and restricted service configuration.
- **SEC-010 — Evidence integrity limitations:** Hash chaining detects changes against a **trusted external checkpoint**, but database-local hashes alone do not prevent rewriting by a privileged database operator.

**Operational guardrails:** Bound request sizes, configure connection and request timeouts, avoid logging sensitive bodies, and run development services on loopback or private lab networks.

## 9. Risks, assumptions, and mitigation

| Risk / constraint | Mitigation |
|---|---|
| Development on a 16 GB Mac | Run a mock provider and modest Compose services; use a small optional Ollama model; no GPU purchase needed |
| Limited time (maximum two hours/day) | One small deliverable per session; keep scope fixed; dedicate review/buffer days |
| Policy mistakes | Rego unit tests, deny-by-default rules, explicit negative tests |
| Misclassified sensitive data | Only accept trusted classification metadata; document that v0.1 cannot infer sensitivity reliably |
| Evidence leaks private content | Define metadata allowlist; test redaction and log behavior |
| Evidence store outage | Mandatory allow events must commit before forwarding or request fails closed |
| Hash chain appears stronger than it is | Document verification trust assumptions; independent signed checkpoints are future work |
| Provider bypass | Segmented network and fixed routes within lab; disclose limitations outside managed environment |
| Scope creep | Defer UI, multi-tenancy, Kubernetes, streaming, and agent/tool controls |

## 10. Implementation and milestone alignment

1. **Foundation:** FastAPI app and tests, Docker Compose, deterministic mock provider.
2. **Runtime security:** API-key auth, model routing, OPA policies, deny/allow tests.
3. **Governance:** PostgreSQL schema, policy/control mapping, pre-inference decision evidence.
4. **Assurance:** Outcome events, redacted export, integrity verification, security regression tests.
5. **Release:** Ollama demo (if practical), documentation, reproducible setup, security review, release notes.

Release is **blocked** by failing security invariants, a missing evidence commit gate, known high-severity issues in shipped configuration, or unreproducible installation. Cosmetic UI polish is not a blocker.

## 11. Decisions and unresolved questions

| Decision | v0.1 choice |
|---|---|
| Application language | Python 3.12+ with FastAPI |
| Policy engine | Separate OPA container; Rego |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Provider | Deterministic mock first, Ollama as optional real-model demo |
| Deployment | Docker Compose on Mac / Linux; no production exposure |
| Evidence ordering | One logical ordered writer for the initial chain |
| Classification authority | Server-configured app/workload classification; caller labels cannot reduce it |

**Open design questions (do not block Day 4):** How are policy bundle activations approved? Which administrator identity mechanism is used for the initial demo? Where should an independently trusted evidence checkpoint be stored? Record a decision before implementing each feature.

## 12. Day 4 sign-off checklist

- [ ] Primary user, problem, and value proposition are clearly defined.
- [ ] In-scope and deferred functionality are unambiguous.
- [ ] Functional and security requirements have IDs.
- [ ] Three governance controls are defined.
- [ ] Allow, deny, and fail-closed behavior are testable.
- [ ] Evidence guarantees and limitations are stated accurately.
- [ ] The document has been reviewed against `architecture.md`.
- [ ] The file is committed to the repository.

**Suggested commit message:** `Define MVP scope and acceptance criteria`
