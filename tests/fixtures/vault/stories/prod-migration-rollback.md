---
type: story
competencies: [ownership, learning-from-failure, systems-thinking]
roles: [acme-payments-rotation]
---
While improving a shared CI action used org-wide, a bad default silently
disabled a rollback step. Situation: a production migration failed halfway
through and the automated rollback didn't fire. Action: paged in, diagnosed
the missing rollback trigger, and manually rolled back the schema change
within the maintenance window. Lesson: added a synthetic rollback drill to the
CI action's own test suite so the failure mode couldn't recur silently.
