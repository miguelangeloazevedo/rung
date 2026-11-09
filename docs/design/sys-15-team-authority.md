# SYS-15 Team authority and stronger verifier isolation

Design note only: nothing here is built. It keeps the item's dependencies and acceptance criteria so the claim
Rung makes today stays honest (`docs/roadmap.md`).

## Problem

Rung's approval is a workflow boundary, not an authenticated person: the REST seam under the pane acts for
whoever can reach the local dashboard, and agents reach the engine only through four tools that cannot approve.
A worker runs as the same operating-system user as the person, so it can read the store, edit test files and
start processes. Protected test files (Round 22) make a changed check count for nothing, but a determined local
worker with the same file access could still edit the store itself. A different Hermes profile name is not a
different authority.

## Boundary

In scope: who may approve what, and a verifier the worker cannot alter. Out of scope: hosted multi-tenant
service, single sign-on integration details, billing.

## Proposed model

- **Roles**: author (proposes), approver (approves text, tests, manual results, files), operator (starts and
  stops work), verifier (runs checks). A person may hold several roles; an agent profile only author and
  operator.
- **Authority**: approvals are signed records (an approver key held outside the worker's reach, for example the
  OS keychain or a hardware key), verified by the engine on read. An unsigned or wrongly signed approval counts
  as not approved.
- **Verifier boundary**: checks run in a separate process under a different OS user or a container with the
  project mounted read-only, from a copy of the approved test assets taken at approval time. The worker's
  workspace (SYS-05) is never the verifier's input except through integration.
- **Store integrity**: an append-only, hash-chained execution log, so a later edit to an earlier result is
  detected.
- **Threat model first**: list worker capabilities (file, process, network, store access) and for each the
  control that removes it, before any code.

## Dependencies

B20 (team identity and sharing), a written threat model, SYS-05 (isolated workspaces), Round 22 protected test
assets.

## Acceptance criteria

- A worker with the same file access as before cannot produce an approval the engine accepts.
- A worker that edits the store directly is detected on the next read (the chain breaks) and every affected
  result counts as Could not verify.
- Checks run from the approved copy of test assets; editing the project's test files changes nothing the
  verifier reads until a person approves the change.
- The threat model lists each worker capability and its control, with a test per control.

## Not claimed until built

Rung must not claim authenticated approval, tamper-proof evidence or protection against a malicious local
worker. Today it claims: agents cannot approve through Rung's tools, and a changed protected test file makes its
result count for nothing.
