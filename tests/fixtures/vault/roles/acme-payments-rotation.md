---
type: role
company: Acme Corp
title: Software Engineer
team: Payments Platform
programme: acme-grad
start: 2025-03
end: 2025-09
skills: [csharp, dotnet-core, postgresql, testcontainers, ci-cd]
---
## Context
The payments platform handling order settlement across the group's storefronts.

## Achievements
### Settlement-service refactor
Collapsed several internal microservices that added unnecessary IPC and DB
round-trips into a single settlement service.
**Impact:** the codebase's first integration tests (Testcontainers + Postgres
in Docker), built as a reusable pattern.
**Lessons:** time pure refactors to coincide with a UAT window.

### Partner-bank onboarding automation
Extended the settlement module to onboard a new partner bank via an automated
reconciliation job.
**Impact:** ~500 txns/month automated (projection, per go-live email — upgrade
to actuals #revisit); eliminated interim manual entry.

## Reflections
Learned to negotiate scope with the payments compliance team early, not after
design lock.
