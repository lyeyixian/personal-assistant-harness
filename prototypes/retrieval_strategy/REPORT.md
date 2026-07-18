# Prototype run report — retrieval strategy (#6)

Run: 2026-07-19, against the seeded vault + Temus "AI Engineer" (Singapore) posting fetched from the Greenhouse API. Token counts are chars/4 estimates.

```
========================================================================
A. CORPUS MEASUREMENT (curated notes; journal + README excluded)
========================================================================
     218 tok  profile.md
     432 tok  direction.md
     710 tok  skills.md
     217 tok  roles/acfirst-freelance.md
     442 tok  roles/gic-atlas-rotation.md
   1,752 tok  roles/gic-controllership.md
     760 tok  roles/gic-dealcloud-rotation.md
     606 tok  roles/gic-gpp-programme.md
     566 tok  roles/gic-ieto.md
   1,066 tok  roles/gic-ispmone-rotation.md
     413 tok  roles/two-app-studio-intern.md
     158 tok  roles/two-app-studio-parttime.md
     348 tok  projects/cs3203-spa.md
     176 tok  projects/gic-hackathon.md
     170 tok  projects/kecca-orbital.md
     156 tok  projects/module-planner.md
     344 tok  projects/personal-assistant-harness.md
     210 tok  projects/teammates.md
     179 tok  projects/wanderlust.md
     165 tok  stories/breaking-shared-ci-action.md
     155 tok  stories/cs3203-query-redesign.md
     182 tok  stories/engineering-culture-legacy.md
     175 tok  stories/jfrog-versioning-fix.md
     178 tok  stories/leading-eurovest-stp.md
     152 tok  stories/localhost-tunnel-incident.md
     128 tok  stories/mdm-api-flipflop.md
     166 tok  stories/mdm-entity-service-from-vagueness.md
  10,224 tok  TOTAL  (40,937 chars)

========================================================================
B. FULL-CONTEXT: one fit-analysis prompt = system + corpus + posting
========================================================================
  assembled prompt: 11,494 tok (est.)
    claude-sonnet-5: $0.0345/call cold, $0.0034/call with prompt-cache read (1.1% of 1000k window)
    claude-haiku-4-5: $0.0115/call cold, $0.0011/call with prompt-cache read (5.7% of 200k window)
  written to ~/Documents/repo/personal-assistant-harness/.claude/worktrees/wayfinder-6-retrieval-strategy/prototypes/retrieval_strategy/out/full_context_prompt.txt

========================================================================
C. STRUCTURED RETRIEVAL: frontmatter skill-filter against the posting
========================================================================
  skill registry size: 60 slugs
  posting-matched slugs: ['ci-cd', 'datadog', 'docker']
  kept   11 notes, 5,443 tok
      + profile.md
      + direction.md
      + skills.md
      + roles/gic-controllership.md
      + roles/gic-ispmone-rotation.md
      + roles/two-app-studio-intern.md
      + stories/breaking-shared-ci-action.md
      + stories/engineering-culture-legacy.md
      + stories/jfrog-versioning-fix.md
      + stories/leading-eurovest-stp.md
      + stories/localhost-tunnel-incident.md
  dropped 16 notes, 4,781 tok
      - roles/acfirst-freelance.md
      - roles/gic-atlas-rotation.md
      - roles/gic-dealcloud-rotation.md
      - roles/gic-gpp-programme.md
      - roles/gic-ieto.md
      - roles/two-app-studio-parttime.md
      - projects/cs3203-spa.md
      - projects/gic-hackathon.md
      - projects/kecca-orbital.md
      - projects/module-planner.md
      - projects/personal-assistant-harness.md
      - projects/teammates.md
      - projects/wanderlust.md
      - stories/cs3203-query-redesign.md
      - stories/mdm-api-flipflop.md
      - stories/mdm-entity-service-from-vagueness.md
  assembled filtered prompt: 6,496 tok (saves 4,998 tok, 43%)
    claude-sonnet-5: $0.0195/call cold, $0.0019/call with prompt-cache read (0.6% of 1000k window)
    claude-haiku-4-5: $0.0065/call cold, $0.0006/call with prompt-cache read (3.2% of 200k window)
  written to ~/Documents/repo/personal-assistant-harness/.claude/worktrees/wayfinder-6-retrieval-strategy/prototypes/retrieval_strategy/out/structured_prompt.txt
```
