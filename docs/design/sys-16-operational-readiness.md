# SYS-16 Operational readiness and deployment boundary

Design note only: nothing here is built. It keeps the item's dependencies and acceptance criteria so the claim
Rung makes today stays honest (`docs/roadmap.md`).

## Problem

A verified integration milestone says the declared journeys pass on the code as it is now. It says nothing about
whether that code can be deployed, configured, monitored or rolled back, or whether anyone authorised a release.
Reusing words like Released or Done for a green milestone invites that confusion (the outside assessment's R and
U findings on vocabulary).

## Boundary

In scope: a separate readiness record per candidate, its obligations and who may grant it. Out of scope:
running deployments, infrastructure provisioning, incident management.

## Proposed model

- An **operational readiness** record attaches to a verified milestone candidate (its code basis and version).
- Its obligations are declared per project: deployability (a build or package step and its artifact digest),
  configuration (required settings present for a named environment), monitoring (named signals exist), rollback
  (a tested way back to the previous artifact) and post-deployment checks (journeys to rerun against the deployed
  environment).
- Each obligation is a check or a required human review, recorded with the environment it ran against
  (SYS-10). A missing obligation keeps the candidate Not operationally ready.
- Granting readiness is an approver action (SYS-15 roles) naming the candidate; a new candidate needs its own.
- Rung records post-deployment check results when a person runs them; it never deploys.

## Dependencies

SYS-01 (milestones), SYS-10 (environments), SYS-12 (report), SYS-15 (who may grant readiness), declared
operational requirements from the project.

## Acceptance criteria

- A verified milestone with any readiness obligation unmet shows Verified for integration and Not operationally
  ready, both visible, neither implying the other.
- A new candidate after readiness was granted needs its own readiness.
- The system report separates software verification from operational readiness.

## Not claimed until built

Rung must not say a milestone is released, deployable or production ready. A green integration milestone is
never permission to deploy.
