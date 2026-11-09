# SYS-14 Larger systems and several repositories

Design note only: nothing here is built. It keeps the item's dependencies and acceptance criteria so the claim
Rung makes today stays honest (`docs/roadmap.md`).

## Problem

A real system is often several services in several repositories, released at different versions. Rung today
judges one project folder: its code basis is the content of that folder, and a milestone's checks run there.
Opening several project folders in Rung does not make them one system: nothing records which version of one
service another was checked against.

## Boundary

In scope: several Rung projects that together form one declared system, each still verified on its own code.
Out of scope: building, deploying or hosting the services; package registries; cross-machine execution.

## Proposed model

- A **system** names member projects and, per member, the artifact it provides to the others (a package
  version, a container digest, a commit, or a folder content digest from `evidence.basis`).
- A **system milestone** is a milestone whose scope names member projects instead of specifications. Its checks
  run with each member at a recorded artifact version, assembled by a declared setup command (SYS-10).
- Its evidence is the tuple of member artifact versions plus the check result. A new artifact version from any
  member makes the system milestone Out of date, naming the member (SYS-11 impact over members).
- Interface contracts (SYS-06) between members are owned by the producing member and versioned there; consumers
  pin the version they were checked against.
- Failure recovery: a member that cannot provide its declared artifact makes the run Could not verify, never a
  pass against a stale artifact.

## Dependencies

SYS-02 (contracts), SYS-03 (dependencies between members), SYS-05 (isolated assembly), SYS-06, SYS-10 (declared
setup), SYS-11 (impact), SYS-12 (report).

## Acceptance criteria

- A representative two-service example (a producer and a consumer in separate folders) records the artifact
  version of each member with every system check.
- Changing the producer's artifact makes the consumer-side system milestone Out of date, named.
- A member that cannot provide its artifact gives Could not verify with the member and reason.
- The system report lists every member and version the acceptance applies to.

## Not claimed until built

Rung must not say it supports multi-repository systems, microservices or monorepos with independent release
trains until this is built and the acceptance above passes. Several open projects are several projects.
